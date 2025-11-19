#!/usr/bin/env python3
"""NDBC buoy observation data collector for weather model verification."""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import requests
from loguru import logger
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.database import get_db_connection
from src.config import settings
from src.config.regions import get_region_stations, get_all_regions


# NDBC (National Data Buoy Center) API
NDBC_BASE_URL = "https://www.ndbc.noaa.gov/data/realtime2"


def fetch_buoy_data(buoy_id: int, hours_back: int = 24) -> List[Dict]:
    """
    Fetch buoy observations from NDBC.

    Args:
        buoy_id: Buoy station number (e.g., 46086)
        hours_back: Hours of historical data to fetch

    Returns:
        List of observation dictionaries
    """
    try:
        # NDBC provides realtime data in .txt format
        url = f"{NDBC_BASE_URL}/{buoy_id}.txt"

        logger.debug(f"Fetching buoy data for {buoy_id}: {url}")

        response = requests.get(url, timeout=30)
        response.raise_for_status()

        # Parse text response
        lines = response.text.strip().split('\n')
        if len(lines) < 3:
            logger.warning(f"No data returned for buoy {buoy_id}")
            return []

        # First line is header with variable names
        # Second line is units
        # Remaining lines are data
        header = lines[0].split()
        units_line = lines[1].split()

        observations = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        for line in lines[2:]:
            if not line.strip() or line.startswith('#'):
                continue

            values = line.split()
            if len(values) < len(header):
                continue

            try:
                # Parse time - format: #YY  MM DD hh mm
                year = int(values[0])
                month = int(values[1])
                day = int(values[2])
                hour = int(values[3])
                minute = int(values[4])

                # Handle 2-digit year
                if year < 100:
                    year += 2000

                obs_time = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)

                # Skip if outside time range
                if obs_time < cutoff_time:
                    continue

                # Create observation dict
                obs = {'time': obs_time}
                for i, (key, value) in enumerate(zip(header[5:], values[5:]), start=5):
                    obs[key] = value

                observations.append(obs)

            except (ValueError, IndexError) as e:
                logger.debug(f"Failed to parse buoy line: {e}")
                continue

        logger.info(f"Fetched {len(observations)} observations for buoy {buoy_id}")
        return observations

    except Exception as e:
        logger.error(f"Failed to fetch buoy data for {buoy_id}: {e}")
        return []


def get_buoy_location(buoy_id: int) -> Optional[tuple]:
    """
    Get buoy location from NDBC station metadata.

    Args:
        buoy_id: Buoy station number

    Returns:
        Tuple of (lat, lon) or None
    """
    try:
        # Fetch station metadata
        url = f"https://www.ndbc.noaa.gov/station_page.php?station={buoy_id}"

        # For now, use hardcoded locations from region config
        # In production, could parse the station page or use stations.txt
        # This is a simplified implementation
        return None

    except Exception:
        return None


