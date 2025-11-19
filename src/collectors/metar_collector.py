#!/usr/bin/env python3
"""METAR observation data collector for weather model verification."""
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


# METAR data source - Iowa State ASOS/AWOS network
METAR_BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"


def fetch_metar_data(station_id: str, start_time: datetime, end_time: datetime) -> List[Dict]:
    """
    Fetch METAR observations from Iowa State Mesonet.

    Args:
        station_id: 4-letter ICAO station identifier (e.g., 'KSAN')
        start_time: Start of observation period
        end_time: End of observation period

    Returns:
        List of observation dictionaries
    """
    try:
        # Format times for API
        start_str = start_time.strftime('%Y-%m-%d %H:%M')
        end_str = end_time.strftime('%Y-%m-%d %H:%M')

        params = {
            'station': station_id,
            'data': 'all',  # Get all available data
            'year1': start_time.year,
            'month1': start_time.month,
            'day1': start_time.day,
            'hour1': start_time.hour,
            'minute1': start_time.minute,
            'year2': end_time.year,
            'month2': end_time.month,
            'day2': end_time.day,
            'hour2': end_time.hour,
            'minute2': end_time.minute,
            'tz': 'Etc/UTC',
            'format': 'onlycomma',  # CSV format
            'latlon': 'yes',
            'elev': 'yes',
            'missing': 'null',
            'trace': 'null',
            'direct': 'no',
            'report_type': [3],  # Routine observations
        }

        logger.debug(f"Fetching METAR data for {station_id}: {start_str} to {end_str}")

        response = requests.get(METAR_BASE_URL, params=params, timeout=30)
        response.raise_for_status()

        # Parse CSV response
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            logger.warning(f"No data returned for {station_id}")
            return []

        # First line is header
        headers = lines[0].split(',')

        observations = []
        for line in lines[1:]:
            if not line.strip():
                continue

            values = line.split(',')
            if len(values) != len(headers):
                continue

            # Create observation dict
            obs = dict(zip(headers, values))

            # Skip if missing critical data
            if obs.get('valid') == 'null' or obs.get('valid') == '':
                continue

            observations.append(obs)

        logger.info(f"Fetched {len(observations)} observations for {station_id}")
        return observations

    except Exception as e:
        logger.error(f"Failed to fetch METAR data for {station_id}: {e}")
        return []


def parse_and_store_observations(observations: List[Dict], station_id: str) -> int:
    """
    Parse METAR observations and store in database.

    Args:
        observations: List of observation dictionaries
        station_id: Station identifier

    Returns:
        Number of records inserted
    """
    if not observations:
        return 0

    records = []

    for obs in observations:
        try:
            # Parse observation time
            valid_str = obs.get('valid', '').strip()
            if not valid_str or valid_str == 'null':
                continue

            obs_time = datetime.strptime(valid_str, '%Y-%m-%d %H:%M')
            obs_time = obs_time.replace(tzinfo=timezone.utc)

            # Get location
            try:
                lat = float(obs.get('lat', 0))
                lon = float(obs.get('lon', 0))
            except (ValueError, TypeError):
                continue

            if lat == 0 and lon == 0:
                continue

            # Extract meteorological variables
            variables = {
                'temperature_2m': ('tmpf', 'degF'),  # Temperature in Fahrenheit
                'dewpoint_2m': ('dwpf', 'degF'),  # Dewpoint in Fahrenheit
                'wind_speed_10m': ('sknt', 'knots'),  # Wind speed in knots
                'wind_direction_10m': ('drct', 'degrees'),  # Wind direction
                'wind_gust_10m': ('gust', 'knots'),  # Wind gust
                'mslp': ('mslp', 'mb'),  # Mean sea level pressure in mb
                'altimeter': ('alti', 'inHg'),  # Altimeter setting
                'visibility': ('vsby', 'miles'),  # Visibility in miles
                'precipitation_1hr': ('p01i', 'inches'),  # 1-hour precipitation
            }

            for var_name, (field, units) in variables.items():
                value_str = obs.get(field, 'null')
                if value_str == 'null' or value_str == '' or value_str == 'M':
                    continue

                try:
                    value = float(value_str)

                    # Convert to metric where appropriate
                    if units == 'degF':
                        # Convert F to Kelvin
                        value = (value - 32) * 5/9 + 273.15
                        units = 'K'
                    elif units == 'knots':
                        # Convert knots to m/s
                        value = value * 0.514444
                        units = 'm/s'
                    elif units == 'mb':
                        # Convert mb to Pa
                        value = value * 100
                        units = 'Pa'
                    elif units == 'inHg':
                        # Convert inHg to Pa
                        value = value * 3386.39
                        units = 'Pa'
                    elif units == 'miles':
                        # Convert miles to meters
                        value = value * 1609.34
                        units = 'm'
                    elif units == 'inches':
                        # Convert inches to mm
                        value = value * 25.4
                        units = 'mm'

                    records.append((
                        station_id,
                        obs_time,
                        lat,
                        lon,
                        var_name,
                        value,
                        units,
                        'METAR'
                    ))

                except (ValueError, TypeError):
                    continue

        except Exception as e:
            logger.debug(f"Failed to parse observation: {e}")
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

                logger.success(f"Inserted {inserted} observation records for {station_id}")
                return inserted

        except Exception as e:
            logger.error(f"Failed to insert observations: {e}")
            return 0

    return 0


def collect_metar_observations(region: str, hours_back: int = 24) -> Dict[str, int]:
    """
    Collect METAR observations for a region.

    Args:
        region: Region identifier
        hours_back: How many hours of data to collect

    Returns:
        Dictionary with collection statistics
    """
    logger.info(f"Collecting METAR observations for region: {region}")

    # Get stations for region
    stations = get_region_stations(region, obs_type='metar')
    if not stations:
        logger.warning(f"No METAR stations configured for region: {region}")
        return {'stations': 0, 'observations': 0}

    logger.info(f"Found {len(stations)} METAR stations")

    # Time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours_back)

    total_obs = 0
    successful_stations = 0

    for station_id in stations:
        logger.info(f"Processing station: {station_id}")

        # Fetch data
        observations = fetch_metar_data(station_id, start_time, end_time)

        # Store data
        if observations:
            count = parse_and_store_observations(observations, station_id)
            total_obs += count
            if count > 0:
                successful_stations += 1

    logger.info(f"Collection complete: {successful_stations}/{len(stations)} stations, {total_obs} observations")

    return {
        'stations': successful_stations,
        'total_stations': len(stations),
        'observations': total_obs
    }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='METAR Observation Collector')
    parser.add_argument('--region', type=str, default='all',
                       choices=['all'] + get_all_regions(),
                       help='Region to collect data for')
    parser.add_argument('--hours', type=int, default=24,
                       help='Hours of historical data to collect (default: 24)')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("METAR Observation Collector")
    logger.info("=" * 60)

    regions_to_process = get_all_regions() if args.region == 'all' else [args.region]

    total_stats = {'stations': 0, 'observations': 0}

    for region in regions_to_process:
        stats = collect_metar_observations(region, args.hours)
        total_stats['stations'] += stats.get('stations', 0)
        total_stats['observations'] += stats.get('observations', 0)

    logger.info("=" * 60)
    logger.info("COLLECTION SUMMARY")
    logger.info(f"Regions processed: {len(regions_to_process)}")
    logger.info(f"Stations with data: {total_stats['stations']}")
    logger.info(f"Total observations: {total_stats['observations']}")
    logger.info("=" * 60)
    logger.success("Collection completed successfully")


if __name__ == "__main__":
    main()
