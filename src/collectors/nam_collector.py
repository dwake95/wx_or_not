#!/usr/bin/env python3
"""NAM forecast data collector with multi-region and storage tier support."""
import sys
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
import requests
import xarray as xr
import numpy as np
from loguru import logger
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.database import get_db_connection
from src.utils.storage import get_storage_path, check_available_space
from src.config import settings


# NAM Configuration
NAM_BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_nam.pl"
MODEL_NAME = "NAM"

# Regional boundaries (same as GFS)
REGIONS = {
    'southern_ca': {
        'name': 'Southern California',
        'lat_min': 30.0, 'lat_max': 36.0,
        'lon_min': -122.0, 'lon_max': -114.0
    },
    'colorado': {
        'name': 'Colorado Rockies',
        'lat_min': 37.0, 'lat_max': 42.0,
        'lon_min': -110.0, 'lon_max': -104.0
    },
    'great_lakes': {
        'name': 'Great Lakes',
        'lat_min': 40.0, 'lat_max': 48.0,
        'lon_min': -92.0, 'lon_max': -78.0
    },
    'gulf_coast': {
        'name': 'Gulf Coast',
        'lat_min': 26.0, 'lat_max': 32.0,
        'lon_min': -98.0, 'lon_max': -87.0
    },
    'pacific_nw': {
        'name': 'Pacific Northwest',
        'lat_min': 43.0, 'lat_max': 50.0,
        'lon_min': -128.0, 'lon_max': -120.0
    }
}

# NAM variables to download
NAM_VARIABLES = {
    'TMP': {'level': '2_m_above_ground', 'name': 'temperature_2m'},
    'UGRD': {'level': '10_m_above_ground', 'name': 'u_wind_10m'},
    'VGRD': {'level': '10_m_above_ground', 'name': 'v_wind_10m'},
    'PRMSL': {'level': 'mean_sea_level', 'name': 'mslp'}
}

# Default forecast hours for NAM (more frequent than GFS)
DEFAULT_FORECAST_HOURS = [0, 3, 6, 12, 18, 24, 36, 48, 60, 72, 84]


def get_latest_nam_cycle() -> Tuple[datetime, int]:
    """
    Get the latest available NAM cycle.

    NAM runs at 00, 06, 12, 18 UTC. Data is typically available 2-3 hours after cycle time.

    Returns:
        Tuple of (cycle_date, cycle_hour)
    """
    now = datetime.now(timezone.utc)
    # Subtract 3 hours to ensure data is available
    safe_time = now - timedelta(hours=3)

    # Round down to nearest 6-hour cycle
    cycle_hour = (safe_time.hour // 6) * 6
    cycle_date = safe_time.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)

    logger.info(f"Using NAM cycle: {cycle_date.strftime('%Y%m%d')} {cycle_hour:02d}Z")
    return cycle_date, cycle_hour


def build_nam_url(cycle_date: datetime, cycle_hour: int, forecast_hour: int,
                  region: Dict[str, float]) -> str:
    """
    Build NAM download URL for NOAA NOMADS filter service.

    Args:
        cycle_date: Date of the model initialization
        cycle_hour: Hour of model initialization (00, 06, 12, 18)
        forecast_hour: Forecast lead time in hours
        region: Dictionary with lat/lon bounds

    Returns:
        Download URL string
    """
    date_str = cycle_date.strftime('%Y%m%d')
    cycle_str = f"{cycle_hour:02d}"

    # NAM filename pattern
    file_param = f"nam.t{cycle_str}z.awphys{forecast_hour:02d}.tm00.grib2"

    # Build the directory parameter
    dir_param = f"/nam.{date_str}"

    # Build URL with all variables
    var_params = []
    lev_params = []
    for var, info in NAM_VARIABLES.items():
        var_params.append(f"var_{var}=on")
        lev_params.append(f"lev_{info['level']}=on")

    params = {
        'file': file_param,
        'subregion': '',
        'leftlon': str(region['lon_min']),
        'rightlon': str(region['lon_max']),
        'toplat': str(region['lat_max']),
        'bottomlat': str(region['lat_min']),
        'dir': dir_param
    }

    # Construct URL
    url = NAM_BASE_URL + '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
    url += '&' + '&'.join(var_params + lev_params)

    return url


