"""Multi-tier storage management for weather model data."""
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from loguru import logger
import psutil

from src.config import settings


# Storage tier constants
TIER_LOCAL = 'local'
TIER_NAS = 'nas'
TIER_CLOUD = 'cloud'

# Data type constants
DATA_TYPE_RAW = 'raw'
DATA_TYPE_PROCESSED = 'processed'
DATA_TYPE_OBSERVATIONS = 'observations'


def get_storage_path(data_type: str, date: datetime, tier: str = 'local') -> Path:
    """
    Get the storage path for a given data type, date, and tier.

    Args:
        data_type: Type of data ('raw', 'processed', 'observations')
        date: Date for directory organization
        tier: Storage tier ('local' or 'nas')

    Returns:
        Path object for storage location

    Examples:
        >>> get_storage_path('raw', datetime(2025, 11, 18), 'local')
        Path('data/raw/20251118')
        >>> get_storage_path('raw', datetime(2025, 11, 18), 'nas')
        Path('/mnt/nas/weather-data/raw/20251118')
    """
    date_str = date.strftime('%Y%m%d')

    if tier == TIER_LOCAL:
        base_path = settings.local_storage_path
    elif tier == TIER_NAS:
        base_path = settings.nas_storage_path
    else:
        raise ValueError(f"Invalid tier: {tier}. Must be 'local' or 'nas'")

    # Build path: base/data_type/YYYYMMDD
    path = base_path / data_type / date_str

    # Create directory if it doesn't exist
    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured storage path exists: {path}")
    except Exception as e:
        logger.error(f"Failed to create storage path {path}: {e}")

    return path


def move_to_nas(file_path: str, delete_local: bool = True) -> bool:
    """
    Move files from local to NAS storage.

    Args:
        file_path: Path to local file (string or Path)
        delete_local: Whether to delete the local file after successful copy

    Returns:
        True if successful, False otherwise
    """
    if not settings.nas_enabled:
        logger.debug("NAS not enabled, skipping move")
        return False

    local_path = Path(file_path)

    if not local_path.exists():
        logger.error(f"Local file does not exist: {local_path}")
        return False

    try:
        # Determine the relative path from local storage
        relative_path = local_path.relative_to(settings.local_storage_path)

        # Build NAS destination path
        nas_path = settings.nas_storage_path / relative_path

        # Ensure destination directory exists
        nas_path.parent.mkdir(parents=True, exist_ok=True)

        # Copy file to NAS
        logger.info(f"Moving {local_path} → {nas_path}")
        shutil.copy2(local_path, nas_path)

        # Verify file integrity (compare sizes)
        if local_path.stat().st_size != nas_path.stat().st_size:
            logger.error(f"File size mismatch after copy: {local_path} vs {nas_path}")
            return False

        logger.success(f"Successfully copied to NAS: {nas_path}")

        # Delete local file if requested
        if delete_local:
            local_path.unlink()
            logger.info(f"Deleted local file: {local_path}")

        return True

    except ValueError as e:
        logger.error(f"File is not in local storage path: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to move file to NAS: {e}")
        return False


def archive_to_cloud(data_type: str, date_range: str) -> bool:
    """
    Export verification metrics to cloud storage.

    Note: This is a placeholder for cloud backup functionality.
    Only metrics (not raw data) should be archived to cloud.

    Args:
        data_type: Type of data to archive
        date_range: Date range in format 'YYYY-MM-DD:YYYY-MM-DD'

    Returns:
        True if successful, False otherwise
    """
    if settings.cloud_provider == 'none':
        logger.debug("Cloud backup not enabled")
        return False

    # Placeholder implementation
    logger.warning(f"Cloud archive not yet implemented for {data_type}, {date_range}")
    logger.info(f"Would archive to {settings.cloud_provider}")

    return False


