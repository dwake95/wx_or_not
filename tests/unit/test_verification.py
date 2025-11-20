"""
Unit tests for forecast verification system.

Tests cover:
- Haversine distance calculations
- Quality control checks
- Statistical metrics (MAE, RMSE, Bias)
- Decision metrics (CSI, Hit Rate, FAR)
- Threshold calculations
"""
import pytest
import numpy as np
from datetime import datetime, timedelta, timezone

# Import verification functions
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.verification.forecast_verification import (
    haversine_distance,
    quality_check_observation,
    calculate_statistical_metrics,
    calculate_threshold_metrics,
    calculate_decision_scores,
)


class TestHaversineDistance:
    """Test great circle distance calculations."""

    def test_same_point(self):
        """Distance from point to itself should be zero."""
        distance = haversine_distance(34.0, -118.0, 34.0, -118.0)
        assert distance == pytest.approx(0.0, abs=0.01)

    def test_known_distance(self):
        """Test against known distance: LAX to JFK ~3983 km."""
        # LAX: 33.9425° N, 118.4081° W
        # JFK: 40.6413° N, 73.7781° W
        distance = haversine_distance(33.9425, -118.4081, 40.6413, -73.7781)
        assert distance == pytest.approx(3983, rel=0.05)  # Within 5%

    def test_equator_distance(self):
        """1 degree longitude at equator ≈ 111.32 km."""
        distance = haversine_distance(0.0, 0.0, 0.0, 1.0)
        assert distance == pytest.approx(111.32, rel=0.01)

    def test_hemisphere_change(self):
        """Distance across hemisphere."""
        distance = haversine_distance(-34.0, 151.0, 34.0, -118.0)  # Sydney to LA
        assert distance > 10000  # Should be over 10,000 km

    def test_within_verification_threshold(self):
        """Points within 50km should be close enough for verification."""
        # ~30 km apart (roughly 0.27° at 34°N latitude)
        distance = haversine_distance(34.0, -118.0, 34.27, -118.0)
        assert distance < 50.0


class TestQualityCheck:
    """Test observation quality control."""

    def test_valid_temperature(self):
        """Valid temperature should pass QC."""
        assert quality_check_observation(288.15, 'temperature_2m') is True  # 15°C

    def test_temperature_too_cold(self):
        """Unreasonably cold temperature should fail QC."""
        assert quality_check_observation(200.0, 'temperature_2m') is False  # -73°C

    def test_temperature_too_hot(self):
        """Unreasonably hot temperature should fail QC."""
        assert quality_check_observation(350.0, 'temperature_2m') is False  # 77°C

    def test_missing_value_none(self):
        """None value should fail QC."""
        assert quality_check_observation(None, 'temperature_2m') is False

    def test_missing_value_nan(self):
        """NaN value should fail QC."""
        assert quality_check_observation(np.nan, 'temperature_2m') is False

    def test_missing_value_999(self):
        """Missing value indicator 999.9 should fail QC."""
        assert quality_check_observation(999.9, 'temperature_2m') is False

    def test_valid_mslp(self):
        """Valid MSLP should pass QC."""
        assert quality_check_observation(101300.0, 'mslp') is True  # 1013 hPa

    def test_mslp_too_low(self):
        """Unreasonably low pressure should fail QC."""
        assert quality_check_observation(85000.0, 'mslp') is False  # 850 hPa

    def test_mslp_too_high(self):
        """Unreasonably high pressure should fail QC."""
        assert quality_check_observation(115000.0, 'mslp') is False  # 1150 hPa

    def test_valid_wind_speed(self):
        """Valid wind speed should pass QC."""
        assert quality_check_observation(10.0, 'wind_speed_10m') is True  # 10 m/s

    def test_negative_wind_speed(self):
        """Negative wind speed should fail QC."""
        assert quality_check_observation(-5.0, 'wind_speed_10m') is False


class TestStatisticalMetrics:
    """Test traditional statistical verification metrics."""

    def test_perfect_forecast(self):
        """Perfect forecast should have zero error."""
        metrics = calculate_statistical_metrics(101300.0, 101300.0)
        assert metrics['error'] == 0.0
        assert metrics['absolute_error'] == 0.0
        assert metrics['squared_error'] == 0.0

    def test_positive_bias(self):
        """Forecast higher than observation (positive bias)."""
        metrics = calculate_statistical_metrics(101500.0, 101300.0)
        assert metrics['error'] == 200.0
        assert metrics['absolute_error'] == 200.0
        assert metrics['squared_error'] == 40000.0

    def test_negative_bias(self):
        """Forecast lower than observation (negative bias)."""
        metrics = calculate_statistical_metrics(101100.0, 101300.0)
        assert metrics['error'] == -200.0
        assert metrics['absolute_error'] == 200.0
        assert metrics['squared_error'] == 40000.0

    def test_large_error(self):
        """Large error should produce large squared error."""
        metrics = calculate_statistical_metrics(102000.0, 101000.0)
        assert metrics['error'] == 1000.0
        assert metrics['absolute_error'] == 1000.0
        assert metrics['squared_error'] == 1000000.0


