# Task 8: Forecast Verification System

Create `src/verification/forecast_verification.py` that matches forecasts to observations and calculates **forecast quality** metrics focused on decision-making utility.

## Forecast Quality vs Model Quality

### Critical Distinction

**Model Quality (Traditional Metrics):**
- MAE, RMSE, correlation - statistical accuracy
- "How close is the forecast to the observation?"
- Treats all errors equally

**Forecast Quality (Decision-Relevant Metrics):**
- Threshold accuracy, hit rate, false alarm rate
- "Does this forecast lead to better decisions?"
- Weighs errors by their operational impact

### Why This Matters

A forecast with MAE=3°F that correctly predicts whether temperature will exceed 32°F (ice/no ice) is MORE VALUABLE than a forecast with MAE=2°F that gets the threshold crossing wrong.

**Example:**
- Forecast A: Predicts 35°F, actual is 31°F (error = 4°F, but wrong side of freezing)
- Forecast B: Predicts 33°F, actual is 31°F (error = 2°F, both below freezing)

Traditional metrics say A is worse (larger error). But for road treatment decisions, B is actually worse because you still need to treat the road either way - the forecast didn't help the decision.

### Our Approach

We calculate BOTH types of metrics:
1. **Statistical metrics** (MAE, RMSE, bias) - for model diagnosis and comparison
2. **Decision metrics** (threshold accuracy, hit rate, CSI) - for operational value assessment

The decision metrics should be weighted MORE HEAVILY when selecting which model to use for a given forecast.

---

## 1. Core Verification Engine

```python
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
```

## 2. Spatial Matching

```python
def find_nearest_forecast(obs_lat: float, obs_lon: float, 
                         obs_time: datetime, variable: str,
                         model_name: str) -> Optional[Dict]:
    """
    Find nearest forecast point to observation location and time.
    
    Uses haversine distance for spatial matching.
    
    Returns:
        Dictionary with forecast value, distance_km, time_diff_hours
        or None if no match within thresholds
    """
```

## 3. Statistical Verification Metrics

**Purpose:** Diagnose model performance and systematic errors

```python
def calculate_statistical_metrics(forecast_value: float, 
                                  observed_value: float) -> Dict[str, float]:
    """
    Calculate traditional statistical verification metrics.
    
    Returns:
        {
            'error': forecast - observed,           # Bias detection
            'absolute_error': abs(forecast - observed),  # Average magnitude
            'squared_error': (forecast - observed) ** 2,  # Penalize large errors
        }
    """
```

### Why These Matter:

- **Error (Bias):** Systematic over/under-prediction. If bias is consistent, we can correct it.
- **Absolute Error:** Average miss distance. Useful for comparing models.
- **Squared Error:** Penalizes large misses more than small ones. Important for safety-critical applications.

## 4. Decision-Relevant Metrics

**Purpose:** Measure operational forecast value

```python
def calculate_threshold_metrics(forecast_value: float,
                               observed_value: float,
                               thresholds: List[float]) -> Dict[str, Dict]:
    """
    Calculate decision-relevant metrics for operational thresholds.
    
    For each threshold, determines:
    - Hit: Forecast and obs both exceed threshold
    - Miss: Obs exceeds but forecast doesn't (DANGEROUS - failed to warn)
    - False Alarm: Forecast exceeds but obs doesn't (COSTLY - unnecessary action)
    - Correct Negative: Both below threshold
    
    Args:
        forecast_value: Model forecast
        observed_value: Observed value
        thresholds: List of decision thresholds (e.g., [32.0] for freezing)
    
    Returns:
        Dictionary keyed by threshold with contingency table results
    """
    results = {}
    
    for threshold in thresholds:
        forecast_exceeds = forecast_value > threshold
        observed_exceeds = observed_value > threshold
        
        # Contingency table
        if forecast_exceeds and observed_exceeds:
            outcome = 'hit'
        elif not forecast_exceeds and observed_exceeds:
            outcome = 'miss'  # WORST CASE - didn't warn when should have
        elif forecast_exceeds and not observed_exceeds:
            outcome = 'false_alarm'  # COSTLY - took action unnecessarily
        else:
            outcome = 'correct_negative'
        
        results[threshold] = {
            'outcome': outcome,
            'forecast_exceeds': forecast_exceeds,
            'observed_exceeds': observed_exceeds
        }
    
    return results
```

### Common Operational Thresholds

