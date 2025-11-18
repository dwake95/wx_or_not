#!/usr/bin/env python3
"""Verify the development environment is set up correctly."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
import psycopg2
from src.config import settings

def main():
    """Run all verification checks."""
    
    logger.info("=== Environment Verification ===\n")
    
    # Check Python packages
    logger.info("Checking Python packages...")
    try:
        import pandas as pd
        import numpy as np
        import xarray as xr
        import metpy
        import sklearn
        import fastapi
        logger.success("✓ All required Python packages installed")
    except ImportError as e:
        logger.error(f"✗ Missing package: {e}")
        return False
    
    # Check database connection
    logger.info("Checking database connection...")
    try:
        conn = psycopg2.connect(settings.database_url)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        db_version = cur.fetchone()[0]
        logger.success(f"✓ Database connected: {db_version.split(',')[0]}")
        
        # Check TimescaleDB
        cur.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb';")
        ts_version = cur.fetchone()[0]
        logger.success(f"✓ TimescaleDB extension active: v{ts_version}")
        
        # Check tables exist
        cur.execute("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname='public' 
            AND tablename IN ('model_forecasts', 'observations', 'verification_scores', 'asset_thresholds');
        """)
        tables = [row[0] for row in cur.fetchall()]
        if len(tables) == 4:
            logger.success(f"✓ All 4 required tables exist: {', '.join(tables)}")
        else:
            logger.warning(f"⚠ Only {len(tables)}/4 tables found")
        
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"✗ Database connection failed: {e}")
        return False
    
    # Check data directories
    logger.info("Checking data directories...")
    if settings.raw_data_dir.exists() and settings.processed_data_dir.exists():
        logger.success("✓ Data directories exist")
    else:
        logger.warning("⚠ Data directories missing")
    
    # Check .env configuration
    logger.info("Checking configuration...")
    if settings.anthropic_api_key and settings.anthropic_api_key != "your_api_key_here":
        logger.success("✓ Anthropic API key configured")
    else:
        logger.warning("⚠ Anthropic API key not set in .env file")
    
    logger.info("\n=== Verification Complete ===")
    logger.success("✓ Development environment is ready!")
    logger.info("\nNext steps:")
    logger.info("1. If Anthropic API key not set: nano .env")
    logger.info("2. Start using Claude Code: claude-code")
    logger.info("3. Or start building collectors manually")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