def calculate_md5(file_path: Path) -> str:
    """Calculate MD5 checksum of a file."""
    md5_hash = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def download_grib_file(url: str, output_path: Path, max_retries: int = 3) -> bool:
    """
    Download GRIB file from NOAA NOMADS with retry logic.

    Args:
        url: Download URL
        output_path: Path to save the file
        max_retries: Maximum number of retry attempts

    Returns:
        True if successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading (attempt {attempt + 1}/{max_retries}): {output_path.name}")

            response = requests.get(url, timeout=180, stream=True)
            response.raise_for_status()

            # Get file size
            total_size = int(response.headers.get('content-length', 0))

            # Download with progress
            downloaded = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.success(f"Downloaded {output_path.name} ({file_size_mb:.2f} MB)")
            return True

        except requests.exceptions.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to download after {max_retries} attempts")
                return False

    return False


def convert_to_netcdf(grib_file: Path) -> Optional[Path]:
    """
    Convert GRIB2 file to NetCDF format.

    Args:
        grib_file: Path to GRIB2 file

    Returns:
        Path to NetCDF file if successful, None otherwise
    """
    try:
        netcdf_file = grib_file.with_suffix('.nc')

        logger.info(f"Converting to NetCDF: {grib_file.name}")

        # Open with cfgrib and save as NetCDF
        ds = xr.open_dataset(grib_file, engine='cfgrib')
        ds.to_netcdf(netcdf_file)
        ds.close()

        nc_size_mb = netcdf_file.stat().st_size / (1024 * 1024)
        logger.success(f"Created NetCDF: {netcdf_file.name} ({nc_size_mb:.2f} MB)")

        return netcdf_file

    except Exception as e:
        logger.error(f"Failed to convert {grib_file} to NetCDF: {e}")
        return None


def extract_point_data(grib_file: Path, init_time: datetime, valid_time: datetime,
                      lead_time_hours: int) -> int:
    """
    Extract point data from GRIB file and insert into database.

    Args:
        grib_file: Path to GRIB file
        init_time: Model initialization time
        valid_time: Forecast valid time
        lead_time_hours: Forecast lead time

    Returns:
        Number of records inserted
    """
    try:
        ds = xr.open_dataset(grib_file, engine='cfgrib')

        # Get coordinates
        lats = ds['latitude'].values
        lons = ds['longitude'].values

        # Sample every 0.5 degrees to reduce database size
        # NAM is 12km (~0.11 degrees), so sample every ~4-5 points
        lat_step = 4
        lon_step = 4

        records = []

        # Extract variables
        for var_key, var_info in NAM_VARIABLES.items():
            var_name = var_info['name']

            # Find variable in dataset
            for ds_var in ds.data_vars:
                if var_name.lower() in str(ds_var).lower() or var_key.lower() in str(ds_var).lower():
                    data = ds[ds_var].values

                    # Sample points
                    for i in range(0, len(lats), lat_step):
                        for j in range(0, len(lons), lon_step):
                            value = float(data[i, j]) if data.ndim == 2 else float(data[0, i, j])
                            if not np.isnan(value):
                                records.append((
                                    MODEL_NAME,
                                    init_time,
                                    valid_time,
                                    lead_time_hours,
                                    float(lats[i]),
                                    float(lons[j]),
                                    var_name,
                                    value,
                                    ds[ds_var].attrs.get('units', '')
                                ))
                    break

        ds.close()

        # Insert into database
        if records:
            with get_db_connection() as conn:
                cur = conn.cursor()
                insert_query = """
                    INSERT INTO model_forecasts
                    (model_name, init_time, valid_time, lead_time_hours,
                     location_lat, location_lon, variable, value, units)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cur.executemany(insert_query, records)
                inserted = cur.rowcount
                cur.close()

                logger.success(f"Inserted {inserted} forecast records into database")
                return inserted

        return 0

    except Exception as e:
        logger.error(f"Failed to extract point data from {grib_file}: {e}")
        return 0


def store_file_metadata(file_path: Path, model: str, init_time: datetime,
                       forecast_hour: int, region_name: str, file_type: str) -> bool:
    """Store file metadata in database for tracking."""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'file_registry'
                )
            """)
            table_exists = cur.fetchone()[0]

            if not table_exists:
                logger.debug("file_registry table doesn't exist, skipping metadata storage")
                return True

            checksum = calculate_md5(file_path)
            file_size = file_path.stat().st_size
            tier = 'nas' if str(file_path).startswith(str(settings.nas_storage_path)) else 'local'

            insert_query = """
                INSERT INTO file_registry
                (model_name, init_time, forecast_hour, region, file_type,
                 storage_tier, file_path, file_size_bytes, checksum)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            cur.execute(insert_query, (
                model, init_time, forecast_hour, region_name, file_type,
                tier, str(file_path), file_size, checksum
            ))
            cur.close()

            logger.debug(f"Stored file metadata: {file_path.name}")
            return True

    except Exception as e:
        logger.warning(f"Failed to store file metadata: {e}")
        return False


