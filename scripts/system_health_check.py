#!/usr/bin/env python3
"""
System Health Check for Weather Model Selector

Monitors:
- Database connectivity
- Data freshness (forecasts and observations)
- Disk space (local and NAS)
- Verification status

Generates health reports and returns exit code 0 if healthy, 1 if issues detected.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Tuple
import psutil
from loguru import logger

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.database import get_db_connection

# Configure logging
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)
logger.add(log_dir / "health.log", rotation="10 MB", retention="30 days")

# Thresholds
MIN_LOCAL_DISK_GB = 50
MIN_NAS_DISK_GB = 100
MAX_FORECAST_AGE_HOURS = 12
MAX_OBSERVATION_AGE_HOURS = 2
MAX_VERIFICATION_AGE_HOURS = 24


def check_database_connectivity() -> Tuple[bool, str]:
    """
    Check if database is accessible and responding.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                if result and result[0] == 1:
                    return True, "Database connection successful"
                else:
                    return False, "Database query returned unexpected result"
    except Exception as e:
        return False, f"Database connection failed: {e}"


def check_data_freshness() -> Tuple[bool, str]:
    """
    Check age of latest forecasts and observations.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check latest forecast
                cur.execute("""
                    SELECT model_name, MAX(init_time) as latest_init
                    FROM model_forecasts
                    GROUP BY model_name
                    ORDER BY latest_init DESC
                    LIMIT 1
                """)
                forecast_row = cur.fetchone()

                # Check latest observation
                cur.execute("""
                    SELECT obs_type, MAX(obs_time) as latest_obs
                    FROM observations
                    GROUP BY obs_type
                    ORDER BY latest_obs DESC
                    LIMIT 1
                """)
                obs_row = cur.fetchone()

                now = datetime.now(timezone.utc)
                issues = []

                if forecast_row:
                    model_name, latest_forecast = forecast_row
                    age_hours = (now - latest_forecast).total_seconds() / 3600
                    if age_hours > MAX_FORECAST_AGE_HOURS:
                        issues.append(f"Latest forecast ({model_name}) is {age_hours:.1f} hours old (max {MAX_FORECAST_AGE_HOURS})")
                else:
                    issues.append("No forecasts found in database")

                if obs_row:
                    obs_type, latest_obs = obs_row
                    age_hours = (now - latest_obs).total_seconds() / 3600
                    if age_hours > MAX_OBSERVATION_AGE_HOURS:
                        issues.append(f"Latest observation ({obs_type}) is {age_hours:.1f} hours old (max {MAX_OBSERVATION_AGE_HOURS})")
                else:
                    issues.append("No observations found in database")

                if issues:
                    return False, "; ".join(issues)
                else:
                    return True, f"Data fresh (forecast: {age_hours:.1f}h old)"

    except Exception as e:
        return False, f"Data freshness check failed: {e}"


def check_disk_space() -> Tuple[bool, str]:
    """
    Check available disk space on local and NAS storage.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        issues = []

        # Check local disk (project directory)
        project_dir = Path(__file__).parent.parent
        local_usage = psutil.disk_usage(str(project_dir))
        local_free_gb = local_usage.free / (1024 ** 3)

        if local_free_gb < MIN_LOCAL_DISK_GB:
            issues.append(f"Local disk space low: {local_free_gb:.1f} GB free (min {MIN_LOCAL_DISK_GB} GB)")

        # Check NAS if mounted
        nas_path = Path("/tmp/weather-nas-test")
        if nas_path.exists() and nas_path.is_mount():
            nas_usage = psutil.disk_usage(str(nas_path))
            nas_free_gb = nas_usage.free / (1024 ** 3)

            if nas_free_gb < MIN_NAS_DISK_GB:
                issues.append(f"NAS disk space low: {nas_free_gb:.1f} GB free (min {MIN_NAS_DISK_GB} GB)")

        if issues:
            return False, "; ".join(issues)
        else:
            return True, f"Disk space adequate (local: {local_free_gb:.1f} GB free)"

    except Exception as e:
        return False, f"Disk space check failed: {e}"


def check_verification_status() -> Tuple[bool, str]:
    """
    Check if verification is running and up to date.

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Check latest verification
                cur.execute("""
                    SELECT model_name, COUNT(*), MAX(created_at) as latest_verification
                    FROM verification_scores
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY model_name
                """)
                results = cur.fetchall()

                if not results:
                    return False, "No verifications in last 24 hours"

                now = datetime.now(timezone.utc)
                messages = []

                for model_name, count, latest_verif in results:
                    age_hours = (now - latest_verif).total_seconds() / 3600
                    messages.append(f"{model_name}: {count} verifications, latest {age_hours:.1f}h ago")

                    if age_hours > MAX_VERIFICATION_AGE_HOURS:
                        return False, f"{model_name} verification is {age_hours:.1f}h old (max {MAX_VERIFICATION_AGE_HOURS}h)"

                return True, "; ".join(messages)

    except Exception as e:
        return False, f"Verification check failed: {e}"


def generate_health_report() -> bool:
    """
    Run all health checks and generate detailed report.

    Returns:
        True if all checks pass, False otherwise
    """
    timestamp = datetime.now(timezone.utc)
    report_file = log_dir / f"health_report_{timestamp.strftime('%Y%m%d_%H%M%S')}.txt"

    # Run all checks
    checks = {
        "Database Connectivity": check_database_connectivity(),
        "Data Freshness": check_data_freshness(),
        "Disk Space": check_disk_space(),
        "Verification Status": check_verification_status()
    }

    # Determine overall health
    all_passed = all(success for success, _ in checks.values())

    # Generate report
    with open(report_file, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("WEATHER MODEL SELECTOR - SYSTEM HEALTH REPORT\n")
        f.write(f"Generated: {timestamp.strftime('%Y-%m-%dT%H:%M:%S')} UTC\n")
        f.write("=" * 70 + "\n\n")

        f.write("CHECK RESULTS:\n")
        f.write("-" * 70 + "\n")

        for check_name, (success, message) in checks.items():
            status = "PASS" if success else "FAIL"
            padding = "." * (55 - len(check_name))
            f.write(f"{check_name}{padding} {status}\n")
            if message:
                f.write(f"  {message}\n")

        f.write("\n" + "=" * 70 + "\n")
        if all_passed:
            f.write("OVERALL STATUS: HEALTHY ✓\n")
        else:
            f.write("OVERALL STATUS: ISSUES DETECTED ✗\n")
        f.write("=" * 70 + "\n")

    # Log results
    if all_passed:
        logger.success(f"Health check passed - report saved to {report_file}")
    else:
        logger.error(f"Health check failed - report saved to {report_file}")
        for check_name, (success, message) in checks.items():
            if not success:
                logger.error(f"{check_name}: {message}")

    # Print to console
    with open(report_file, 'r') as f:
        print(f.read())

    return all_passed


def main():
    """Main entry point."""
    try:
        logger.info("Starting system health check")
        all_healthy = generate_health_report()

        if all_healthy:
            logger.success("System health check completed - all checks passed")
            sys.exit(0)
        else:
            logger.error("System health check completed - issues detected")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Health check failed with error: {e}")
        print(f"ERROR: Health check failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
