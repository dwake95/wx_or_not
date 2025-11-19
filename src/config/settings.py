"""Configuration management for weather model selector."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    """Application settings."""
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "postgresql://weather_user:weather_dev_2024!@localhost:5432/weather_dev")
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # API Keys
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Data directories
    raw_data_dir: Path = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
    processed_data_dir: Path = Path(os.getenv("PROCESSED_DATA_DIR", "data/processed"))

    # Storage Tiers
    local_storage_path: Path = Path(os.getenv("LOCAL_STORAGE_PATH", "data/raw"))
    nas_storage_path: Path = Path(os.getenv("NAS_STORAGE_PATH", "/mnt/nas/weather-data"))
    nas_enabled: bool = os.getenv("NAS_ENABLED", "false").lower() == "true"

    # Cloud Backup
    cloud_provider: str = os.getenv("CLOUD_PROVIDER", "none")  # aws, azure, or none

    # AWS S3 Configuration
    aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    aws_region: str = os.getenv("AWS_REGION", "us-west-2")
    s3_bucket_name: str = os.getenv("S3_BUCKET_NAME", "weather-verification-backup")

    # Azure Blob Storage Configuration
    azure_storage_connection_string: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    azure_container_name: str = os.getenv("AZURE_CONTAINER_NAME", "weather-verification")

    # Retention Policies (in days)
    retention_raw_forecasts_days: int = int(os.getenv("RETENTION_RAW_FORECASTS_DAYS", "14"))
    retention_observations_days: int = int(os.getenv("RETENTION_OBSERVATIONS_DAYS", "30"))

    # NOAA URLs
    nomads_base_url: str = os.getenv("NOMADS_BASE_URL", "https://nomads.ncep.noaa.gov")
    
    class Config:
        env_file = ".env"

settings = Settings()
