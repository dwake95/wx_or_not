#!/usr/bin/env python3
"""
HRRR (High-Resolution Rapid Refresh) Forecast Data Collector

HRRR Specifications:
- Resolution: 3km (highest resolution operational model)
- Update frequency: Hourly
- Coverage: Continental United States (CONUS)
- Forecast range: 0-18 hours
- Data source: NOMADS GRIB2

Key advantages:
- Best for local-scale forecasts
- Excellent for convective weather (thunderstorms)
- Great for aviation and energy applications
"""
import sys
import argparse
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


# HRRR Configuration
HRRR_BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_hrrr_2d.pl"
MODEL_NAME = "HRRR"

# Regional boundaries (same as GFS/NAM for consistency)
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

# HRRR variables to download
HRRR_VARIABLES = {
    'TMP': {'level': '2_m_above_ground', 'name': 'temperature_2m'},
    'UGRD': {'level': '10_m_above_ground', 'name': 'u_wind_10m'},
    'VGRD': {'level': '10_m_above_ground', 'name': 'v_wind_10m'},
    'MSLMA': {'level': 'mean_sea_level', 'name': 'mslp'}  # HRRR uses MSLMA instead of PRMSL
}

# HRRR forecast hours (0-18, hourly)
DEFAULT_FORECAST_HOURS = [0, 1, 3, 6, 12, 18]


def get_latest_hrrr_cycle() -> Tuple[datetime, int]:
    """
    Get the latest available HRRR cycle.

    HRRR runs hourly. Data is typically available 45-60 minutes after cycle time.

    Returns:
        Tuple of (cycle_date, cycle_hour)
    """
    now = datetime.now(timezone.utc)
    # Subtract 1.5 hours to ensure data is available
    safe_time = now - timedelta(hours=1, minutes=30)

    cycle_date = safe_time.replace(minute=0, second=0, microsecond=0)
    cycle_hour = cycle_date.hour

    logger.info(f"Latest HRRR cycle: {cycle_date.strftime('%Y%m%d')} {cycle_hour:02d}Z")
    return cycle_date, cycle_hour


def build_hrrr_url(cycle_date: datetime, cycle_hour: int, forecast_hour: int,
                   region: Dict[str, float]) -> str:
    """
    Build NOMADS filter URL for HRRR data.

    Args:
        cycle_date: Model initialization date
        cycle_hour: Model initialization hour (0-23)
        forecast_hour: Forecast lead time in hours
        region: Dictionary with lat/lon boundaries

    Returns:
        NOMADS filter URL for HRRR GRIB2 data
    """
    date_str = cycle_date.strftime('%Y%m%d')

    # HRRR file naming: hrrr.t{HH}z.wrfsfcf{FF}.grib2
    file_name = f"hrrr.t{cycle_hour:02d}z.wrfsfcf{forecast_hour:02d}.grib2"

    # Build filter URL with regional subsetting
    params = {
        'file': file_name,
        'dir': f'/hrrr.{date_str}/conus',
        'subregion': '',
        'toplat': region['lat_max'],
        'leftlon': region['lon_min'],
        'rightlon': region['lon_max'],
        'bottomlat': region['lat_min'],
    }

    # Add variable selections
    for var, config in HRRR_VARIABLES.items():
        level_key = f'lev_{config["level"]}'
        params[level_key] = 'on'
        params[f'var_{var}'] = 'on'

    # Build query string
    query_parts = [f"{k}={v}" for k, v in params.items()]
    url = f"{HRRR_BASE_URL}?{'&'.join(query_parts)}"

    return url


