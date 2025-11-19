#!/usr/bin/env python3
"""GFS forecast data collector for Southern California region."""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple
import requests
import xarray as xr
import numpy as np
from loguru import logger
import tempfile
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.database import get_db_connection
from src.config import settings


# GFS Configuration
GFS_BASE_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
MODEL_NAME = "GFS_0.25"

# Southern California bounding box
LAT_MIN, LAT_MAX = 32.0, 34.0
LON_MIN, LON_MAX = 116.0, 118.0  # Will be converted to 0-360 for GFS

# Variables to extract with their GRIB filter names
GFS_VARIABLES = {
    'temperature_2m': {
        'filter_params': {'lev_2_m_above_ground': 'on', 'var_TMP': 'on'},
        'grib_name': 't2m',
        'db_variable': 'temperature_2m',
        'units': 'K'
    },
    'u_wind_10m': {
        'filter_params': {'lev_10_m_above_ground': 'on', 'var_UGRD': 'on'},
        'grib_name': 'u10',
        'db_variable': 'u_wind_10m',
        'units': 'm/s'
    },
    'v_wind_10m': {
        'filter_params': {'lev_10_m_above_ground': 'on', 'var_VGRD': 'on'},
        'grib_name': 'v10',
        'db_variable': 'v_wind_10m',
        'units': 'm/s'
    },
    'mslp': {
        'filter_params': {'lev_mean_sea_level': 'on', 'var_PRMSL': 'on'},
        'grib_name': 'prmsl',
        'db_variable': 'mslp',
        'units': 'Pa'
    }
}

# Forecast hours to download
FORECAST_HOURS = [0, 6, 12, 24, 48, 72]


def get_latest_gfs_cycle() -> Tuple[datetime, int]:
    """
    Get the latest available GFS cycle.

    GFS runs at 00, 06, 12, 18 UTC. Data is typically available 3-4 hours after cycle time.

    Returns:
        Tuple of (cycle_date, cycle_hour)
    """
    now = datetime.now(timezone.utc)
    # Subtract 4 hours to ensure data is available
    safe_time = now - timedelta(hours=4)

    # Round down to nearest 6-hour cycle
    cycle_hour = (safe_time.hour // 6) * 6
    cycle_date = safe_time.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)

    logger.info(f"Using GFS cycle: {cycle_date.strftime('%Y%m%d')} {cycle_hour:02d}Z")
    return cycle_date, cycle_hour


def build_gfs_url(cycle_date: datetime, cycle_hour: int, forecast_hour: int,
                  variable_params: Dict[str, str]) -> str:
    """
    Build GFS download URL for NOAA NOMADS filter service.

    Args:
        cycle_date: Date of the model initialization
        cycle_hour: Hour of model initialization (00, 06, 12, 18)
        forecast_hour: Forecast lead time in hours
        variable_params: Dictionary of filter parameters for variable selection

    Returns:
        Download URL string
    """
    # Convert longitude to 0-360 range (GFS uses this)
    lon_min_360 = LON_MIN if LON_MIN >= 0 else 360 + LON_MIN
    lon_max_360 = LON_MAX if LON_MAX >= 0 else 360 + LON_MAX

    date_str = cycle_date.strftime('%Y%m%d')
    cycle_str = f"{cycle_hour:02d}"

    # Build the file parameter
    file_param = f"gfs.t{cycle_str}z.pgrb2.0p25.f{forecast_hour:03d}"

    # Build the directory parameter (URL encoded)
    dir_param = f"/gfs.{date_str}/{cycle_str}/atmos"

    # Build URL with all parameters
    params = {
        'file': file_param,
        'subregion': '',
        'leftlon': str(lon_min_360),
        'rightlon': str(lon_max_360),
        'toplat': str(LAT_MAX),
        'bottomlat': str(LAT_MIN),
        'dir': dir_param
    }

    # Add variable-specific parameters
    params.update(variable_params)

    # Construct URL
    url = GFS_BASE_URL + '?' + '&'.join([f"{k}={v}" for k, v in params.items()])
    return url


