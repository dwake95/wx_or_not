# Task 4: Data Lifecycle Manager

Create `scripts/data_lifecycle_manager.py` that automates data retention and backups.

## 1. Daily Cleanup Operations

```python
def cleanup_local_storage():
    """
    - Scan local storage for files older than 7 days
    - Move to NAS if not already there
    - Delete from local after successful NAS transfer
    - Log all operations
    """

def cleanup_nas_storage():
    """
    - Scan NAS for files exceeding retention periods
    - Delete raw forecasts older than RETENTION_RAW_FORECASTS_DAYS (default 14)
    - Delete raw observations older than RETENTION_OBSERVATIONS_DAYS (default 30)
    - Never delete processed metrics
    """
```

## 2. Backup Operations

```python
def backup_database_to_nas():
    """Daily PostgreSQL dump to NAS"""
    # Use pg_dump to create SQL dump
    # Compress with gzip
    # Save to /mnt/nas/weather-data/backups/database/pgdump_YYYYMMDD.sql.gz
    # Keep last 30 days of dumps

def backup_metrics_to_cloud():
    """Weekly verification metrics to cloud"""
    # Call src.utils.cloud_backup functions
    # Only run on Sundays or first run of week

def backup_full_to_cloud():
    """Monthly full database backup to cloud"""
    # Only run on 1st of month
```

## 3. Storage Monitoring

```python
def monitor_storage():
    """
    Check disk space on all tiers:
    - Local: warn if < 50 GB free
    - NAS: warn if < 100 GB free
    - Track growth rate (GB/day)
    - Project days until full
    - Return dict with stats
    """

def generate_storage_report():
    """
    Create report showing:
    - Current usage by tier and data type
    - Daily growth rate
    - Retention compliance
    - Backup status
    - Recommendations
    
    Save to: logs/storage_report_YYYYMMDD.txt
    """
```

## 4. Special Operations

```python
def archive_date_range(start_date: str, end_date: str):
    """Preserve specific period in long-term archive, don't delete"""

def reprocess_date_range(start_date: str, end_date: str):
    """Re-run verification on historical forecasts"""

def emergency_cleanup(target_gb: float):
    """
    Aggressive cleanup to free specified space:
    - Start with oldest, least important data
    - Respect critical data (recent forecasts, all metrics)
    - Log everything deleted
    """
```

## 5. Main Function

```python
def main():
    """
    Run all daily operations in sequence:
    1. Cleanup local → NAS moves
    2. Cleanup NAS (delete old)
    3. Backup database to NAS
    4. Backup metrics to cloud (if scheduled)
    5. Monitor storage
    6. Generate report
    
    Log everything to: logs/lifecycle.log
    Email summary if configured
    """
```

## 6. Command-Line Interface

Support arguments:
```bash
python scripts/data_lifecycle_manager.py --dry-run
python scripts/data_lifecycle_manager.py --cleanup-only
python scripts/data_lifecycle_manager.py --backup-only
python scripts/data_lifecycle_manager.py --emergency-cleanup 50  # free 50 GB
python scripts/data_lifecycle_manager.py --report-only
```

## 7. Cron Integration

Designed to run daily at 2 AM:
```cron
0 2 * * * cd ~/projects/weather-model-selector && venv/bin/python scripts/data_lifecycle_manager.py >> logs/lifecycle.log 2>&1
```

## Requirements

- Use `subprocess` for `pg_dump`
- Import `src.utils.storage` and `src.utils.cloud_backup`
- Use `loguru` for logging
- Send email summary using `smtplib` (if configured)
- Exit code 0 on success, non-zero on error
- Include timestamp in all log messages

## File Location

Create: `scripts/data_lifecycle_manager.py`