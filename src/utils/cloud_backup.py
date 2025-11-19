"""Cloud backup system for weather model verification metrics."""
import gzip
import json
import os
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from loguru import logger

from src.config import settings
from src.utils.database import get_db_connection


# Last backup tracking file
LAST_BACKUP_FILE = Path("data/.last_backup")


class CloudBackupError(Exception):
    """Base exception for cloud backup operations."""
    pass


def get_cloud_client():
    """
    Get cloud storage client based on configured provider.

    Returns:
        Configured cloud client (boto3 S3 client or Azure BlobServiceClient)

    Raises:
        CloudBackupError: If provider is not configured or not supported
    """
    provider = settings.cloud_provider.lower()

    if provider == 'none':
        raise CloudBackupError("Cloud backup is not enabled (CLOUD_PROVIDER=none)")

    elif provider == 'aws':
        try:
            import boto3
            from botocore.exceptions import ClientError

            client = boto3.client(
                's3',
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                region_name=settings.aws_region
            )
            logger.debug("AWS S3 client initialized")
            return client, 'aws'

        except ImportError:
            raise CloudBackupError(
                "boto3 not installed. Install with: pip install boto3"
            )
        except Exception as e:
            raise CloudBackupError(f"Failed to initialize AWS S3 client: {e}")

    elif provider == 'azure':
        try:
            from azure.storage.blob import BlobServiceClient

            client = BlobServiceClient.from_connection_string(
                settings.azure_storage_connection_string
            )
            logger.debug("Azure Blob Storage client initialized")
            return client, 'azure'

        except ImportError:
            raise CloudBackupError(
                "azure-storage-blob not installed. Install with: pip install azure-storage-blob"
            )
        except Exception as e:
            raise CloudBackupError(f"Failed to initialize Azure client: {e}")

    else:
        raise CloudBackupError(f"Unsupported cloud provider: {provider}")


