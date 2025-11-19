#!/usr/bin/env python3
"""Automated data lifecycle management for weather model storage system."""
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.config import settings
from src.utils.storage import (
    get_storage_path,
    move_to_nas,
    cleanup_old_data,
    get_storage_stats,
    check_available_space,
    estimate_daily_usage,
    recommend_cleanup
)
from src.utils.cloud_backup import (
    backup_verification_scores,
    backup_conditional_skill_db,
    backup_database_dump
)


# Configure logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "lifecycle.log"


def setup_logging():
    """Configure loguru logging."""
    logger.add(
        LOG_FILE,
        rotation="10 MB",
        retention="30 days",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
    )


def cleanup_local_storage(dry_run: bool = False) -> Dict[str, Any]:
    """
    Scan local storage for files older than 7 days and move to NAS.

    Args:
        dry_run: If True, don't actually move files

    Returns:
        Dictionary with cleanup statistics
    """
    logger.info("=" * 60)
    logger.info("CLEANUP: Local Storage → NAS")
    logger.info("=" * 60)

    result = {
        'files_scanned': 0,
        'files_moved': 0,
        'files_failed': 0,
        'space_freed_gb': 0,
        'success': True
    }

    if not settings.nas_enabled:
        logger.info("NAS not enabled, skipping local cleanup")
        return result

    try:
        # Age threshold: 7 days
        age_threshold = datetime.now() - timedelta(days=7)
        cutoff_timestamp = age_threshold.timestamp()

        # Scan local storage for old files
        local_base = settings.local_storage_path

        if not local_base.exists():
            logger.warning(f"Local storage path does not exist: {local_base}")
            return result

        # Find files older than threshold
        old_files = []
        for file_path in local_base.rglob('*'):
            if file_path.is_file():
                result['files_scanned'] += 1
                file_mtime = file_path.stat().st_mtime

                if file_mtime < cutoff_timestamp:
                    old_files.append(file_path)

        logger.info(f"Found {len(old_files)} files older than 7 days")

        # Move files to NAS
        for file_path in old_files:
            file_size = file_path.stat().st_size

            if dry_run:
                logger.info(f"[DRY RUN] Would move: {file_path}")
                result['files_moved'] += 1
                result['space_freed_gb'] += file_size / (1024 ** 3)
            else:
                if move_to_nas(str(file_path), delete_local=True):
                    result['files_moved'] += 1
                    result['space_freed_gb'] += file_size / (1024 ** 3)
                else:
                    result['files_failed'] += 1

        logger.success(
            f"Local cleanup: {result['files_moved']} files moved, "
            f"{result['space_freed_gb']:.2f} GB freed"
        )

    except Exception as e:
        logger.error(f"Local cleanup failed: {e}")
        result['success'] = False

    return result


def cleanup_nas_storage(dry_run: bool = False) -> Dict[str, Any]:
    """
    Scan NAS for files exceeding retention periods and delete them.

    Args:
        dry_run: If True, don't actually delete files

    Returns:
        Dictionary with cleanup statistics
    """
    logger.info("=" * 60)
    logger.info("CLEANUP: NAS Storage (Delete Old)")
    logger.info("=" * 60)

    result = {
        'forecasts_deleted': 0,
        'observations_deleted': 0,
        'space_freed_gb': 0,
        'success': True
    }

    if not settings.nas_enabled:
        logger.info("NAS not enabled, skipping NAS cleanup")
        return result

    try:
        # Clean up raw forecasts (default: 14 days)
        logger.info(f"Cleaning forecasts older than {settings.retention_raw_forecasts_days} days")
        forecast_result = cleanup_old_data(
            'raw',
            settings.retention_raw_forecasts_days,
            tier='nas',
            dry_run=dry_run
        )
        result['forecasts_deleted'] = forecast_result

        # Clean up observations (default: 30 days)
        logger.info(f"Cleaning observations older than {settings.retention_observations_days} days")
        obs_result = cleanup_old_data(
            'observations',
            settings.retention_observations_days,
            tier='nas',
            dry_run=dry_run
        )
        result['observations_deleted'] = obs_result

        logger.success(
            f"NAS cleanup: {result['forecasts_deleted']} forecasts, "
            f"{result['observations_deleted']} observations deleted"
        )

    except Exception as e:
        logger.error(f"NAS cleanup failed: {e}")
        result['success'] = False

    return result