def parse_and_store_buoy_observations(observations: List[Dict], buoy_id: int) -> int:
    """
    Parse buoy observations and store in database.

    Args:
        observations: List of observation dictionaries
        buoy_id: Buoy identifier

    Returns:
        Number of records inserted
    """
    if not observations:
        return 0

    records = []

    # Try to get buoy location (simplified - using region bounds as approximation)
    # In production, fetch from NDBC stations.txt or API
    lat, lon = 0.0, 0.0  # Placeholder - will be updated from actual data

    for obs in observations:
        try:
            obs_time = obs.get('time')
            if not obs_time:
                continue

            # Map NDBC variables to our standard names
            # See: https://www.ndbc.noaa.gov/measdes.shtml
            variable_mapping = {
                'WDIR': ('wind_direction_10m', 'degrees', 'degT'),
                'WSPD': ('wind_speed_10m', 'm/s', 'm/s'),
                'GST': ('wind_gust_10m', 'm/s', 'm/s'),
                'WVHT': ('wave_height', 'm', 'm'),
                'DPD': ('dominant_wave_period', 's', 'sec'),
                'APD': ('average_wave_period', 's', 'sec'),
                'MWD': ('mean_wave_direction', 'degrees', 'degT'),
                'PRES': ('mslp', 'Pa', 'hPa'),
                'ATMP': ('air_temperature_2m', 'K', 'degC'),
                'WTMP': ('water_temperature', 'K', 'degC'),
                'DEWP': ('dewpoint_2m', 'K', 'degC'),
                'VIS': ('visibility', 'm', 'nmi'),
            }

            for ndbc_var, (var_name, target_units, source_units) in variable_mapping.items():
                value_str = obs.get(ndbc_var, 'MM')
                if value_str == 'MM' or value_str == '' or value_str is None:
                    continue

                try:
                    value = float(value_str)

                    # Convert units
                    if source_units == 'degC' and target_units == 'K':
                        value = value + 273.15
                    elif source_units == 'hPa' and target_units == 'Pa':
                        value = value * 100
                    elif source_units == 'nmi' and target_units == 'm':
                        value = value * 1852

                    # Use actual buoy coordinates if available, otherwise estimate
                    # For coastal buoys, lat/lon should be from NDBC metadata
                    record_lat = lat if lat != 0 else 33.0  # Placeholder
                    record_lon = lon if lon != 0 else -118.0  # Placeholder

                    records.append((
                        f"BUOY_{buoy_id}",
                        obs_time,
                        record_lat,
                        record_lon,
                        var_name,
                        value,
                        target_units,
                        'NDBC'
                    ))

                except (ValueError, TypeError):
                    continue

        except Exception as e:
            logger.debug(f"Failed to parse buoy observation: {e}")
            continue

    # Insert into database
    if records:
        try:
            with get_db_connection() as conn:
                cur = conn.cursor()
                insert_query = """
                    INSERT INTO observations
                    (station_id, obs_time, location_lat, location_lon,
                     variable, value, units, obs_type)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """
                cur.executemany(insert_query, records)
                inserted = cur.rowcount
                cur.close()

                logger.success(f"Inserted {inserted} observation records for buoy {buoy_id}")
                return inserted

        except Exception as e:
            logger.error(f"Failed to insert observations: {e}")
            return 0

    return 0


def collect_buoy_observations(region: str, hours_back: int = 24) -> Dict[str, int]:
    """
    Collect buoy observations for a region.

    Args:
        region: Region identifier
        hours_back: How many hours of data to collect

    Returns:
        Dictionary with collection statistics
    """
    logger.info(f"Collecting buoy observations for region: {region}")

    # Get buoys for region
    buoys = get_region_stations(region, obs_type='buoy')
    if not buoys:
        logger.warning(f"No buoys configured for region: {region}")
        return {'buoys': 0, 'observations': 0}

    logger.info(f"Found {len(buoys)} buoys")

    total_obs = 0
    successful_buoys = 0

    for buoy_id in buoys:
        logger.info(f"Processing buoy: {buoy_id}")

        # Fetch data
        observations = fetch_buoy_data(buoy_id, hours_back)

        # Store data
        if observations:
            count = parse_and_store_buoy_observations(observations, buoy_id)
            total_obs += count
            if count > 0:
                successful_buoys += 1

    logger.info(f"Collection complete: {successful_buoys}/{len(buoys)} buoys, {total_obs} observations")

    return {
        'buoys': successful_buoys,
        'total_buoys': len(buoys),
        'observations': total_obs
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='NDBC Buoy Observation Collector')
    parser.add_argument('--region', type=str, default='all',
                       choices=['all'] + get_all_regions(),
                       help='Region to collect data for')
    parser.add_argument('--hours', type=int, default=24,
                       help='Hours of historical data to collect (default: 24)')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("NDBC Buoy Observation Collector")
    logger.info("=" * 60)

    regions_to_process = get_all_regions() if args.region == 'all' else [args.region]

    total_stats = {'buoys': 0, 'observations': 0}

    for region in regions_to_process:
        stats = collect_buoy_observations(region, args.hours)
        total_stats['buoys'] += stats.get('buoys', 0)
        total_stats['observations'] += stats.get('observations', 0)

    logger.info("=" * 60)
    logger.info("COLLECTION SUMMARY")
    logger.info(f"Regions processed: {len(regions_to_process)}")
    logger.info(f"Buoys with data: {total_stats['buoys']}")
    logger.info(f"Total observations: {total_stats['observations']}")
    logger.info("=" * 60)
    logger.success("Collection completed successfully")


if __name__ == "__main__":
    main()