def cleanup_old_data(data_type: str, age_days: int, tier: str = 'local', dry_run: bool = False) -> int:
    """
    Delete files older than the specified age based on retention policy.

    Args:
        data_type: Type of data ('raw', 'processed', 'observations')
        age_days: Delete files older than this many days
        tier: Storage tier to clean ('local' or 'nas')
        dry_run: If True, only report what would be deleted without deleting

    Returns:
        Number of files deleted (or would be deleted in dry_run mode)
    """
    if tier == TIER_LOCAL:
        base_path = settings.local_storage_path / data_type
    elif tier == TIER_NAS:
        if not settings.nas_enabled:
            logger.debug("NAS not enabled, skipping cleanup")
            return 0
        base_path = settings.nas_storage_path / data_type
    else:
        logger.error(f"Invalid tier: {tier}")
        return 0

    if not base_path.exists():
        logger.debug(f"Path does not exist: {base_path}")
        return 0

    # Calculate cutoff time
    cutoff_time = datetime.now().timestamp() - (age_days * 24 * 3600)
    deleted_count = 0
    freed_space = 0

    try:
        # Walk through all files in the directory
        for file_path in base_path.rglob('*'):
            if file_path.is_file():
                # Check file age
                file_mtime = file_path.stat().st_mtime
                if file_mtime < cutoff_time:
                    file_size = file_path.stat().st_size
                    freed_space += file_size

                    if dry_run:
                        logger.info(f"[DRY RUN] Would delete: {file_path} ({file_size / 1024 / 1024:.2f} MB)")
                    else:
                        logger.info(f"Deleting old file: {file_path}")
                        file_path.unlink()

                    deleted_count += 1

        mode = "[DRY RUN]" if dry_run else ""
        logger.success(
            f"{mode} Cleaned up {deleted_count} files from {tier}/{data_type}, "
            f"freed {freed_space / 1024 / 1024 / 1024:.2f} GB"
        )

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

    return deleted_count


def get_storage_stats() -> Dict[str, Dict[str, Any]]:
    """
    Get storage statistics for all tiers.

    Returns:
        Dictionary with statistics for each tier:
        {
            'local': {
                'total_space_gb': float,
                'used_space_gb': float,
                'free_space_gb': float,
                'usage_percent': float,
                'files_count': int,
                'total_size_gb': float
            },
            'nas': { ... } (if enabled)
        }
    """
    stats = {}

    # Local storage stats
    try:
        local_path = settings.local_storage_path
        usage = psutil.disk_usage(str(local_path))

        # Count files and total size
        files_count = 0
        total_size = 0
        if local_path.exists():
            for file_path in local_path.rglob('*'):
                if file_path.is_file():
                    files_count += 1
                    total_size += file_path.stat().st_size

        stats['local'] = {
            'total_space_gb': usage.total / (1024 ** 3),
            'used_space_gb': usage.used / (1024 ** 3),
            'free_space_gb': usage.free / (1024 ** 3),
            'usage_percent': usage.percent,
            'files_count': files_count,
            'total_size_gb': total_size / (1024 ** 3)
        }
    except Exception as e:
        logger.error(f"Failed to get local storage stats: {e}")
        stats['local'] = {'error': str(e)}

    # NAS storage stats (if enabled)
    if settings.nas_enabled:
        try:
            nas_path = settings.nas_storage_path
            if nas_path.exists():
                usage = psutil.disk_usage(str(nas_path))

                # Count files and total size
                files_count = 0
                total_size = 0
                for file_path in nas_path.rglob('*'):
                    if file_path.is_file():
                        files_count += 1
                        total_size += file_path.stat().st_size

                stats['nas'] = {
                    'total_space_gb': usage.total / (1024 ** 3),
                    'used_space_gb': usage.used / (1024 ** 3),
                    'free_space_gb': usage.free / (1024 ** 3),
                    'usage_percent': usage.percent,
                    'files_count': files_count,
                    'total_size_gb': total_size / (1024 ** 3)
                }
            else:
                stats['nas'] = {'error': 'NAS path does not exist'}
        except Exception as e:
            logger.error(f"Failed to get NAS storage stats: {e}")
            stats['nas'] = {'error': str(e)}

    return stats


