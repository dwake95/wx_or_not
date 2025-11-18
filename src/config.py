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
    
    # NOAA URLs
    nomads_base_url: str = os.getenv("NOMADS_BASE_URL", "https://nomads.ncep.noaa.gov")
    
    class Config:
        env_file = ".env"

settings = Settings()