def collect_nam_forecast(region_name: str, forecast_hours: List[int],
                        init_time: Optional[datetime] = None,
                        init_hour: Optional[int] = None) -> Dict[str, any]:
    """
    Collect NAM forecast for a specific region.

    Args:
        region_name: Region identifier
        forecast_hours: List of forecast hours to download
        init_time: Specific initialization time (default: latest)
        init_hour: Specific initialization hour (default: latest)

    Returns:
        Dictionary with collection statistics
    """
    if region_name not in REGIONS:
        logger.error(f"Unknown region: {region_name}")
        return {'success': False}

    region = REGIONS[region_name]
    logger.info(f"Collecting NAM forecasts for {region['name']}")

    # Check available disk space
    space_check = check_available_space('local')
    if 'free_space_gb' in space_check and space_check['free_space_gb'] < 10:
        logger.error(f"Insufficient disk space: {space_check['free_space_gb']:.1f} GB free")
        return {'success': False, 'error': 'insufficient_space'}

    # Get initialization time
    if init_time is None or init_hour is None:
        init_time, init_hour = get_latest_nam_cycle()

    # Create storage directory
    date_str = init_time.strftime('%Y%m%d')
    storage_dir = get_storage_path('nam', init_time, tier='local')
    storage_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        'region': region_name,
        'init_time': init_time,
        'files_downloaded': 0,
        'files_converted': 0,
        'records_inserted': 0,
        'success': True
    }

    # Download each forecast hour
    for i, fhour in enumerate(forecast_hours, 1):
        logger.info(f"Processing forecast hour {fhour} ({i}/{len(forecast_hours)})")

        valid_time = init_time + timedelta(hours=fhour)

        # Build filename
        filename = f"nam_{date_str}_{init_hour:02d}z_f{fhour:02d}_{region_name}.grb2"
        grib_file = storage_dir / filename

        # Skip if already exists
        if grib_file.exists():
            logger.info(f"File already exists, skipping: {filename}")
            stats['files_downloaded'] += 1
            continue

        # Build URL and download
        url = build_nam_url(init_time, init_hour, fhour, region)

        if download_grib_file(url, grib_file):
            stats['files_downloaded'] += 1

            # Store file metadata
            store_file_metadata(grib_file, MODEL_NAME, init_time, fhour, region_name, 'grb2')

            # Convert to NetCDF
            netcdf_file = convert_to_netcdf(grib_file)
            if netcdf_file:
                stats['files_converted'] += 1
                store_file_metadata(netcdf_file, MODEL_NAME, init_time, fhour, region_name, 'nc')

            # Extract point data for database
            records = extract_point_data(grib_file, init_time, valid_time, fhour)
            stats['records_inserted'] += records
        else:
            logger.error(f"Failed to download forecast hour {fhour}")
            stats['success'] = False

    # Log final statistics
    logger.info("=" * 60)
    logger.info(f"Collection complete for {region['name']}")
    logger.info(f"Files downloaded: {stats['files_downloaded']}/{len(forecast_hours)}")
    logger.info(f"Files converted: {stats['files_converted']}")
    logger.info(f"Database records: {stats['records_inserted']}")
    logger.info("=" * 60)

    return stats


def main():
    """Main entry point for NAM collector."""
    parser = argparse.ArgumentParser(description='NAM Forecast Collector')
    parser.add_argument('--region',
                       choices=['all'] + list(REGIONS.keys()),
                       default='all',
                       help='Region to collect')
    parser.add_argument('--forecast-hours', nargs='+', type=int,
                       default=DEFAULT_FORECAST_HOURS,
                       help='Forecast hours to download')
    parser.add_argument('--init-time',
                       help='Initialization time (YYYYMMDDHH or "latest")')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("NAM Forecast Collector (Multi-Region)")
    logger.info("=" * 60)

    # Determine regions to collect
    if args.region == 'all':
        regions_to_collect = list(REGIONS.keys())
    else:
        regions_to_collect = [args.region]

    # Parse init time if provided
    init_time = None
    init_hour = None
    if args.init_time and args.init_time != 'latest':
        try:
            init_time = datetime.strptime(args.init_time, '%Y%m%d%H')
            init_time = init_time.replace(tzinfo=timezone.utc)
            init_hour = init_time.hour
        except ValueError:
            logger.error(f"Invalid init time format: {args.init_time}")
            return 1

    # Collect for each region
    all_stats = []
    for region in regions_to_collect:
        stats = collect_nam_forecast(region, args.forecast_hours, init_time, init_hour)
        all_stats.append(stats)

    # Summary
    total_files = sum(s['files_downloaded'] for s in all_stats)
    total_records = sum(s['records_inserted'] for s in all_stats)

    logger.info("=" * 60)
    logger.info("COLLECTION SUMMARY")
    logger.info(f"Regions processed: {len(all_stats)}")
    logger.info(f"Total files downloaded: {total_files}")
    logger.info(f"Total database records: {total_records}")
    logger.info("=" * 60)

    # Check if all successful
    if all(s['success'] for s in all_stats):
        logger.success("All collections completed successfully")
        return 0
    else:
        logger.warning("Some collections failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