class TestThresholdMetrics:
    """Test threshold-based decision metrics."""

    def test_hit(self):
        """Both forecast and observation exceed threshold = HIT."""
        result = calculate_threshold_metrics(
            forecast_value=101500.0,
            observed_value=101600.0,
            thresholds=[101000.0],
            operator='>'
        )
        assert result[101000.0]['outcome'] == 'hit'
        assert result[101000.0]['forecast_exceeds'] is True
        assert result[101000.0]['observed_exceeds'] is True

    def test_miss(self):
        """Forecast doesn't exceed but observation does = MISS (worst)."""
        result = calculate_threshold_metrics(
            forecast_value=100900.0,
            observed_value=101100.0,
            thresholds=[101000.0],
            operator='>'
        )
        assert result[101000.0]['outcome'] == 'miss'
        assert result[101000.0]['forecast_exceeds'] is False
        assert result[101000.0]['observed_exceeds'] is True

    def test_false_alarm(self):
        """Forecast exceeds but observation doesn't = FALSE ALARM (costly)."""
        result = calculate_threshold_metrics(
            forecast_value=101100.0,
            observed_value=100900.0,
            thresholds=[101000.0],
            operator='>'
        )
        assert result[101000.0]['outcome'] == 'false_alarm'
        assert result[101000.0]['forecast_exceeds'] is True
        assert result[101000.0]['observed_exceeds'] is False

    def test_correct_negative(self):
        """Neither exceeds threshold = CORRECT NEGATIVE."""
        result = calculate_threshold_metrics(
            forecast_value=100800.0,
            observed_value=100900.0,
            thresholds=[101000.0],
            operator='>'
        )
        assert result[101000.0]['outcome'] == 'correct_negative'
        assert result[101000.0]['forecast_exceeds'] is False
        assert result[101000.0]['observed_exceeds'] is False

    def test_multiple_thresholds(self):
        """Test with multiple thresholds."""
        result = calculate_threshold_metrics(
            forecast_value=101200.0,
            observed_value=101300.0,
            thresholds=[100000.0, 101000.0, 102000.0],
            operator='>'
        )
        # Should exceed first two thresholds but not third
        assert result[100000.0]['outcome'] == 'hit'
        assert result[101000.0]['outcome'] == 'hit'
        # Both forecast (101200) and observation (101300) are below 102000
        # So neither exceeds threshold = correct_negative
        assert result[102000.0]['outcome'] == 'correct_negative'

    def test_less_than_operator(self):
        """Test with less-than operator (e.g., low pressure)."""
        result = calculate_threshold_metrics(
            forecast_value=100500.0,
            observed_value=100400.0,
            thresholds=[101000.0],
            operator='<'
        )
        # Both are below threshold
        assert result[101000.0]['outcome'] == 'hit'
        assert result[101000.0]['forecast_exceeds'] is True
        assert result[101000.0]['observed_exceeds'] is True