def download_grib_file(url: str, output_path: Path) -> bool:
    """
    Download GRIB file from NOAA NOMADS.

    Args:
        url: Download URL
        output_path: Path to save the file

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Downloading: {url}")
        response = requests.get(url, timeout=120)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            f.write(response.content)

        logger.success(f"Downloaded {output_path.name} ({len(response.content) / 1024:.1f} KB)")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def extract_variable_data(grib_file: Path, variable_info: Dict) -> List[Dict]:
    """
    Extract variable data from GRIB file for the specified region.

    Args:
        grib_file: Path to GRIB file
        variable_info: Dictionary with variable metadata

    Returns:
        List of dictionaries with extracted data points
    """
    try:
        # Open GRIB file with cfgrib
        ds = xr.open_dataset(
            grib_file,
            engine='cfgrib',
            backend_kwargs={'indexpath': ''}
        )

        data_points = []

        # Get the variable name from the dataset
        # cfgrib often uses different names than expected
        var_name = None
        for possible_name in [variable_info['grib_name'], variable_info['db_variable']]:
            if possible_name in ds.variables:
                var_name = possible_name
                break

        # If not found, try to find by standard_name or long_name
        if var_name is None:
            for var in ds.variables:
                if var not in ['latitude', 'longitude', 'time', 'step', 'valid_time']:
                    var_name = var
                    break

        if var_name is None:
            logger.warning(f"Could not find variable in {grib_file.name}. Available: {list(ds.variables.keys())}")
            return data_points

        logger.info(f"Extracting variable: {var_name}")

        # Get the data
        data = ds[var_name]

        # Get coordinates
        lats = ds['latitude'].values
        lons = ds['longitude'].values

        # Convert longitudes from 0-360 to -180-180 if needed
        if lons.max() > 180:
            lons = np.where(lons > 180, lons - 360, lons)

        # Create meshgrid for lat/lon
        if lats.ndim == 1 and lons.ndim == 1:
            lon_grid, lat_grid = np.meshgrid(lons, lats)
        else:
            lat_grid, lon_grid = lats, lons

        # Extract values within our region
        values = data.values
        if values.ndim > 2:
            values = values.squeeze()

        # Filter to our region
        mask = (
            (lat_grid >= LAT_MIN) & (lat_grid <= LAT_MAX) &
            (lon_grid >= LON_MIN) & (lon_grid <= LON_MAX)
        )

        # Extract data points
        valid_lats = lat_grid[mask]
        valid_lons = lon_grid[mask]
        valid_values = values[mask]

        for lat, lon, value in zip(valid_lats, valid_lons, valid_values):
            if not np.isnan(value):
                data_points.append({
                    'lat': float(lat),
                    'lon': float(lon),
                    'value': float(value),
                    'variable': variable_info['db_variable'],
                    'units': variable_info['units']
                })

        logger.success(f"Extracted {len(data_points)} data points for {variable_info['db_variable']}")
        ds.close()
        return data_points

    except Exception as e:
        logger.error(f"Failed to extract data from {grib_file}: {e}")
        return []


def insert_forecast_data(data_points: List[Dict], init_time: datetime,
                        valid_time: datetime, lead_time_hours: int) -> int:
    """
    Insert forecast data into the database.

    Args:
        data_points: List of data point dictionaries
        init_time: Model initialization time
        valid_time: Forecast valid time
        lead_time_hours: Forecast lead time in hours

    Returns:
        Number of records inserted
    """
    if not data_points:
        return 0

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # Prepare bulk insert
            insert_query = """
                INSERT INTO model_forecasts
                (model_name, init_time, valid_time, lead_time_hours,
                 location_lat, location_lon, variable, value, units)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            records = [
                (
                    MODEL_NAME,
                    init_time,
                    valid_time,
                    lead_time_hours,
                    point['lat'],
                    point['lon'],
                    point['variable'],
                    point['value'],
                    point['units']
                )
                for point in data_points
            ]

            cur.executemany(insert_query, records)
            inserted = cur.rowcount
            cur.close()

            logger.success(f"Inserted {inserted} forecast records into database")
            return inserted

    except Exception as e:
        logger.error(f"Failed to insert data into database: {e}")
        return 0


def collect_gfs_forecast(cycle_date: datetime = None, cycle_hour: int = None) -> Dict[str, int]:
    """
    Main collection function to download and process GFS forecasts.

    Args:
        cycle_date: Model initialization date (default: auto-detect latest)
        cycle_hour: Model initialization hour (default: auto-detect latest)

    Returns:
        Dictionary with statistics
    """
    # Get latest cycle if not specified
    if cycle_date is None or cycle_hour is None:
        cycle_date, cycle_hour = get_latest_gfs_cycle()

    init_time = cycle_date.replace(hour=cycle_hour)

    stats = {
        'total_downloads': 0,
        'successful_downloads': 0,
        'total_points': 0,
        'total_inserted': 0
    }

    # Create temporary directory for downloads
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Process each variable and forecast hour
        for var_name, var_info in GFS_VARIABLES.items():
            logger.info(f"Processing variable: {var_name}")

            for forecast_hour in FORECAST_HOURS:
                stats['total_downloads'] += 1

                # Calculate valid time
                valid_time = init_time + timedelta(hours=forecast_hour)

                # Build URL and download
                url = build_gfs_url(cycle_date, cycle_hour, forecast_hour, var_info['filter_params'])
                grib_file = temp_path / f"gfs_{var_name}_f{forecast_hour:03d}.grib2"

                if not download_grib_file(url, grib_file):
                    continue

                stats['successful_downloads'] += 1

                # Extract data
                data_points = extract_variable_data(grib_file, var_info)
                stats['total_points'] += len(data_points)

                # Insert into database
                inserted = insert_forecast_data(data_points, init_time, valid_time, forecast_hour)
                stats['total_inserted'] += inserted

                # Clean up GRIB file
                grib_file.unlink()

    return stats


def main():
    """Main entry point for the GFS collector."""
    logger.info("=" * 60)
    logger.info("GFS Forecast Collector - Southern California")
    logger.info("=" * 60)

    try:
        stats = collect_gfs_forecast()

        logger.info("=" * 60)
        logger.info("Collection Summary:")
        logger.info(f"  Total download attempts: {stats['total_downloads']}")
        logger.info(f"  Successful downloads: {stats['successful_downloads']}")
        logger.info(f"  Total data points extracted: {stats['total_points']}")
        logger.info(f"  Total records inserted: {stats['total_inserted']}")
        logger.info("=" * 60)

        if stats['total_inserted'] > 0:
            logger.success("GFS collection completed successfully!")
        else:
            logger.warning("No data was inserted. Check logs for errors.")

    except Exception as e:
        logger.exception(f"Fatal error in GFS collection: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