```python
# Temperature thresholds (Celsius)
TEMPERATURE_THRESHOLDS = [
    0.0,   # Freezing - road treatment needed
    -5.0,  # Severe frost - increased treatment
    35.0,  # Heat stress begins
]

# Wind speed thresholds (knots)
WIND_THRESHOLDS = [
    25.0,  # Small craft advisory
    34.0,  # Gale warning
    48.0,  # Storm warning
    64.0,  # Hurricane force
]

# Pressure thresholds (hPa)
PRESSURE_THRESHOLDS = [
    1000.0,  # Low pressure system indicator
]
```

## 5. Aggregate Decision Metrics

```python
def calculate_decision_scores(contingency_counts: Dict) -> Dict[str, float]:
    """
    Calculate aggregate decision quality metrics from contingency table.
    
    Args:
        contingency_counts: {
            'hits': int,
            'misses': int,
            'false_alarms': int,
            'correct_negatives': int
        }
    
    Returns:
        {
            'hit_rate': hits / (hits + misses),  # POD - Probability of Detection
            'false_alarm_rate': false_alarms / (false_alarms + correct_negatives),
            'false_alarm_ratio': false_alarms / (false_alarms + hits),
            'accuracy': (hits + correct_negatives) / total,
            'csi': hits / (hits + misses + false_alarms),  # Critical Success Index
            'bias_score': (hits + false_alarms) / (hits + misses)  # Forecast frequency bias
        }
    """
    hits = contingency_counts['hits']
    misses = contingency_counts['misses']
    false_alarms = contingency_counts['false_alarms']
    correct_negatives = contingency_counts['correct_negatives']
    total = hits + misses + false_alarms + correct_negatives
    
    # Avoid division by zero
    hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 0.0
    false_alarm_rate = false_alarms / (false_alarms + correct_negatives) if (false_alarms + correct_negatives) > 0 else 0.0
    false_alarm_ratio = false_alarms / (false_alarms + hits) if (false_alarms + hits) > 0 else 0.0
    accuracy = (hits + correct_negatives) / total if total > 0 else 0.0
    csi = hits / (hits + misses + false_alarms) if (hits + misses + false_alarms) > 0 else 0.0
    bias_score = (hits + false_alarms) / (hits + misses) if (hits + misses) > 0 else 0.0
    
    return {
        'hit_rate': hit_rate,
        'false_alarm_rate': false_alarm_rate,
        'false_alarm_ratio': false_alarm_ratio,
        'accuracy': accuracy,
        'csi': csi,
        'bias_score': bias_score
    }
```

### Why These Metrics Matter:

**Hit Rate (Probability of Detection - POD):**
- "When the event happened, did we predict it?"
- Range: 0 to 1 (1 = perfect)
- Critical for safety - want HIGH hit rate for dangerous events
- A hit rate of 0.85 means "we warned about 85% of freezing events"

**False Alarm Rate:**
- "When the event didn't happen, how often did we incorrectly warn?"
- Range: 0 to 1 (0 = perfect)
- Important for operational efficiency - false alarms are expensive
- A FAR of 0.20 means "20% of non-events were incorrectly forecast"

**False Alarm Ratio:**
- "Of all our warnings, how many were false alarms?"
- Range: 0 to 1 (0 = perfect)
- Measures forecast credibility
- A FAR of 0.30 means "30% of our warnings were false"

**Critical Success Index (CSI):**
- Overall skill at forecasting events
- Range: 0 to 1 (1 = perfect)
- Penalizes both misses and false alarms
- **This is often the single best metric for operational value**
- A CSI of 0.70 is excellent for most weather phenomena

**Accuracy:**
- "Overall, how often were we right?"
- Can be misleading for rare events (base rate problem)
- Use CSI instead for most decisions

**Bias Score:**
- "Do we over-forecast or under-forecast events?"
- = 1: Unbiased
- &gt; 1: Over-forecasting (too many warnings)
- &lt; 1: Under-forecasting (missing events)

## 6. Economic Value Metrics (Future Enhancement)

```python
def calculate_economic_value(contingency_counts: Dict,
                            cost_false_alarm: float,
                            cost_miss: float,
                            base_rate: float) -> float:
    """
    Calculate economic value of forecast relative to climatology.
    
    Economic Value = (cost_avoided - cost_incurred) / max_possible_value
    
    This tells us: "How much money does this forecast save compared to 
    always/never taking action?"
    
    Args:
        contingency_counts: Hit/miss/FA/CN counts
        cost_false_alarm: Cost of taking action when not needed
        cost_miss: Cost of NOT taking action when needed
        base_rate: Climatological probability of event
    
    Returns:
        Economic value (0 = no better than climatology, 1 = perfect)
    """
    # Implementation in Phase 1
    pass
```

