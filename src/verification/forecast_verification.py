"""
Forecast Verification System

Matches forecasts to observations and calculates BOTH:
1. Statistical metrics (MAE, RMSE, Bias) - for model diagnosis
2. Decision metrics (CSI, Hit Rate, FAR) - for operational value

Key Principle: A forecast's value is measured by the decisions it enables,
not just its statistical accuracy.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from math import radians, sin, cos, sqrt, atan2
import pandas as pd
import numpy as np
from loguru import logger

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.database import get_db_connection
from src.config import settings


# Operational thresholds for decision metrics
TEMPERATURE_THRESHOLDS = {
    'temperature_2m': [0.0, -5.0, 10.0, 35.0],  # Celsius: freezing, severe frost, comfort, heat
}

WIND_THRESHOLDS = {
    'wind_speed_10m': [12.86, 17.49, 24.69, 32.92],  # m/s: small craft, gale, storm, hurricane
}

PRESSURE_THRESHOLDS = {
    'mslp': [100000.0, 102000.0],  # Pa: low pressure indicators
}

# Variable mapping and conversion
VARIABLE_MAPPINGS = {
    'temperature_2m': {
        'obs_names': ['temperature_2m', 'air_temperature', 'air_temperature_2m'],
        'model_units': 'K',
        'target_units': 'K',
        'conversion': lambda x: x,  # Both in Kelvin already
        'default_thresholds': [273.15, 268.15, 283.15, 308.15],  # Kelvin
    },
    'dewpoint_2m': {
        'obs_names': ['dewpoint_2m', 'dewpoint'],
        'model_units': 'K',
        'target_units': 'K',
        'conversion': lambda x: x,
        'default_thresholds': [273.15],
    },
    'wind_speed_10m': {
        'obs_names': ['wind_speed_10m', 'wind_speed'],
        'model_units': 'm/s',
        'target_units': 'm/s',
        'conversion': lambda x: x,
        'default_thresholds': [12.86, 17.49, 24.69],  # m/s
    },
    'mslp': {
        'obs_names': ['mslp', 'pressure', 'sea_level_pressure'],
        'model_units': 'Pa',
        'target_units': 'Pa',
        'conversion': lambda x: x,
        'default_thresholds': [100000.0],  # Pa
    },
}

# Reasonable ranges for QC
REASONABLE_RANGES = {
    'temperature_2m': (213.15, 333.15),  # -60°C to 60°C in Kelvin
    'wind_speed_10m': (0, 77.2),  # 0 to 150 knots in m/s
    'mslp': (90000, 110000),  # 900-1100 hPa in Pa
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great circle distance between two points in kilometers.

    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth radius in km

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c


def quality_check_observation(obs_value: float, variable: str) -> bool:
    """
    Basic QC checks for observations.

    Args:
        obs_value: Observed value
        variable: Variable name

    Returns:
        True if observation passes QC, False otherwise
    """
    # Check for missing value indicators
    if obs_value is None or np.isnan(obs_value) or obs_value == 999.9 or obs_value == -999.9:
        return False

    # Check physically reasonable range
    if variable in REASONABLE_RANGES:
        min_val, max_val = REASONABLE_RANGES[variable]
        if not (min_val <= obs_value <= max_val):
            logger.warning(f"Value {obs_value} for {variable} outside reasonable range {REASONABLE_RANGES[variable]}")
            return False

    return True


def calculate_statistical_metrics(forecast_value: float, observed_value: float) -> Dict[str, float]:
    """
    Calculate traditional statistical verification metrics.

    Returns:
        Dictionary with error, absolute_error, squared_error
    """
    error = forecast_value - observed_value
    return {
        'error': error,
        'absolute_error': abs(error),
        'squared_error': error ** 2,
    }


def calculate_threshold_metrics(forecast_value: float, observed_value: float,
                                thresholds: List[float], operator: str = '>') -> Dict[float, Dict]:
    """
    Calculate decision-relevant metrics for operational thresholds.

    Args:
        forecast_value: Model forecast
        observed_value: Observed value
        thresholds: List of decision thresholds
        operator: Comparison operator ('>', '<', '>=', '<=')

    Returns:
        Dictionary keyed by threshold with contingency table results
    """
    results = {}

    for threshold in thresholds:
        if operator == '>':
            forecast_exceeds = forecast_value > threshold
            observed_exceeds = observed_value > threshold
        elif operator == '>=':
            forecast_exceeds = forecast_value >= threshold
            observed_exceeds = observed_value >= threshold
        elif operator == '<':
            forecast_exceeds = forecast_value < threshold
            observed_exceeds = observed_value < threshold
        else:  # '<='
            forecast_exceeds = forecast_value <= threshold
            observed_exceeds = observed_value <= threshold

        # Determine outcome
        if forecast_exceeds and observed_exceeds:
            outcome = 'hit'
        elif not forecast_exceeds and observed_exceeds:
            outcome = 'miss'  # WORST - didn't warn when should have
        elif forecast_exceeds and not observed_exceeds:
            outcome = 'false_alarm'  # COSTLY - unnecessary action
        else:
            outcome = 'correct_negative'

        results[threshold] = {
            'outcome': outcome,
            'forecast_exceeds': forecast_exceeds,
            'observed_exceeds': observed_exceeds,
            'operator': operator
        }

    return results


def calculate_decision_scores(contingency_counts: Dict[str, int]) -> Dict[str, float]:
    """
    Calculate aggregate decision quality metrics from contingency table.

    Args:
        contingency_counts: {'hits': int, 'misses': int, 'false_alarms': int, 'correct_negatives': int}

    Returns:
        Dictionary with decision metrics (hit_rate, FAR, CSI, etc.)
    """
    hits = contingency_counts.get('hits', 0)
    misses = contingency_counts.get('misses', 0)
    false_alarms = contingency_counts.get('false_alarms', 0)
    correct_negatives = contingency_counts.get('correct_negatives', 0)
    total = hits + misses + false_alarms + correct_negatives

    # Avoid division by zero
    hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0.0
    false_alarm_rate = false_alarms / (false_alarms + correct_negatives) if (false_alarms + correct_negatives) > 0 else 0.0
    false_alarm_ratio = false_alarms / (false_alarms + hits) if (false_alarms + hits) > 0 else 0.0
    accuracy = (hits + correct_negatives) / total if total > 0 else 0.0
    csi = hits / (hits + misses + false_alarms) if (hits + misses + false_alarms) > 0 else 0.0
    bias_score = (hits + false_alarms) / (hits + misses) if (hits + misses) > 0 else 0.0

    return {
        'hit_rate': hit_rate,  # POD - Probability of Detection
        'false_alarm_rate': false_alarm_rate,
        'false_alarm_ratio': false_alarm_ratio,
        'accuracy': accuracy,
        'csi': csi,  # Critical Success Index - KEY METRIC
        'bias_score': bias_score,
        'hits': hits,
        'misses': misses,
        'false_alarms': false_alarms,
        'correct_negatives': correct_negatives,
        'total': total
    }


class ForecastVerifier:
    """
    Main verification engine that matches forecasts to observations
    and calculates both statistical and decision-relevant metrics.
    """

    def __init__(self, spatial_threshold_km: float = 50.0,
                 temporal_threshold_hours: float = 1.0):
        """
        Args:
            spatial_threshold_km: Maximum distance for forecast-obs matching
            temporal_threshold_hours: Maximum time difference for matching
        """
        self.spatial_threshold_km = spatial_threshold_km
        self.temporal_threshold_hours = temporal_threshold_hours
        logger.info(f"ForecastVerifier initialized: spatial={spatial_threshold_km}km, temporal={temporal_threshold_hours}h")

    def find_nearest_forecast(self, obs_lat: float, obs_lon: float, obs_time: datetime,
                             variable: str, model_name: str) -> Optional[Dict]:
        """
        Find nearest forecast point to observation location and time.

        Args:
            obs_lat: Observation latitude
            obs_lon: Observation longitude
            obs_time: Observation time
            variable: Variable name
            model_name: Model to search

        Returns:
            Dictionary with forecast data or None if no match
        """
        try:
            # Time window
            time_min = obs_time - timedelta(hours=self.temporal_threshold_hours)
            time_max = obs_time + timedelta(hours=self.temporal_threshold_hours)

            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Query forecasts near observation
                    query = """
                        SELECT
                            id, value, location_lat, location_lon,
                            valid_time, init_time, lead_time_hours
                        FROM model_forecasts
                        WHERE model_name = %s
                          AND variable = %s
                          AND valid_time BETWEEN %s AND %s
                        ORDER BY valid_time
                    """

                    cur.execute(query, (model_name, variable, time_min, time_max))
                    forecasts = cur.fetchall()

                    if not forecasts:
                        return None

                    # Find nearest by distance
                    best_match = None
                    best_distance = float('inf')

                    for fc_id, value, fc_lat, fc_lon, valid_time, init_time, lead_time in forecasts:
                        distance = haversine_distance(obs_lat, obs_lon, fc_lat, fc_lon)

                        if distance <= self.spatial_threshold_km and distance < best_distance:
                            time_diff = abs((obs_time - valid_time).total_seconds() / 3600.0)
                            best_distance = distance
                            best_match = {
                                'id': fc_id,
                                'value': value,
                                'lat': fc_lat,
                                'lon': fc_lon,
                                'obs_lat': obs_lat,
                                'obs_lon': obs_lon,
                                'valid_time': valid_time,
                                'init_time': init_time,
                                'lead_time_hours': lead_time,
                                'distance_km': distance,
                                'time_diff_hours': time_diff
                            }

                    return best_match

        except Exception as e:
            logger.error(f"Error finding nearest forecast: {e}")
            return None

    def verify_forecasts(self, model_name: str, start_time: datetime, end_time: datetime,
                        variable: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Verify all forecasts for a model within a time range.

        Args:
            model_name: Model to verify
            start_time: Start of verification period
            end_time: End of verification period
            variable: Specific variable (None = all)
            dry_run: If True, don't store results

        Returns:
            Verification statistics
        """
        logger.info(f"Starting verification for {model_name}: {start_time} to {end_time}")

        # Query observations
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT
                        id, station_id, obs_time, location_lat, location_lon,
                        variable, value, units, obs_type
                    FROM observations
                    WHERE obs_time BETWEEN %s AND %s
                """
                params = [start_time, end_time]

                if variable:
                    query += " AND variable = %s"
                    params.append(variable)

                query += " ORDER BY obs_time"

                cur.execute(query, params)
                observations = cur.fetchall()

        logger.info(f"Found {len(observations)} observations to verify")

        pairs_verified = 0
        stats_by_variable = {}
        threshold_stats = {}

        for obs in observations:
            obs_id, station_id, obs_time, obs_lat, obs_lon, obs_var, obs_value, obs_units, obs_type = obs

            # QC check
            if not quality_check_observation(obs_value, obs_var):
                continue

            # Find matching forecast
            forecast = self.find_nearest_forecast(obs_lat, obs_lon, obs_time, obs_var, model_name)

            if not forecast:
                continue

            # Calculate statistical metrics
            stat_metrics = calculate_statistical_metrics(forecast['value'], obs_value)

            # Get thresholds for this variable
            var_config = VARIABLE_MAPPINGS.get(obs_var, {})
            thresholds = var_config.get('default_thresholds', [])

            # Calculate threshold metrics
            threshold_results = calculate_threshold_metrics(
                forecast['value'], obs_value, thresholds
            ) if thresholds else {}

            # Store results
            if not dry_run:
                verification_id = self._store_verification_result(
                    model_name, obs_var, forecast, obs_value,
                    stat_metrics, threshold_results
                )

            # Aggregate stats
            if obs_var not in stats_by_variable:
                stats_by_variable[obs_var] = {
                    'errors': [],
                    'absolute_errors': [],
                    'squared_errors': [],
                    'pairs': 0
                }

            stats_by_variable[obs_var]['errors'].append(stat_metrics['error'])
            stats_by_variable[obs_var]['absolute_errors'].append(stat_metrics['absolute_error'])
            stats_by_variable[obs_var]['squared_errors'].append(stat_metrics['squared_error'])
            stats_by_variable[obs_var]['pairs'] += 1

            # Aggregate threshold stats
            for threshold, result in threshold_results.items():
                key = (obs_var, threshold)
                if key not in threshold_stats:
                    threshold_stats[key] = {'hits': 0, 'misses': 0, 'false_alarms': 0, 'correct_negatives': 0}
                threshold_stats[key][result['outcome'] + 's'] = threshold_stats[key].get(result['outcome'] + 's', 0) + 1

            pairs_verified += 1

        # Calculate summary statistics
        summary = self._calculate_summary(stats_by_variable, threshold_stats)
        summary['pairs_verified'] = pairs_verified

        logger.success(f"Verified {pairs_verified} forecast-observation pairs for {model_name}")

        return summary

    def _store_verification_result(self, model_name: str, variable: str, forecast: Dict,
                                   obs_value: float, stat_metrics: Dict,
                                   threshold_results: Dict) -> int:
        """Store verification result in database."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    # Insert verification_scores
                    insert_query = """
                        INSERT INTO verification_scores
                        (model_name, variable, valid_time, lead_time_hours,
                         location_lat, location_lon,
                         forecast_value, observed_value,
                         forecast_lat, forecast_lon, distance_km, time_diff_hours,
                         error, absolute_error, squared_error,
                         forecast_init_time, forecast_valid_time)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """

                    cur.execute(insert_query, (
                        model_name, variable,
                        forecast['valid_time'], forecast['lead_time_hours'],
                        forecast['obs_lat'], forecast['obs_lon'],
                        forecast['value'], obs_value,
                        forecast['lat'], forecast['lon'],
                        forecast['distance_km'], forecast['time_diff_hours'],
                        stat_metrics['error'], stat_metrics['absolute_error'], stat_metrics['squared_error'],
                        forecast['init_time'], forecast['valid_time']
                    ))

                    verification_id = cur.fetchone()[0]

                    # Insert threshold_verification results
                    if threshold_results:
                        threshold_insert = """
                            INSERT INTO threshold_verification
                            (verification_score_id, threshold_value, threshold_operator,
                             forecast_exceeds, observed_exceeds, outcome)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """

                        threshold_data = [
                            (verification_id, threshold, result['operator'],
                             result['forecast_exceeds'], result['observed_exceeds'], result['outcome'])
                            for threshold, result in threshold_results.items()
                        ]

                        cur.executemany(threshold_insert, threshold_data)

                    conn.commit()
                    return verification_id

        except Exception as e:
            logger.error(f"Failed to store verification result: {e}")
            return -1

    def _calculate_summary(self, stats_by_variable: Dict, threshold_stats: Dict) -> Dict:
        """Calculate summary statistics."""
        summary = {
            'statistical_summary': {},
            'decision_summary': {}
        }

        # Statistical summary
        for var, stats in stats_by_variable.items():
            summary['statistical_summary'][var] = {
                'mae': np.mean(stats['absolute_errors']),
                'rmse': np.sqrt(np.mean(stats['squared_errors'])),
                'bias': np.mean(stats['errors']),
                'pairs': stats['pairs']
            }

        # Decision summary
        for (var, threshold), counts in threshold_stats.items():
            key = f"{var}_threshold_{threshold}"
            summary['decision_summary'][key] = calculate_decision_scores(counts)

        return summary

    def aggregate_skill_metrics(self, model_name: str, lookback_days: int = 30,
                                by_threshold: bool = True) -> pd.DataFrame:
        """
        Aggregate verification scores into conditional skill metrics.

        Args:
            model_name: Model to aggregate
            lookback_days: Days to look back
            by_threshold: Include threshold breakdowns

        Returns:
            DataFrame with aggregated metrics
        """
        try:
            with get_db_connection() as conn:
                # Refresh materialized view
                with conn.cursor() as cur:
                    cur.execute("REFRESH MATERIALIZED VIEW skill_metrics_summary")
                    conn.commit()

                # Query aggregated metrics
                query = """
                    SELECT * FROM skill_metrics_summary
                    WHERE model_name = %s
                      AND verification_date >= NOW() - INTERVAL '%s days'
                    ORDER BY verification_date DESC, variable, lead_time_hours
                """

                df = pd.read_sql_query(query, conn, params=(model_name, lookback_days))
                return df

        except Exception as e:
            logger.error(f"Failed to aggregate skill metrics: {e}")
            return pd.DataFrame()