def upload_to_cloud(local_file: Path, cloud_key: str, dry_run: bool = False) -> bool:
    """
    Upload a file to cloud storage.

    Args:
        local_file: Path to local file
        cloud_key: Key/path in cloud storage
        dry_run: If True, don't actually upload

    Returns:
        True if successful, False otherwise
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would upload {local_file} to {cloud_key}")
        return True

    try:
        client, provider = get_cloud_client()
        file_size = local_file.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        logger.info(f"Uploading {local_file.name} ({file_size_mb:.2f} MB) to {provider}...")

        if provider == 'aws':
            client.upload_file(
                str(local_file),
                settings.s3_bucket_name,
                cloud_key,
                ExtraArgs={
                    'Metadata': {
                        'upload_timestamp': datetime.now().isoformat(),
                        'original_size': str(file_size)
                    }
                }
            )

        elif provider == 'azure':
            container_client = client.get_container_client(settings.azure_container_name)
            blob_client = container_client.get_blob_client(cloud_key)

            with open(local_file, 'rb') as data:
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    metadata={
                        'upload_timestamp': datetime.now().isoformat(),
                        'original_size': str(file_size)
                    }
                )

        logger.success(f"Successfully uploaded {cloud_key}")
        return True

    except CloudBackupError as e:
        logger.warning(str(e))
        return False
    except Exception as e:
        logger.error(f"Failed to upload {local_file}: {e}")
        return False


def download_from_cloud(cloud_key: str, local_file: Path) -> bool:
    """
    Download a file from cloud storage.

    Args:
        cloud_key: Key/path in cloud storage
        local_file: Path to save file locally

    Returns:
        True if successful, False otherwise
    """
    try:
        client, provider = get_cloud_client()

        logger.info(f"Downloading {cloud_key} from {provider}...")

        # Ensure local directory exists
        local_file.parent.mkdir(parents=True, exist_ok=True)

        if provider == 'aws':
            client.download_file(
                settings.s3_bucket_name,
                cloud_key,
                str(local_file)
            )

        elif provider == 'azure':
            container_client = client.get_container_client(settings.azure_container_name)
            blob_client = container_client.get_blob_client(cloud_key)

            with open(local_file, 'wb') as data:
                download_stream = blob_client.download_blob()
                data.write(download_stream.readall())

        logger.success(f"Successfully downloaded to {local_file}")
        return True

    except CloudBackupError as e:
        logger.warning(str(e))
        return False
    except Exception as e:
        logger.error(f"Failed to download {cloud_key}: {e}")
        return False


def get_last_backup_time() -> Optional[datetime]:
    """
    Get the timestamp of the last successful backup.

    Returns:
        Datetime of last backup, or None if never backed up
    """
    if not LAST_BACKUP_FILE.exists():
        return None

    try:
        timestamp_str = LAST_BACKUP_FILE.read_text().strip()
        return datetime.fromisoformat(timestamp_str)
    except Exception as e:
        logger.warning(f"Failed to read last backup time: {e}")
        return None


def update_last_backup_time():
    """Update the last backup timestamp to now."""
    try:
        LAST_BACKUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_BACKUP_FILE.write_text(datetime.now().isoformat())
        logger.debug("Updated last backup timestamp")
    except Exception as e:
        logger.error(f"Failed to update last backup time: {e}")


def backup_verification_scores(date_range: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Export verification_scores table to Parquet, compress, and upload to cloud.

    Args:
        date_range: 'YYYY-MM-DD:YYYY-MM-DD' or None for incremental backup
        dry_run: If True, don't actually upload

    Returns:
        Dictionary with:
        - records_exported: Number of records exported
        - size_bytes: Size of compressed file
        - duration_seconds: Time taken
        - success: Whether backup succeeded
    """
    start_time = time.time()
    result = {
        'records_exported': 0,
        'size_bytes': 0,
        'duration_seconds': 0,
        'success': False
    }

    try:
        # Build query
        if date_range:
            # Specific date range
            start_date, end_date = date_range.split(':')
            query = f"""
                SELECT * FROM verification_scores
                WHERE valid_time >= '{start_date}'
                  AND valid_time <= '{end_date}'
                ORDER BY valid_time
            """
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"verification_{start_date}_to_{end_date}_{timestamp}"
        else:
            # Incremental: get records since last backup
            last_backup = get_last_backup_time()
            if last_backup:
                query = f"""
                    SELECT * FROM verification_scores
                    WHERE created_at > '{last_backup.isoformat()}'
                    ORDER BY created_at
                """
                logger.info(f"Incremental backup since {last_backup}")
            else:
                # First backup - get everything
                query = "SELECT * FROM verification_scores ORDER BY created_at"
                logger.info("First backup - exporting all records")

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"verification_{timestamp}"

        # Export to pandas DataFrame
        logger.info("Querying verification scores...")
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn)

        result['records_exported'] = len(df)

        if result['records_exported'] == 0:
            logger.info("No new records to backup")
            result['success'] = True
            result['duration_seconds'] = time.time() - start_time
            return result

        # Save to Parquet
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        parquet_file = temp_dir / f"{filename}.parquet"
        logger.info(f"Writing {result['records_exported']} records to Parquet...")
        df.to_parquet(parquet_file, compression='gzip', index=False)

        # Compress with gzip (level 6)
        compressed_file = temp_dir / f"{filename}.parquet.gz"
        logger.info("Compressing with gzip...")

        with open(parquet_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb', compresslevel=6) as f_out:
                f_out.writelines(f_in)

        result['size_bytes'] = compressed_file.stat().st_size
        size_mb = result['size_bytes'] / (1024 * 1024)
        logger.info(f"Compressed size: {size_mb:.2f} MB")

        # Estimate cost (S3 Standard: $0.023/GB/month)
        size_gb = result['size_bytes'] / (1024 ** 3)
        monthly_cost = size_gb * 0.023
        logger.info(f"Estimated monthly storage cost: ${monthly_cost:.4f}")

        # Upload to cloud
        cloud_key = f"verification_scores/{filename}.parquet.gz"
        success = upload_to_cloud(compressed_file, cloud_key, dry_run)

        if success:
            result['success'] = True
            if not dry_run:
                update_last_backup_time()
            logger.success(f"Backup completed: {result['records_exported']} records")
        else:
            logger.error("Backup failed during upload")

        # Cleanup temporary files
        parquet_file.unlink(missing_ok=True)
        compressed_file.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Backup failed: {e}")
        result['success'] = False

    result['duration_seconds'] = time.time() - start_time
    return result


def backup_conditional_skill_db(dry_run: bool = False) -> Dict[str, Any]:
    """
    Export aggregated skill metrics to JSON format.

    Args:
        dry_run: If True, don't actually upload

    Returns:
        Dictionary with backup statistics
    """
    start_time = time.time()
    result = {
        'records_exported': 0,
        'size_bytes': 0,
        'duration_seconds': 0,
        'success': False
    }

    try:
        # Query aggregated skill metrics
        query = """
            SELECT
                model_name,
                variable,
                lead_time_hours,
                DATE(valid_time) as date,
                AVG(absolute_error) as mae,
                SQRT(AVG(squared_error)) as rmse,
                COUNT(*) as sample_size
            FROM verification_scores
            WHERE observed_value IS NOT NULL
              AND forecast_value IS NOT NULL
            GROUP BY model_name, variable, lead_time_hours, DATE(valid_time)
            ORDER BY date DESC, model_name, variable, lead_time_hours
        """

        logger.info("Querying conditional skill metrics...")
        with get_db_connection() as conn:
            df = pd.read_sql_query(query, conn)

        result['records_exported'] = len(df)

        if result['records_exported'] == 0:
            logger.warning("No skill metrics found")
            result['duration_seconds'] = time.time() - start_time
            return result

        # Convert to JSON
        skill_data = {
            'export_timestamp': datetime.now().isoformat(),
            'record_count': result['records_exported'],
            'metrics': df.to_dict(orient='records')
        }

        # Save to JSON file
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = temp_dir / f"skill_metrics_{timestamp}.json"

        logger.info(f"Writing {result['records_exported']} skill metrics to JSON...")
        with open(json_file, 'w') as f:
            json.dump(skill_data, f, indent=2, default=str)

        # Compress with gzip
        compressed_file = temp_dir / f"skill_metrics_{timestamp}.json.gz"
        with open(json_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb', compresslevel=6) as f_out:
                f_out.writelines(f_in)

        result['size_bytes'] = compressed_file.stat().st_size
        logger.info(f"Compressed size: {result['size_bytes'] / 1024:.2f} KB")

        # Upload to cloud
        cloud_key = f"skill_metrics/skill_metrics_{timestamp}.json.gz"
        success = upload_to_cloud(compressed_file, cloud_key, dry_run)

        if success:
            result['success'] = True
            logger.success(f"Skill metrics backup completed")
        else:
            logger.error("Skill metrics backup failed during upload")

        # Cleanup
        json_file.unlink(missing_ok=True)
        compressed_file.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Skill metrics backup failed: {e}")
        result['success'] = False

    result['duration_seconds'] = time.time() - start_time
    return result


def backup_database_dump(backup_type: str = 'full', dry_run: bool = False) -> Dict[str, Any]:
    """
    Create full PostgreSQL dump, compress, and upload to cloud.

    Args:
        backup_type: 'full' or 'incremental' (currently only full is supported)
        dry_run: If True, don't actually upload

    Returns:
        Dictionary with backup statistics
    """
    start_time = time.time()
    result = {
        'backup_type': backup_type,
        'size_bytes': 0,
        'duration_seconds': 0,
        'success': False
    }

    try:
        # Prepare dump file
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dump_file = temp_dir / f"database_dump_{timestamp}.sql"
        compressed_file = temp_dir / f"database_dump_{timestamp}.sql.gz"

        # Parse database URL
        db_url = settings.database_url
        # Format: postgresql://user:pass@host:port/dbname

        logger.info(f"Creating {backup_type} database dump...")

        # Use pg_dump command
        dump_command = [
            'pg_dump',
            db_url,
            '-f', str(dump_file),
            '--no-owner',
            '--no-acl'
        ]

        # Execute pg_dump
        process = subprocess.run(
            dump_command,
            capture_output=True,
            text=True
        )

        if process.returncode != 0:
            raise Exception(f"pg_dump failed: {process.stderr}")

        logger.success("Database dump created")

        # Compress with gzip
        logger.info("Compressing database dump...")
        with open(dump_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb', compresslevel=6) as f_out:
                f_out.writelines(f_in)

        result['size_bytes'] = compressed_file.stat().st_size
        size_mb = result['size_bytes'] / (1024 * 1024)
        logger.info(f"Compressed dump size: {size_mb:.2f} MB")

        # Upload to cloud
        cloud_key = f"database_dumps/database_{timestamp}.sql.gz"
        success = upload_to_cloud(compressed_file, cloud_key, dry_run)

        if success:
            result['success'] = True
            logger.success("Database dump backup completed")
        else:
            logger.error("Database dump backup failed during upload")

        # Cleanup
        dump_file.unlink(missing_ok=True)
        compressed_file.unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Database dump backup failed: {e}")
        result['success'] = False

    result['duration_seconds'] = time.time() - start_time
    return result


def restore_verification_scores(date_range: Optional[str] = None) -> int:
    """
    Download and import verification scores from cloud backup.

    Args:
        date_range: Specific backup date range to restore (format: YYYYMMDD)

    Returns:
        Number of records restored
    """
    try:
        # List available backups
        backups = list_available_backups()
        verification_backups = [b for b in backups if b['type'] == 'verification_scores']

        if not verification_backups:
            logger.warning("No verification score backups found")
            return 0

        # Find matching backup
        if date_range:
            matching = [b for b in verification_backups if date_range in b['filename']]
            if not matching:
                logger.error(f"No backup found for date range: {date_range}")
                return 0
            backup = matching[0]
        else:
            # Use most recent
            backup = verification_backups[0]

        logger.info(f"Restoring from: {backup['filename']}")

        # Download backup
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_file = temp_dir / backup['filename']

        if not download_from_cloud(backup['key'], local_file):
            logger.error("Failed to download backup")
            return 0

        # Decompress
        decompressed_file = local_file.with_suffix('')  # Remove .gz
        with gzip.open(local_file, 'rb') as f_in:
            with open(decompressed_file, 'wb') as f_out:
                f_out.write(f_in.read())

        # Read Parquet
        df = pd.read_parquet(decompressed_file)
        records_count = len(df)

        logger.info(f"Importing {records_count} records to database...")

        # Import to database
        with get_db_connection() as conn:
            df.to_sql('verification_scores', conn, if_exists='append', index=False)

        logger.success(f"Restored {records_count} records")

        # Cleanup
        local_file.unlink(missing_ok=True)
        decompressed_file.unlink(missing_ok=True)

        return records_count

    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return 0


def restore_database(backup_date: str) -> bool:
    """
    Restore full database from backup.

    Args:
        backup_date: Date of backup to restore (format: YYYYMMDD)

    Returns:
        True if successful, False otherwise
    """
    try:
        # List available backups
        backups = list_available_backups()
        db_backups = [b for b in backups if b['type'] == 'database_dump']

        # Find matching backup
        matching = [b for b in db_backups if backup_date in b['filename']]
        if not matching:
            logger.error(f"No database backup found for date: {backup_date}")
            return False

        backup = matching[0]
        logger.info(f"Restoring database from: {backup['filename']}")

        # Download backup
        temp_dir = Path("data/temp")
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_file = temp_dir / backup['filename']

        if not download_from_cloud(backup['key'], local_file):
            logger.error("Failed to download backup")
            return False

        # Decompress
        decompressed_file = local_file.with_suffix('')
        with gzip.open(local_file, 'rb') as f_in:
            with open(decompressed_file, 'wb') as f_out:
                f_out.write(f_in.read())

        # Restore using psql
        logger.warning("This will overwrite the current database!")
        logger.info("Restoring database...")

        restore_command = [
            'psql',
            settings.database_url,
            '-f', str(decompressed_file)
        ]

        process = subprocess.run(
            restore_command,
            capture_output=True,
            text=True
        )

        if process.returncode != 0:
            raise Exception(f"Database restore failed: {process.stderr}")

        logger.success("Database restored successfully")

        # Cleanup
        local_file.unlink(missing_ok=True)
        decompressed_file.unlink(missing_ok=True)

        return True

    except Exception as e:
        logger.error(f"Database restore failed: {e}")
        return False


def list_available_backups() -> List[Dict[str, Any]]:
    """
    List all available backups in cloud storage.

    Returns:
        List of dictionaries with backup metadata:
        - filename: Name of backup file
        - key: Cloud storage key
        - size_bytes: File size
        - last_modified: Timestamp
        - type: Backup type (verification_scores, skill_metrics, database_dump)
    """
    backups = []

    try:
        client, provider = get_cloud_client()

        if provider == 'aws':
            # List objects in S3 bucket
            paginator = client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=settings.s3_bucket_name)

            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    key = obj['Key']
                    backup_type = key.split('/')[0] if '/' in key else 'unknown'

                    backups.append({
                        'filename': Path(key).name,
                        'key': key,
                        'size_bytes': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'type': backup_type
                    })

        elif provider == 'azure':
            # List blobs in Azure container
            container_client = client.get_container_client(settings.azure_container_name)
            blobs = container_client.list_blobs()

            for blob in blobs:
                key = blob.name
                backup_type = key.split('/')[0] if '/' in key else 'unknown'

                backups.append({
                    'filename': Path(key).name,
                    'key': key,
                    'size_bytes': blob.size,
                    'last_modified': blob.last_modified,
                    'type': backup_type
                })

        # Sort by last_modified (most recent first)
        backups.sort(key=lambda x: x['last_modified'], reverse=True)

        logger.info(f"Found {len(backups)} backups in cloud storage")

    except CloudBackupError as e:
        logger.warning(str(e))
    except Exception as e:
        logger.error(f"Failed to list backups: {e}")

    return backups