## 7. Bulk Verification with Both Metric Types

```python
def verify_forecasts(model_name: str, 
                    start_time: datetime,
                    end_time: datetime,
                    variable: Optional[str] = None,
                    thresholds: Optional[List[float]] = None) -> Dict[str, Any]:
    """
    Verify all forecasts for a model within a time range.
    
    Process:
    1. Query all observations in time range
    2. For each observation, find matching forecast
    3. Calculate BOTH statistical and decision metrics
    4. Store in verification_scores table (with threshold results)
    
    Args:
        model_name: Model to verify (e.g., 'GFS', 'NAM')
        start_time: Start of verification period
        end_time: End of verification period
        variable: Specific variable to verify (None = all variables)
        thresholds: Decision thresholds to evaluate (uses defaults if None)
    
    Returns:
        {
            'pairs_verified': int,
            'statistical_summary': {...},
            'decision_summary': {...}
        }
    """
```

## 8. Enhanced Verification Scores Table

The verification_scores table needs additional columns for decision metrics:

```sql
ALTER TABLE verification_scores
ADD COLUMN IF NOT EXISTS threshold_value FLOAT,
ADD COLUMN IF NOT EXISTS forecast_exceeds BOOLEAN,
ADD COLUMN IF NOT EXISTS observed_exceeds BOOLEAN,
ADD COLUMN IF NOT EXISTS threshold_outcome VARCHAR(20);
-- outcome is one of: 'hit', 'miss', 'false_alarm', 'correct_negative'
```

Or better yet, create a separate table for threshold verification:

```sql
CREATE TABLE threshold_verification (
    id SERIAL PRIMARY KEY,
    verification_score_id INTEGER REFERENCES verification_scores(id),
    threshold_value FLOAT NOT NULL,
    threshold_operator VARCHAR(10) NOT NULL,  -- '>', '<', '>=', '<='
    forecast_exceeds BOOLEAN NOT NULL,
    observed_exceeds BOOLEAN NOT NULL,
    outcome VARCHAR(20) NOT NULL,  -- 'hit', 'miss', 'false_alarm', 'correct_negative'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_threshold_outcome ON threshold_verification(outcome, threshold_value);
```

## 9. Variable Conversion

Handle unit conversions and variable name mappings:

```python
VARIABLE_MAPPINGS = {
    'temperature_2m': {
        'model_units': 'K',
        'obs_units': 'C',
        'conversion': lambda k: k - 273.15,  # Kelvin to Celsius
        'obs_names': ['temperature', 'temp', 'air_temperature'],
        'default_thresholds': [0.0, -5.0, 35.0]  # Celsius
    },
    'wind_speed': {
        'model_units': 'm/s',
        'obs_units': 'kt',
        'conversion': lambda ms: ms * 1.94384,  # m/s to knots
        'obs_names': ['wind_speed', 'wspd'],
        'default_thresholds': [25.0, 34.0, 48.0]  # knots
    },
    'mslp': {
        'model_units': 'Pa',
        'obs_units': 'hPa',
        'conversion': lambda pa: pa / 100.0,  # Pa to hPa
        'obs_names': ['pressure', 'mslp', 'sea_level_pressure'],
        'default_thresholds': [1000.0]  # hPa
    }
}

def convert_units(value: float, variable: str, 
                 from_units: str, to_units: str) -> float:
    """Convert between units for a variable."""
```

## 10. Conditional Skill Aggregation

```python
def aggregate_skill_metrics(model_name: str,
                           lookback_days: int = 30,
                           by_threshold: bool = True) -> pd.DataFrame:
    """
    Aggregate verification scores into conditional skill metrics.
    
    Groups by:
    - model_name
    - variable
    - lead_time_hours
    - region (based on location)
    - time_of_day (morning/afternoon/evening/night)
    - threshold (if by_threshold=True)
    
    Calculates for each group:
    
    STATISTICAL METRICS:
    - MAE (Mean Absolute Error)
    - RMSE (Root Mean Squared Error)
    - Bias (Mean Error)
    
    DECISION METRICS:
    - Hit Rate (POD)
    - False Alarm Rate
    - False Alarm Ratio
    - CSI (Critical Success Index) ← MOST IMPORTANT
    
    Returns:
        DataFrame with aggregated metrics
    """
```