def download_hrrr_data(url: str, output_path: Path, max_retries: int = 3) -> bool:
    """
    Download HRRR GRIB2 data from NOMADS.

    Args:
        url: NOMADS filter URL
        output_path: Where to save the data
        max_retries: Maximum download attempts

    Returns:
        True if download successful, False otherwise
    """
    for attempt in range(max_retries):
        try:
            logger.info(f"Downloading HRRR data (attempt {attempt + 1}/{max_retries})")
            logger.debug(f"URL: {url[:100]}...")

            response = requests.get(url, timeout=120)
            response.raise_for_status()

            # Save GRIB2 data
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(response.content)

            file_size = output_path.stat().st_size / 1024  # KB
            logger.info(f"Downloaded {file_size:.1f} KB to {output_path.name}")
            return True

        except requests.exceptions.RequestException as e:
            logger.warning(f"Download attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))  # Exponential backoff

    logger.error(f"Failed to download after {max_retries} attempts")
    return False


def process_hrrr_grib(grib_path: Path, region_name: str) -> List[Dict]:
    """
    Process HRRR GRIB2 file and extract forecast data.

    Uses a simple approach: open GRIB once, extract what we can, ignore warnings.

    Args:
        grib_path: Path to GRIB2 file
        region_name: Name of the region

    Returns:
        List of forecast records ready for database insertion
    """
    try:
        logger.info(f"Processing GRIB file: {grib_path.name}")

        # Open GRIB2 file - it will warn about multi-level variables but that's okay
        # cfgrib will just pick one level for each variable
        ds = xr.open_dataset(grib_path, engine='cfgrib')

        records = []

        # Extract initialization and valid times
        if 'time' in ds.coords:
            init_time = pd.Timestamp(ds.time.values).to_pydatetime()
        elif 'valid_time' in ds.coords:
            # Use valid_time and work backwards if we have step
            valid_time = pd.Timestamp(ds.valid_time.values).to_pydatetime()
            if 'step' in ds.coords:
                forecast_step = pd.Timedelta(ds.step.values).total_seconds() / 3600
                init_time = valid_time - timedelta(hours=forecast_step)
            else:
                init_time = valid_time
        else:
            # Extract from filename as fallback
            import re
            match = re.search(r'hrrr_(\d{8})_(\d{2})z_f(\d{2})', grib_path.name)
            if match:
                date_str, hour_str, fhour_str = match.groups()
                from datetime import datetime
                init_time = datetime.strptime(f"{date_str}{hour_str}", "%Y%m%d%H").replace(tzinfo=timezone.utc)
                forecast_step = int(fhour_str)
                valid_time = init_time + timedelta(hours=forecast_step)
                logger.info(f"Extracted time from filename: init={init_time}, step={forecast_step}h")
            else:
                logger.error("No time coordinate in GRIB file and couldn't parse filename")
                return records

        if 'step' in ds.coords:
            forecast_step = pd.Timedelta(ds.step.values).total_seconds() / 3600
            valid_time = init_time + timedelta(hours=forecast_step)
        else:
            forecast_step = 0
            valid_time = init_time

        # Get lat/lon grids
        lats = ds.latitude.values
        lons = ds.longitude.values

        # Convert longitudes from 0-360 to -180-180 if needed
        if lons.max() > 180:
            lons = np.where(lons > 180, lons - 360, lons)

        # Create meshgrid for coordinates
        if lats.ndim == 1 and lons.ndim == 1:
            lon_grid, lat_grid = np.meshgrid(lons, lats)
        else:
            lat_grid = lats
            lon_grid = lons

        # Try to extract each variable we want
        # cfgrib will have opened what it could, we just look for them
        var_map = {
            't2m': 'temperature_2m',
            'u10': 'u_wind_10m',
            'v10': 'v_wind_10m',
            'prmsl': 'mslp',
            'msl': 'mslp',  # alternative name
            'TMP': 'temperature_2m',  # sometimes cfgrib uses GRIB shortName
            'UGRD': 'u_wind_10m',
            'VGRD': 'v_wind_10m',
        }

        for ds_var_name in ds.data_vars:
            # Map to our standardized variable name
            var_name = var_map.get(ds_var_name, ds_var_name)

            try:
                values = ds[ds_var_name].values

                # Flatten arrays for database storage
                if values.ndim == 2:
                    flat_lats = lat_grid.flatten()
                    flat_lons = lon_grid.flatten()
                    flat_values = values.flatten()
                elif values.ndim == 0:
                    # Scalar value
                    flat_lats = lat_grid.flatten()
                    flat_lons = lon_grid.flatten()
                    flat_values = np.full_like(flat_lats, float(values))
                else:
                    logger.warning(f"Unexpected dimensionality for {ds_var_name}: {values.ndim}D")
                    continue

                # Remove NaN/invalid values
                valid_mask = ~np.isnan(flat_values)

                # Get units from GRIB attributes
                units = ds[ds_var_name].attrs.get('units', '')

                # Create records
                for lat, lon, val in zip(flat_lats[valid_mask],
                                         flat_lons[valid_mask],
                                         flat_values[valid_mask]):
                    records.append({
                        'model_name': MODEL_NAME,
                        'init_time': init_time,
                        'valid_time': valid_time,
                        'lead_time_hours': int(forecast_step),
                        'location_lat': float(lat),
                        'location_lon': float(lon),
                        'variable': var_name,
                        'value': float(val),
                        'units': units
                    })

                logger.info(f"Extracted {sum(valid_mask)} points for {var_name} (from {ds_var_name})")

            except Exception as e:
                logger.warning(f"Could not process variable {ds_var_name}: {e}")
                continue

        ds.close()
        logger.info(f"Processed {len(records)} total forecast points")
        return records

    except Exception as e:
        logger.error(f"Error processing GRIB file: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


def save_to_database(records: List[Dict]) -> int:
    """
    Save forecast records to database.

    Args:
        records: List of forecast dictionaries

    Returns:
        Number of records saved
    """
    if not records:
        logger.warning("No records to save")
        return 0

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Prepare batch insert
                insert_query = """
                    INSERT INTO model_forecasts (
                        model_name, init_time, valid_time, lead_time_hours,
                        location_lat, location_lon, variable, value, units
                    ) VALUES (
                        %(model_name)s, %(init_time)s, %(valid_time)s, %(lead_time_hours)s,
                        %(location_lat)s, %(location_lon)s, %(variable)s, %(value)s, %(units)s
                    )
                """

                cur.executemany(insert_query, records)
                conn.commit()

                inserted = cur.rowcount
                logger.info(f"Saved {inserted} records to database")
                return inserted

    except Exception as e:
        logger.error(f"Database error: {e}")
        return 0


def collect_hrrr_region(region_id: str, forecast_hours: List[int] = None) -> int:
    """
    Collect HRRR data for a specific region.

    Args:
        region_id: Region identifier (e.g., 'southern_ca')
        forecast_hours: List of forecast hours to collect

    Returns:
        Total number of records collected
    """
    if region_id not in REGIONS:
        logger.error(f"Unknown region: {region_id}")
        return 0

    region = REGIONS[region_id]
    forecast_hours = forecast_hours or DEFAULT_FORECAST_HOURS

    logger.info(f"Collecting HRRR data for {region['name']}")
    logger.info(f"Forecast hours: {forecast_hours}")

    # Get latest cycle
    cycle_date, cycle_hour = get_latest_hrrr_cycle()

    total_records = 0

    for fhour in forecast_hours:
        if fhour > 18:
            logger.warning(f"HRRR only forecasts to 18 hours, skipping {fhour}")
            continue

        logger.info(f"Processing forecast hour {fhour}")

        # Build download URL
        url = build_hrrr_url(cycle_date, cycle_hour, fhour, region)

        # Download data
        output_file = f"hrrr_{cycle_date.strftime('%Y%m%d')}_{cycle_hour:02d}z_f{fhour:02d}_{region_id}.grib2"
        storage_dir = get_storage_path('hrrr', cycle_date, tier='local')
        storage_dir.mkdir(parents=True, exist_ok=True)
        output_path = storage_dir / output_file

        if download_hrrr_data(url, output_path):
            # Process GRIB2 file
            records = process_hrrr_grib(output_path, region_id)

            # Save to database
            saved = save_to_database(records)
            total_records += saved

            # Clean up GRIB file to save space
            output_path.unlink()
            logger.info(f"Cleaned up {output_path.name}")
        else:
            logger.error(f"Failed to download forecast hour {fhour}")

    logger.info(f"Total records collected for {region['name']}: {total_records}")
    return total_records


def main():
    """Main entry point for HRRR collector."""
    parser = argparse.ArgumentParser(description='Collect HRRR forecast data')
    parser.add_argument('--region', choices=list(REGIONS.keys()) + ['all'],
                       default='all', help='Region to collect data for')
    parser.add_argument('--forecast-hours', type=int, nargs='+',
                       default=DEFAULT_FORECAST_HOURS,
                       help='Forecast hours to collect')

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("HRRR DATA COLLECTOR")
    logger.info("=" * 70)
    logger.info(f"Model: {MODEL_NAME}")
    logger.info(f"Resolution: 3km (highest operational model)")
    logger.info(f"Update frequency: Hourly")

    # Check disk space
    space_check = check_available_space('local')
    if 'free_space_gb' in space_check and space_check['free_space_gb'] < 10:
        logger.error(f"Insufficient disk space: {space_check['free_space_gb']:.1f} GB free")
        return 1

    # Collect data
    regions_to_collect = list(REGIONS.keys()) if args.region == 'all' else [args.region]

    total_collected = 0
    for region_id in regions_to_collect:
        collected = collect_hrrr_region(region_id, args.forecast_hours)
        total_collected += collected

    logger.info("=" * 70)
    logger.info(f"COLLECTION COMPLETE: {total_collected} total records")
    logger.info("=" * 70)

    return 0 if total_collected > 0 else 1


if __name__ == '__main__':
    import pandas as pd  # Import here for timestamp conversion
    sys.exit(main())
