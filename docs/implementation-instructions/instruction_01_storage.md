# Task 1: Storage Architecture Setup

Create `src/utils/storage.py` that manages our multi-tier storage architecture:

## 1. Storage Tiers Configuration

Define three storage tiers:

**LOCAL (Fast SSD storage)**
- Path: `data/raw/` and `data/processed/`
- Retention: Last 7 days of hot data
- Purpose: Active processing

**NAS (Network storage)**
- Path: Configurable via `NAS_STORAGE_PATH` env variable
- Mount point: `/mnt/nas/weather-data/`
- Retention: 14 days raw forecasts, 30 days observations
- Purpose: Medium-term archive

**CLOUD (S3/Azure)**
- Configurable provider (AWS S3 or Azure Blob)
- Only verification metrics, not raw data
- Retention: Forever
- Purpose: Permanent metrics backup

## 2. Data Lifecycle Functions

Implement these functions:

```python
def move_to_nas(file_path: str) -> bool:
    """Move files from local to NAS after 24 hours"""
    
def archive_to_cloud(data_type: str, date_range: str) -> bool:
    """Export metrics to cloud"""
    
def cleanup_old_data(data_type: str, age_days: int) -> int:
    """Delete based on retention policy, return count deleted"""
    
def get_storage_stats() -> dict:
    """Return usage by tier and data type"""
```

## 3. Path Resolution

```python
def get_storage_path(data_type: str, date: datetime, tier: str = 'local') -> Path:
    """Returns correct path, handles local → NAS → cloud hierarchy, creates directories if needed"""
```

## 4. Storage Monitoring

```python
def check_available_space(tier: str) -> dict:
    """Returns free space in GB and percentage"""
    
def estimate_daily_usage(data_type: str) -> float:
    """Predicts growth in GB/day based on recent history"""
    
def recommend_cleanup() -> list:
    """Suggests what to delete based on retention policies"""
```

## 5. Configuration via .env

Required environment variables:
- `LOCAL_STORAGE_PATH`
- `NAS_STORAGE_PATH`
- `NAS_ENABLED` (true/false)
- `CLOUD_PROVIDER` (aws/azure/none)
- `RETENTION_RAW_FORECASTS_DAYS` (default 14)
- `RETENTION_OBSERVATIONS_DAYS` (default 30)

## Requirements

- Use `pathlib.Path` for all path operations
- Include comprehensive docstrings
- Add type hints
- Implement robust error handling
- Use `loguru` for logging
- Support dry-run mode for testing

## File Location

Create: `src/utils/storage.py`