# Task 3: Cloud Backup System

Create `src/utils/cloud_backup.py` that handles cloud storage of metrics.

## 1. Multi-Provider Support

Support both AWS S3 and Azure Blob Storage:
- Auto-detect from `CLOUD_PROVIDER` env variable
- Lazy import (only import provider library when needed)
- Common interface regardless of provider

## 2. Backup Functions

```python
def backup_verification_scores(date_range: str = None, dry_run: bool = False) -> dict:
    """
    Export verification_scores table to Parquet, compress, upload
    
    Args:
        date_range: 'YYYY-MM-DD:YYYY-MM-DD' or None for all new records
        dry_run: If True, don't actually upload
    
    Returns:
        dict with keys: records_exported, size_bytes, duration_seconds
    """

def backup_conditional_skill_db(dry_run: bool = False) -> dict:
    """Export aggregated skill metrics to JSON format"""

def backup_database_dump(backup_type: str = 'full', dry_run: bool = False) -> dict:
    """
    Full PostgreSQL dump, compressed with gzip
    
    Args:
        backup_type: 'full' or 'incremental'
    """
```

## 3. Restore Functions

```python
def restore_verification_scores(date_range: str = None) -> int:
    """Download and import, return count of records restored"""

def restore_database(backup_date: str) -> bool:
    """Full database restore from specified date"""

def list_available_backups() -> list:
    """Return list of available backups with metadata"""
```

## 4. Incremental Backup Strategy

- Track last backup timestamp in local file: `data/.last_backup`
- Only upload records created/modified since last backup
- Maintain 30 days of daily snapshots
- Auto-delete snapshots older than 30 days
- Tag backups with timestamp in filename: `verification_YYYYMMDD_HHMMSS.parquet.gz`

## 5. Cost Optimization

- Compress all data before upload (gzip level 6)
- Batch small files into archives
- Use lifecycle policies hint in upload metadata
- Estimate and log costs: `$0.023/GB/month for S3 Standard`
- Suggest cheaper storage class after 30 days

## 6. Configuration

AWS S3 (.env):
```
CLOUD_PROVIDER=aws
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-west-2
S3_BUCKET_NAME=weather-verification-backup
```

Azure Blob (.env):
```
CLOUD_PROVIDER=azure
AZURE_STORAGE_CONNECTION_STRING=your_connection_string
AZURE_CONTAINER_NAME=weather-verification
```

## 7. Error Handling

- Retry failed uploads up to 3 times with exponential backoff
- Log all operations with detailed error messages
- Continue on failure (don't crash entire backup)
- Send notification email on repeated failures (optional)

## Requirements

- Use `pandas` for Parquet export
- Use `boto3` for AWS S3
- Use `azure-storage-blob` for Azure
- Add these to `requirements.txt`
- Support progress bars for large uploads (optional, using `tqdm`)
- Implement `--dry-run` and `--verbose` flags

## File Location

Create: `src/utils/cloud_backup.py`