## 11. Database Operations

```python
def store_verification_result(forecast_data: Dict, 
                             obs_data: Dict,
                             metrics: Dict,
                             threshold_results: Dict) -> bool:
    """
    Store verification result in database.
    
    Inserts into:
    1. verification_scores (statistical metrics)
    2. threshold_verification (decision metrics)
    """

def get_unverified_forecasts(model_name: str,
                            hours_back: int = 24) -> List[Dict]:
    """
    Find forecasts that haven't been verified yet.
    
    Looks for forecasts where:
    - valid_time has passed
    - No matching entry in verification_scores
    """
```

## 12. Quality Control

```python
def quality_check_observation(obs_value: float, 
                             variable: str,
                             station_id: str) -> bool:
    """
    Basic QC checks for observations.
    
    Checks:
    - Value within physically reasonable range
    - Not a missing value indicator (e.g., 999.9)
    - Not a statistical outlier (if historical data exists)
    
    Returns:
        True if observation passes QC, False otherwise
    """

REASONABLE_RANGES = {
    'temperature': (-60, 60),  # Celsius
    'wind_speed': (0, 150),     # knots
    'mslp': (900, 1100),        # hPa
}
```

## 13. Haversine Distance Function

```python
def haversine_distance(lat1: float, lon1: float,
                      lat2: float, lon2: float) -> float:
    """
    Calculate great circle distance between two points in kilometers.
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
    
    Returns:
        Distance in kilometers
    """
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth radius in km
    
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c
```

## 14. Command-Line Interface

Create `scripts/run_verification.py`:

```python
#!/usr/bin/env python3
"""Run forecast verification for specified models and time range."""
import argparse
from datetime import datetime, timedelta
from src.verification.forecast_verification import ForecastVerifier

def main():
    parser = argparse.ArgumentParser(description='Forecast Verification')
    parser.add_argument('--model', required=True,
                       help='Model name (GFS, NAM, etc.)')
    parser.add_argument('--hours-back', type=int, default=24,
                       help='Hours to look back for verification')
    parser.add_argument('--variable',
                       help='Specific variable to verify (default: all)')
    parser.add_argument('--spatial-threshold', type=float, default=50.0,
                       help='Max distance for matching (km)')
    parser.add_argument('--show-decision-metrics', action='store_true',
                       help='Display decision metrics summary')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be verified without storing results')
    
    args = parser.parse_args()
    
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=args.hours_back)
    
    # Run verification
    verifier = ForecastVerifier(
        spatial_threshold_km=args.spatial_threshold
    )
    
    results = verifier.verify_forecasts(
        model_name=args.model,
        start_time=start_time,
        end_time=end_time,
        variable=args.variable
    )
    
    print(f"\nVerified {results['pairs_verified']} forecast-observation pairs")
    
    # Show statistical metrics
    print("\n=== STATISTICAL METRICS ===")
    print(f"MAE:  {results['statistical_summary']['mae']:.2f}")
    print(f"RMSE: {results['statistical_summary']['rmse']:.2f}")
    print(f"Bias: {results['statistical_summary']['bias']:.2f}")
    
    # Show decision metrics
    if args.show_decision_metrics:
        print("\n=== DECISION METRICS (Operational Value) ===")
        for threshold, metrics in results['decision_summary'].items():
            print(f"\nThreshold: {threshold}")
            print(f"  Hit Rate (POD):       {metrics['hit_rate']:.3f}")
            print(f"  False Alarm Rate:     {metrics['false_alarm_rate']:.3f}")
            print(f"  False Alarm Ratio:    {metrics['false_alarm_ratio']:.3f}")
            print(f"  CSI:                  {metrics['csi']:.3f} ← KEY METRIC")
            print(f"  Accuracy:             {metrics['accuracy']:.3f}")
    
    # Generate skill metrics
    skill_df = verifier.aggregate_skill_metrics(
        model_name=args.model,
        lookback_days=7,
        by_threshold=True
    )
    
    print("\n=== 7-DAY SKILL SUMMARY ===")
    print(skill_df.to_string())

if __name__ == '__main__':
    main()
```

## 15. Automated Verification Cron Job