def backup_database_to_nas(dry_run: bool = False) -> Dict[str, Any]:
    """
    Create daily PostgreSQL dump and save to NAS.

    Args:
        dry_run: If True, don't actually create backup

    Returns:
        Dictionary with backup statistics
    """
    logger.info("=" * 60)
    logger.info("BACKUP: Database → NAS")
    logger.info("=" * 60)

    result = {
        'backup_size_mb': 0,
        'backup_path': None,
        'success': False
    }

    try:
        # Determine backup location
        if settings.nas_enabled:
            backup_dir = settings.nas_storage_path / 'backups' / 'database'
        else:
            backup_dir = Path('data') / 'backups' / 'database'

        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d')
        backup_file = backup_dir / f"pgdump_{timestamp}.sql.gz"

        if dry_run:
            logger.info(f"[DRY RUN] Would create backup: {backup_file}")
            result['success'] = True
            return result

        logger.info(f"Creating database backup: {backup_file}")

        # Create uncompressed dump first
        temp_dump = backup_dir / f"pgdump_{timestamp}.sql"

        # Use pg_dump command
        dump_command = [
            'pg_dump',
            settings.database_url,
            '-f', str(temp_dump),
            '--no-owner',
            '--no-acl'
        ]

        logger.info("Running pg_dump...")
        process = subprocess.run(
            dump_command,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )

        if process.returncode != 0:
            raise Exception(f"pg_dump failed: {process.stderr}")

        # Compress with gzip
        logger.info("Compressing backup...")
        gzip_command = ['gzip', '-f', str(temp_dump)]
        subprocess.run(gzip_command, check=True)

        # Rename to .sql.gz
        compressed_file = Path(str(temp_dump) + '.gz')
        compressed_file.rename(backup_file)

        result['backup_size_mb'] = backup_file.stat().st_size / (1024 * 1024)
        result['backup_path'] = str(backup_file)
        result['success'] = True

        logger.success(f"Database backup created: {result['backup_size_mb']:.2f} MB")

        # Clean up old backups (keep last 30 days)
        logger.info("Cleaning old database backups...")
        cutoff_date = datetime.now() - timedelta(days=30)

        for old_backup in backup_dir.glob('pgdump_*.sql.gz'):
            if old_backup.stat().st_mtime < cutoff_date.timestamp():
                logger.info(f"Deleting old backup: {old_backup.name}")
                old_backup.unlink()

    except subprocess.TimeoutExpired:
        logger.error("Database backup timed out after 10 minutes")
        result['success'] = False
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        result['success'] = False

    return result


