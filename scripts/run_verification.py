#!/usr/bin/env python3
"""
Run forecast verification for specified models and time range.

Calculates both statistical metrics (MAE, RMSE) and decision metrics (CSI, hit rate, FAR)
to assess both model accuracy and operational forecast value.
"""
import sys
from pathlib import Path
import argparse
from datetime import datetime, timedelta, timezone
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.verification.forecast_verification import ForecastVerifier


def main():
    parser = argparse.ArgumentParser(
        description='Forecast Verification - Calculate statistical and decision metrics',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify GFS forecasts from last 24 hours
  python scripts/run_verification.py --model GFS --hours-back 24

  # Verify NAM with decision metrics displayed
  python scripts/run_verification.py --model NAM --hours-back 12 --show-decision-metrics

  # Verify specific variable only
  python scripts/run_verification.py --model GFS --variable temperature_2m --hours-back 48

  # Dry run to see what would be verified
  python scripts/run_verification.py --model GFS --hours-back 6 --dry-run

Decision Metrics Guide:
  CSI (Critical Success Index): 0-1, higher is better (0.7 = excellent)
  Hit Rate (POD): Probability of detection (want HIGH for safety)
  False Alarm Ratio: Fraction of warnings that were false (want LOW)
        """
    )

    parser.add_argument('--model', required=True,
                       help='Model name (GFS, NAM, etc.)')
    parser.add_argument('--hours-back', type=int, default=24,
                       help='Hours to look back for verification (default: 24)')
    parser.add_argument('--variable',
                       help='Specific variable to verify (default: all)')
    parser.add_argument('--spatial-threshold', type=float, default=50.0,
                       help='Max distance for matching in km (default: 50)')
    parser.add_argument('--temporal-threshold', type=float, default=1.0,
                       help='Max time difference for matching in hours (default: 1)')
    parser.add_argument('--show-decision-metrics', action='store_true',
                       help='Display decision metrics summary (CSI, hit rate, etc.)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be verified without storing results')
    parser.add_argument('--skill-summary', action='store_true',
                       help='Display 7-day skill summary from database')

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("FORECAST VERIFICATION")
    logger.info("=" * 70)

    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=args.hours_back)

    logger.info(f"Model: {args.model}")
    logger.info(f"Period: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')} UTC")
    logger.info(f"Variable: {args.variable or 'all'}")
    logger.info(f"Spatial threshold: {args.spatial_threshold} km")
    if args.dry_run:
        logger.warning("DRY RUN - Results will not be stored")

    # Run verification
    verifier = ForecastVerifier(
        spatial_threshold_km=args.spatial_threshold,
        temporal_threshold_hours=args.temporal_threshold
    )

    results = verifier.verify_forecasts(
        model_name=args.model,
        start_time=start_time,
        end_time=end_time,
        variable=args.variable,
        dry_run=args.dry_run
    )

    # Display results
    print("\n" + "=" * 70)
    print(f"VERIFICATION RESULTS - {args.model}")
    print("=" * 70)
    print(f"\nVerified {results['pairs_verified']} forecast-observation pairs\n")

    # Statistical metrics
    if results['statistical_summary']:
        print("=== STATISTICAL METRICS (Model Accuracy) ===")
        for variable, metrics in results['statistical_summary'].items():
            print(f"\n{variable}:")
            print(f"  MAE:        {metrics['mae']:.3f}")
            print(f"  RMSE:       {metrics['rmse']:.3f}")
            print(f"  Bias:       {metrics['bias']:.3f}")
            print(f"  Pairs:      {metrics['pairs']}")

    # Decision metrics
    if args.show_decision_metrics and results['decision_summary']:
        print("\n=== DECISION METRICS (Operational Value) ===")
        print("These metrics show forecast value for decision-making\n")

        for threshold_key, metrics in results['decision_summary'].items():
            print(f"\n{threshold_key}:")
            print(f"  Hit Rate (POD):       {metrics['hit_rate']:.3f}  (want HIGH)")
            print(f"  False Alarm Rate:     {metrics['false_alarm_rate']:.3f}  (want LOW)")
            print(f"  False Alarm Ratio:    {metrics['false_alarm_ratio']:.3f}  (want LOW)")
            print(f"  CSI:                  {metrics['csi']:.3f}  ← KEY METRIC (0.7 = excellent)")
            print(f"  Accuracy:             {metrics['accuracy']:.3f}")
            print(f"  Bias Score:           {metrics['bias_score']:.3f}  (1.0 = unbiased)")
            print(f"\n  Contingency Table:")
            print(f"    Hits:              {metrics['hits']}")
            print(f"    Misses:            {metrics['misses']}  (didn't warn)")
            print(f"    False Alarms:      {metrics['false_alarms']}  (warned unnecessarily)")
            print(f"    Correct Negatives: {metrics['correct_negatives']}")

    # Skill summary
    if args.skill_summary:
        print("\n=== 7-DAY SKILL SUMMARY ===")
        skill_df = verifier.aggregate_skill_metrics(
            model_name=args.model,
            lookback_days=7,
            by_threshold=True
        )

        if not skill_df.empty:
            # Display subset of columns
            display_cols = ['variable', 'lead_time_hours', 'threshold_value',
                          'mae', 'rmse', 'csi', 'hit_rate', 'total_pairs']
            available_cols = [col for col in display_cols if col in skill_df.columns]

            print(skill_df[available_cols].to_string(index=False))
        else:
            print("No historical skill data available")

    print("\n" + "=" * 70)

    if not args.dry_run:
        logger.success("Verification complete - results stored in database")
        logger.info("To view skill summary: add --skill-summary flag")
        logger.info("To see decision metrics: add --show-decision-metrics flag")
    else:
        logger.info("Dry run complete - no results stored")

    print("=" * 70 + "\n")


if __name__ == '__main__':
    main()