Add to crontab (runs hourly):
```bash
# Run verification hourly with decision metrics
0 * * * * cd ~/projects/weather-model-selector && venv/bin/python scripts/run_verification.py --model GFS --hours-back 6 --show-decision-metrics >> logs/verification.log 2>&1
5 * * * * cd ~/projects/weather-model-selector && venv/bin/python scripts/run_verification.py --model NAM --hours-back 6 --show-decision-metrics >> logs/verification.log 2>&1
```

## 16. Metric Selection for Model Choice

**When selecting which model to use:**

```python
def select_best_model_for_decision(variable: str,
                                   lead_time: int,
                                   threshold: float,
                                   decision_type: str = 'safety_critical') -> str:
    """
    Select best model based on decision context.
    
    Args:
        variable: Weather variable
        lead_time: Forecast lead time in hours
        threshold: Decision threshold value
        decision_type: 'safety_critical' or 'cost_sensitive'
    
    Returns:
        Model name with best skill for this decision
    """
    
    if decision_type == 'safety_critical':
        # Prioritize HIGH hit rate (don't miss events)
        # Accept higher false alarm rate
        metric_weights = {
            'hit_rate': 0.5,
            'csi': 0.3,
            'false_alarm_ratio': 0.2
        }
    
    elif decision_type == 'cost_sensitive':
        # Balance hit rate and false alarm rate
        # Prioritize CSI
        metric_weights = {
            'csi': 0.5,
            'hit_rate': 0.25,
            'false_alarm_ratio': 0.25
        }
    
    # Query skill database with weights
    # Return model with highest weighted score
```

## Performance Optimization

For large datasets:
- Batch database queries (100-1000 records at a time)
- Use spatial indexing (PostGIS if available)
- Cache recent forecasts in memory
- Process by region to limit search space
- Use pandas for vectorized operations

## Requirements

- Use PostgreSQL for all database operations
- Use pandas for data aggregation
- Include comprehensive logging with loguru
- Handle missing data gracefully
- Support both real-time and retrospective verification
- Make spatial threshold configurable
- Use proper datetime handling (UTC everywhere)
- Calculate BOTH statistical and decision metrics
- Store threshold verification results separately

## Success Criteria

- Successfully matches 80%+ of observations to forecasts
- Completes verification of 24 hours of data in < 5 minutes
- Correctly handles unit conversions
- Generates skill metrics grouped by lead time AND threshold
- CSI values are in reasonable range (0.3-0.8 for most weather)
- Can identify best model for specific decision contexts

## File Locations

Create:
- `src/verification/forecast_verification.py` (main verification engine)
- `src/verification/__init__.py` (package init)
- `scripts/run_verification.py` (CLI tool)
- `scripts/update_verification_schema.sql` (add threshold tables)
- `tests/test_verification.py` (unit tests)

## Documentation to Include

Add to `docs/verification_methodology.md`:

```markdown
# Verification Methodology

## Why We Use Both Statistical and Decision Metrics

Traditional verification focuses on statistical accuracy (MAE, RMSE).
We also calculate decision-relevant metrics (CSI, hit rate) because:

1. **Decision Context Matters**: A 3°F error matters more at 32°F than at 80°F
2. **Threshold Accuracy**: Getting the right side of a threshold is often more important than minimizing error
3. **Operational Value**: False alarms have costs, misses have risks
4. **Model Selection**: Different models excel at different tasks

## Metric Interpretation Guide

### Critical Success Index (CSI)
- Primary metric for operational value
- Range: 0-1, higher is better
- 0.5 = good, 0.7 = excellent
- Use this to select model for specific decisions

### Hit Rate (POD)
- Safety-critical decisions need HIGH hit rate
- Acceptable to have more false alarms if it means fewer misses
- For freezing forecasts, target hit rate > 0.85

### False Alarm Ratio
- Cost-sensitive decisions need LOW false alarm ratio
- Too many false alarms erode forecast credibility
- For routine operations, target FAR < 0.30

## When to Trust Which Metric

**Use CSI when:**
- Balancing safety and cost
- Selecting "best overall" model
- Event frequency is moderate (10-40% of time)

**Use Hit Rate when:**
- Safety is paramount
- Missing an event is unacceptable
- False alarms are tolerable

**Use MAE/RMSE when:**
- Continuous values matter (not just thresholds)
- Diagnosing systematic model biases
- No specific decision threshold exists
```

## Next Steps After Implementation

1. Run verification on historical data (last 30 days)
2. Generate threshold verification tables
3. Calculate CSI for each model by lead time and threshold
4. Build conditional skill database (Phase 1)
5. Implement model selection based on decision context
6. Create dashboard showing decision metric trends