def backup_metrics_to_cloud(dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
    """
    Weekly verification metrics backup to cloud (runs on Sundays).

    Args:
        dry_run: If True, don't actually upload
        force: If True, run even if not Sunday

    Returns:
        Dictionary with backup statistics
    """
    logger.info("=" * 60)
    logger.info("BACKUP: Verification Metrics → Cloud")
    logger.info("=" * 60)

    result = {
        'verification_success': False,
        'skill_success': False
    }

    # Check if today is Sunday or force flag
    today = datetime.now()
    if not force and today.weekday() != 6:  # 6 = Sunday
        logger.info(f"Today is {today.strftime('%A')}, skipping weekly cloud backup (runs on Sundays)")
        return result

    try:
        # Backup verification scores
        logger.info("Backing up verification scores...")
        verification_result = backup_verification_scores(dry_run=dry_run)
        result['verification_success'] = verification_result['success']
        result['verification_records'] = verification_result['records_exported']

        # Backup skill metrics
        logger.info("Backing up skill metrics...")
        skill_result = backup_conditional_skill_db(dry_run=dry_run)
        result['skill_success'] = skill_result['success']
        result['skill_records'] = skill_result['records_exported']

        if result['verification_success'] and result['skill_success']:
            logger.success("Cloud backup completed successfully")
        else:
            logger.warning("Cloud backup completed with some failures")

    except Exception as e:
        logger.error(f"Cloud backup failed: {e}")

    return result


def backup_full_to_cloud(dry_run: bool = False, force: bool = False) -> Dict[str, Any]:
    """
    Monthly full database backup to cloud (runs on 1st of month).

    Args:
        dry_run: If True, don't actually upload
        force: If True, run even if not 1st of month

    Returns:
        Dictionary with backup statistics
    """
    logger.info("=" * 60)
    logger.info("BACKUP: Full Database → Cloud")
    logger.info("=" * 60)

    result = {
        'success': False
    }

    # Check if today is 1st of month or force flag
    today = datetime.now()
    if not force and today.day != 1:
        logger.info(f"Today is day {today.day}, skipping monthly backup (runs on 1st)")
        return result

    try:
        db_result = backup_database_dump(backup_type='full', dry_run=dry_run)
        result['success'] = db_result['success']
        result['size_mb'] = db_result['size_bytes'] / (1024 * 1024) if db_result['size_bytes'] > 0 else 0

        if result['success']:
            logger.success(f"Full database backup completed: {result.get('size_mb', 0):.2f} MB")
        else:
            logger.warning("Full database backup failed")

    except Exception as e:
        logger.error(f"Full database backup failed: {e}")

    return result


def monitor_storage() -> Dict[str, Any]:
    """
    Check disk space on all storage tiers and track growth rate.

    Returns:
        Dictionary with monitoring statistics
    """
    logger.info("=" * 60)
    logger.info("MONITORING: Storage Tiers")
    logger.info("=" * 60)

    result = {
        'warnings': [],
        'critical': []
    }

    try:
        # Get storage stats for all tiers
        stats = get_storage_stats()

        # Check local storage
        if 'local' in stats and 'error' not in stats['local']:
            local_stats = stats['local']
            free_gb = local_stats['free_space_gb']
            usage_pct = local_stats['usage_percent']

            logger.info(f"Local: {free_gb:.1f} GB free ({usage_pct:.1f}% used)")

            if free_gb < 20:
                result['critical'].append(f"Local storage critically low: {free_gb:.1f} GB free")
                logger.error(f"CRITICAL: Local storage < 20 GB free")
            elif free_gb < 50:
                result['warnings'].append(f"Local storage low: {free_gb:.1f} GB free")
                logger.warning(f"WARNING: Local storage < 50 GB free")

        # Check NAS storage
        if 'nas' in stats and 'error' not in stats['nas']:
            nas_stats = stats['nas']
            free_gb = nas_stats['free_space_gb']
            usage_pct = nas_stats['usage_percent']

            logger.info(f"NAS: {free_gb:.1f} GB free ({usage_pct:.1f}% used)")

            if free_gb < 50:
                result['critical'].append(f"NAS storage critically low: {free_gb:.1f} GB free")
                logger.error(f"CRITICAL: NAS storage < 50 GB free")
            elif free_gb < 100:
                result['warnings'].append(f"NAS storage low: {free_gb:.1f} GB free")
                logger.warning(f"WARNING: NAS storage < 100 GB free")

        # Estimate daily growth
        for tier in ['local', 'nas']:
            if tier == 'nas' and not settings.nas_enabled:
                continue

            growth_raw = estimate_daily_usage('raw', tier, days_to_analyze=7)
            if growth_raw > 0:
                logger.info(f"{tier.upper()} growth (raw): {growth_raw:.2f} GB/day")
                result[f'{tier}_daily_growth_gb'] = growth_raw

                # Project days until full
                tier_stats = stats.get(tier, {})
                if 'free_space_gb' in tier_stats:
                    free_gb = tier_stats['free_space_gb']
                    days_until_full = free_gb / growth_raw if growth_raw > 0 else float('inf')
                    logger.info(f"{tier.upper()} estimated days until full: {days_until_full:.0f}")
                    result[f'{tier}_days_until_full'] = days_until_full

                    if days_until_full < 7:
                        result['critical'].append(
                            f"{tier.upper()} will be full in {days_until_full:.0f} days"
                        )

        result['stats'] = stats

    except Exception as e:
        logger.error(f"Storage monitoring failed: {e}")
        result['error'] = str(e)

    return result


def generate_storage_report() -> str:
    """
    Generate comprehensive storage report.

    Returns:
        Path to generated report file
    """
    logger.info("=" * 60)
    logger.info("REPORT: Storage Status")
    logger.info("=" * 60)

    try:
        # Generate report filename
        timestamp = datetime.now().strftime('%Y%m%d')
        report_file = LOG_DIR / f"storage_report_{timestamp}.txt"

        # Collect data
        stats = get_storage_stats()
        recommendations = recommend_cleanup()

        # Build report
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append(f"STORAGE REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 60)
        report_lines.append("")

        # Current usage by tier
        report_lines.append("CURRENT USAGE BY TIER:")
        report_lines.append("-" * 60)
        for tier, tier_stats in stats.items():
            if 'error' not in tier_stats:
                report_lines.append(f"{tier.upper()}:")
                report_lines.append(f"  Total: {tier_stats['total_space_gb']:.1f} GB")
                report_lines.append(f"  Used: {tier_stats['used_space_gb']:.1f} GB")
                report_lines.append(f"  Free: {tier_stats['free_space_gb']:.1f} GB")
                report_lines.append(f"  Usage: {tier_stats['usage_percent']:.1f}%")
                report_lines.append(f"  Files: {tier_stats['files_count']}")
                report_lines.append(f"  Data size: {tier_stats['total_size_gb']:.2f} GB")
            else:
                report_lines.append(f"{tier.upper()}: {tier_stats['error']}")
            report_lines.append("")

        # Daily growth rate
        report_lines.append("DAILY GROWTH RATE:")
        report_lines.append("-" * 60)
        for tier in ['local', 'nas']:
            if tier == 'nas' and not settings.nas_enabled:
                continue
            growth = estimate_daily_usage('raw', tier, days_to_analyze=7)
            if growth > 0:
                report_lines.append(f"{tier.upper()}: {growth:.2f} GB/day")
        report_lines.append("")

        # Cleanup recommendations
        report_lines.append("CLEANUP RECOMMENDATIONS:")
        report_lines.append("-" * 60)
        if recommendations:
            for rec in recommendations:
                report_lines.append(
                    f"{rec['tier'].upper()}/{rec['data_type']}: "
                    f"{rec['files_count']} files, "
                    f"{rec['space_freed_gb']:.2f} GB can be freed"
                )
                report_lines.append(f"  Action: {rec['action']}")
        else:
            report_lines.append("No cleanup recommended at this time")
        report_lines.append("")

        # Retention compliance
        report_lines.append("RETENTION POLICIES:")
        report_lines.append("-" * 60)
        report_lines.append(f"Raw forecasts: {settings.retention_raw_forecasts_days} days")
        report_lines.append(f"Observations: {settings.retention_observations_days} days")
        report_lines.append("")

        # Write report
        report_file.write_text('\n'.join(report_lines))
        logger.success(f"Report generated: {report_file}")

        # Also log report summary
        for line in report_lines:
            logger.info(line)

        return str(report_file)

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return None


def archive_date_range(start_date: str, end_date: str, dry_run: bool = False) -> bool:
    """
    Archive specific date range to prevent deletion.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        dry_run: If True, don't actually archive

    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Archiving date range: {start_date} to {end_date}")

    # This is a placeholder - actual implementation would:
    # 1. Find all files in date range
    # 2. Move to special 'archive' directory
    # 3. Mark as preserved (e.g., with .archive metadata file)

    logger.warning("Archive function not fully implemented yet")
    return False


def emergency_cleanup(target_gb: float, dry_run: bool = False) -> Dict[str, Any]:
    """
    Aggressive cleanup to free specified amount of space.

    Args:
        target_gb: Target space to free in GB
        dry_run: If True, don't actually delete

    Returns:
        Dictionary with cleanup statistics
    """
    logger.info("=" * 60)
    logger.info(f"EMERGENCY CLEANUP: Target {target_gb} GB")
    logger.info("=" * 60)

    result = {
        'space_freed_gb': 0,
        'files_deleted': 0,
        'target_reached': False
    }

    try:
        # Start with oldest raw forecasts
        local_raw = settings.local_storage_path / 'raw'

        if local_raw.exists():
            # Get all files sorted by age (oldest first)
            files = []
            for f in local_raw.rglob('*'):
                if f.is_file():
                    files.append((f, f.stat().st_mtime, f.stat().st_size))

            files.sort(key=lambda x: x[1])  # Sort by mtime

            # Delete oldest files until target reached
            for file_path, mtime, size in files:
                if result['space_freed_gb'] >= target_gb:
                    result['target_reached'] = True
                    break

                size_gb = size / (1024 ** 3)

                if dry_run:
                    logger.info(f"[DRY RUN] Would delete: {file_path} ({size_gb:.3f} GB)")
                else:
                    logger.warning(f"DELETING: {file_path} ({size_gb:.3f} GB)")
                    file_path.unlink()

                result['space_freed_gb'] += size_gb
                result['files_deleted'] += 1

        logger.success(
            f"Emergency cleanup: {result['files_deleted']} files deleted, "
            f"{result['space_freed_gb']:.2f} GB freed"
        )

    except Exception as e:
        logger.error(f"Emergency cleanup failed: {e}")

    return result


def main():
    """Main lifecycle management function."""
    parser = argparse.ArgumentParser(description='Weather Data Lifecycle Manager')
    parser.add_argument('--dry-run', action='store_true',
                       help='Run without making actual changes')
    parser.add_argument('--cleanup-only', action='store_true',
                       help='Only run cleanup operations')
    parser.add_argument('--backup-only', action='store_true',
                       help='Only run backup operations')
    parser.add_argument('--report-only', action='store_true',
                       help='Only generate storage report')
    parser.add_argument('--emergency-cleanup', type=float, metavar='GB',
                       help='Emergency cleanup to free specified GB')
    parser.add_argument('--force-cloud-backup', action='store_true',
                       help='Force cloud backup regardless of schedule')

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    logger.info("=" * 60)
    logger.info("DATA LIFECYCLE MANAGER STARTED")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("=" * 60)

    overall_success = True

    try:
        # Emergency cleanup mode
        if args.emergency_cleanup:
            result = emergency_cleanup(args.emergency_cleanup, dry_run=args.dry_run)
            if not result['target_reached']:
                overall_success = False
            return 0 if overall_success else 1

        # Report only mode
        if args.report_only:
            generate_storage_report()
            return 0

        # Cleanup operations
        if not args.backup_only:
            # 1. Cleanup local → NAS
            local_result = cleanup_local_storage(dry_run=args.dry_run)
            if not local_result['success']:
                overall_success = False

            # 2. Cleanup NAS (delete old)
            nas_result = cleanup_nas_storage(dry_run=args.dry_run)
            if not nas_result['success']:
                overall_success = False

        # Backup operations
        if not args.cleanup_only:
            # 3. Backup database to NAS
            db_backup_result = backup_database_to_nas(dry_run=args.dry_run)
            if not db_backup_result['success']:
                overall_success = False

            # 4. Backup metrics to cloud (weekly - Sundays)
            metrics_result = backup_metrics_to_cloud(
                dry_run=args.dry_run,
                force=args.force_cloud_backup
            )

            # 5. Full backup to cloud (monthly - 1st of month)
            full_result = backup_full_to_cloud(
                dry_run=args.dry_run,
                force=args.force_cloud_backup
            )

        # 6. Monitor storage
        monitor_result = monitor_storage()
        if monitor_result.get('critical'):
            logger.error("CRITICAL storage issues detected!")
            for issue in monitor_result['critical']:
                logger.error(f"  - {issue}")
            overall_success = False

        # 7. Generate report
        report_path = generate_storage_report()

        logger.info("=" * 60)
        if overall_success:
            logger.success("DATA LIFECYCLE MANAGER COMPLETED SUCCESSFULLY")
        else:
            logger.warning("DATA LIFECYCLE MANAGER COMPLETED WITH ERRORS")
        logger.info("=" * 60)

        return 0 if overall_success else 1

    except Exception as e:
        logger.exception(f"Fatal error in lifecycle manager: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