class TestDecisionScores:
    """Test aggregate decision quality metrics (CSI, Hit Rate, FAR)."""

    def test_perfect_forecast_csi(self):
        """Perfect forecast (all hits) should have CSI=1.0."""
        counts = {
            'hits': 10,
            'misses': 0,
            'false_alarms': 0,
            'correct_negatives': 5
        }
        scores = calculate_decision_scores(counts)
        assert scores['csi'] == 1.0
        assert scores['hit_rate'] == 1.0  # Perfect detection
        assert scores['false_alarm_ratio'] == 0.0  # No false alarms

    def test_all_misses(self):
        """All misses should have CSI=0, hit_rate=0."""
        counts = {
            'hits': 0,
            'misses': 10,
            'false_alarms': 0,
            'correct_negatives': 5
        }
        scores = calculate_decision_scores(counts)
        assert scores['csi'] == 0.0
        assert scores['hit_rate'] == 0.0  # Caught nothing

    def test_mixed_performance(self):
        """Realistic mixed performance."""
        counts = {
            'hits': 7,
            'misses': 2,
            'false_alarms': 1,
            'correct_negatives': 10
        }
        scores = calculate_decision_scores(counts)

        # CSI = hits / (hits + misses + false_alarms) = 7 / 10 = 0.7
        assert scores['csi'] == pytest.approx(0.7, abs=0.01)

        # hit_rate = hits / (hits + misses) = 7 / 9 ≈ 0.778
        assert scores['hit_rate'] == pytest.approx(0.778, abs=0.01)

        # false_alarm_ratio = false_alarms / (hits + false_alarms) = 1 / 8 = 0.125
        assert scores['false_alarm_ratio'] == pytest.approx(0.125, abs=0.01)

    def test_high_false_alarm_rate(self):
        """High false alarm rate should lower CSI."""
        counts = {
            'hits': 5,
            'misses': 1,
            'false_alarms': 10,  # Many false alarms
            'correct_negatives': 4
        }
        scores = calculate_decision_scores(counts)

        # CSI = 5 / 16 = 0.3125
        assert scores['csi'] == pytest.approx(0.3125, abs=0.01)

        # false_alarm_ratio = 10 / 15 ≈ 0.667 (high)
        assert scores['false_alarm_ratio'] == pytest.approx(0.667, abs=0.01)

    def test_no_events(self):
        """No events (hits + misses = 0) should return 0 for hit_rate."""
        counts = {
            'hits': 0,
            'misses': 0,
            'false_alarms': 5,
            'correct_negatives': 10
        }
        scores = calculate_decision_scores(counts)

        # When no events occurred, hit_rate is 0 (per implementation)
        assert scores['hit_rate'] == 0.0

    def test_operational_acceptable_performance(self):
        """Test metrics for operationally acceptable performance.

        CSI ≥ 0.5 is generally acceptable
        hit_rate ≥ 0.8 is good for safety-critical decisions
        false_alarm_ratio ≤ 0.3 is acceptable
        """
        counts = {
            'hits': 80,
            'misses': 15,
            'false_alarms': 25,
            'correct_negatives': 100
        }
        scores = calculate_decision_scores(counts)

        # CSI = 80 / 120 ≈ 0.667 (good)
        assert scores['csi'] > 0.5

        # hit_rate = 80 / 95 ≈ 0.842 (good for safety)
        assert scores['hit_rate'] > 0.8

        # false_alarm_ratio = 25 / 105 ≈ 0.238 (acceptable)
        assert scores['false_alarm_ratio'] < 0.3


class TestIntegrationScenarios:
    """Integration tests for realistic verification scenarios."""

    def test_cold_front_passage(self):
        """Test verification of cold front with temperature drop."""
        # Forecast: Temperature drops below freezing (273.15 K)
        forecast_temp = 271.0  # -2°C
        observed_temp = 272.5  # -0.5°C

        # Both below freezing threshold
        threshold_result = calculate_threshold_metrics(
            forecast_temp, observed_temp,
            thresholds=[273.15],
            operator='<'
        )

        # Should be a HIT (both correctly below threshold)
        assert threshold_result[273.15]['outcome'] == 'hit'

        # Statistical metrics
        stats = calculate_statistical_metrics(forecast_temp, observed_temp)
        assert stats['absolute_error'] == pytest.approx(1.5, abs=0.1)

    def test_low_pressure_system(self):
        """Test verification of low pressure system approach."""
        forecast_mslp = 99800.0  # 998 hPa
        observed_mslp = 100200.0  # 1002 hPa

        # Both below 1010 hPa threshold (low pressure)
        threshold_result = calculate_threshold_metrics(
            forecast_mslp, observed_mslp,
            thresholds=[101000.0],
            operator='<'
        )

        # Should be a HIT
        assert threshold_result[101000.0]['outcome'] == 'hit'

        # Error magnitude
        stats = calculate_statistical_metrics(forecast_mslp, observed_mslp)
        assert stats['absolute_error'] == 400.0

    def test_gale_warning_verification(self):
        """Test verification of gale force wind warning (34 kt threshold)."""
        # 34 knots ≈ 17.49 m/s
        gale_threshold = 17.49

        # Forecast warned of gale, observed gale occurred
        forecast_wind = 18.5
        observed_wind = 19.2

        threshold_result = calculate_threshold_metrics(
            forecast_wind, observed_wind,
            thresholds=[gale_threshold],
            operator='>'
        )

        # Should be a HIT (both exceed gale threshold)
        assert threshold_result[gale_threshold]['outcome'] == 'hit'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