def check_available_space(tier: str) -> Dict[str, float]:
    """
    Check available space for a storage tier.

    Args:
        tier: Storage tier ('local' or 'nas')

    Returns:
        Dictionary with:
        - free_space_gb: Free space in GB
        - usage_percent: Disk usage percentage
    """
    if tier == TIER_LOCAL:
        path = settings.local_storage_path
    elif tier == TIER_NAS:
        if not settings.nas_enabled:
            return {'error': 'NAS not enabled'}
        path = settings.nas_storage_path
    else:
        return {'error': f'Invalid tier: {tier}'}

    try:
        usage = psutil.disk_usage(str(path))
        return {
            'free_space_gb': usage.free / (1024 ** 3),
            'usage_percent': usage.percent
        }
    except Exception as e:
        logger.error(f"Failed to check space for {tier}: {e}")
        return {'error': str(e)}


def estimate_daily_usage(data_type: str, tier: str = 'local', days_to_analyze: int = 7) -> float:
    """
    Estimate daily storage usage based on recent history.

    Args:
        data_type: Type of data ('raw', 'processed', 'observations')
        tier: Storage tier to analyze
        days_to_analyze: Number of recent days to analyze

    Returns:
        Estimated daily usage in GB/day
    """
    if tier == TIER_LOCAL:
        base_path = settings.local_storage_path / data_type
    elif tier == TIER_NAS:
        if not settings.nas_enabled:
            return 0.0
        base_path = settings.nas_storage_path / data_type
    else:
        return 0.0

    if not base_path.exists():
        return 0.0

    try:
        # Collect file sizes by day
        daily_sizes: Dict[str, int] = {}
        cutoff_time = datetime.now() - timedelta(days=days_to_analyze)

        for file_path in base_path.rglob('*'):
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime >= cutoff_time:
                    date_key = file_mtime.strftime('%Y-%m-%d')
                    file_size = file_path.stat().st_size
                    daily_sizes[date_key] = daily_sizes.get(date_key, 0) + file_size

        if not daily_sizes:
            return 0.0

        # Calculate average daily usage
        total_size = sum(daily_sizes.values())
        num_days = len(daily_sizes)
        avg_daily_gb = (total_size / num_days) / (1024 ** 3)

        logger.debug(f"Estimated daily usage for {tier}/{data_type}: {avg_daily_gb:.2f} GB/day")
        return avg_daily_gb

    except Exception as e:
        logger.error(f"Failed to estimate daily usage: {e}")
        return 0.0


def recommend_cleanup() -> List[Dict[str, Any]]:
    """
    Recommend files to delete based on retention policies.

    Returns:
        List of recommendations with:
        - tier: Storage tier
        - data_type: Type of data
        - action: Recommended action
        - files_count: Number of files affected
        - space_freed_gb: Space that would be freed
    """
    recommendations = []

    # Check local storage for raw forecasts older than retention policy
    for data_type in ['raw', 'processed', 'observations']:
        if data_type == 'observations':
            retention_days = settings.retention_observations_days
        else:
            retention_days = settings.retention_raw_forecasts_days

        # Check local tier
        local_path = settings.local_storage_path / data_type
        if local_path.exists():
            cutoff_time = datetime.now().timestamp() - (retention_days * 24 * 3600)
            old_files = []
            total_size = 0

            for file_path in local_path.rglob('*'):
                if file_path.is_file():
                    file_mtime = file_path.stat().st_mtime
                    if file_mtime < cutoff_time:
                        old_files.append(file_path)
                        total_size += file_path.stat().st_size

            if old_files:
                recommendations.append({
                    'tier': 'local',
                    'data_type': data_type,
                    'action': f'Delete files older than {retention_days} days',
                    'files_count': len(old_files),
                    'space_freed_gb': total_size / (1024 ** 3)
                })

        # Check NAS tier if enabled
        if settings.nas_enabled:
            nas_path = settings.nas_storage_path / data_type
            if nas_path.exists():
                cutoff_time = datetime.now().timestamp() - (retention_days * 24 * 3600)
                old_files = []
                total_size = 0

                for file_path in nas_path.rglob('*'):
                    if file_path.is_file():
                        file_mtime = file_path.stat().st_mtime
                        if file_mtime < cutoff_time:
                            old_files.append(file_path)
                            total_size += file_path.stat().st_size

                if old_files:
                    recommendations.append({
                        'tier': 'nas',
                        'data_type': data_type,
                        'action': f'Delete files older than {retention_days} days',
                        'files_count': len(old_files),
                        'space_freed_gb': total_size / (1024 ** 3)
                    })

    return recommendations
