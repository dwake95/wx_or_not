#!/usr/bin/env python3
"""Initialize database schema for weather model selection system."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.database import get_db_cursor
from loguru import logger

def init_database():
    """Create initial database tables."""
    logger.info("Initializing database schema...")
    
    with get_db_cursor() as cur:
        # Create model_forecasts table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS model_forecasts (
            id SERIAL PRIMARY KEY,
            model_name VARCHAR(50) NOT NULL,
            init_time TIMESTAMPTZ NOT NULL,
            valid_time TIMESTAMPTZ NOT NULL,
            lead_time_hours INTEGER NOT NULL,
            location_lat FLOAT NOT NULL,
            location_lon FLOAT NOT NULL,
            variable VARCHAR(50) NOT NULL,
            value FLOAT NOT NULL,
            units VARCHAR(20),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        logger.info("✓ Created model_forecasts table")
        
        # Create observations table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id SERIAL PRIMARY KEY,
            obs_time TIMESTAMPTZ NOT NULL,
            location_lat FLOAT NOT NULL,
            location_lon FLOAT NOT NULL,
            station_id VARCHAR(50),
            obs_type VARCHAR(50) NOT NULL,
            variable VARCHAR(50) NOT NULL,
            value FLOAT NOT NULL,
            units VARCHAR(20),
            quality_flag INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        logger.info("✓ Created observations table")
        
        # Create verification_scores table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS verification_scores (
            id SERIAL PRIMARY KEY,
            model_name VARCHAR(50) NOT NULL,
            valid_time TIMESTAMPTZ NOT NULL,
            lead_time_hours INTEGER NOT NULL,
            location_lat FLOAT NOT NULL,
            location_lon FLOAT NOT NULL,
            variable VARCHAR(50) NOT NULL,
            forecast_value FLOAT,
            observed_value FLOAT,
            error FLOAT,
            absolute_error FLOAT,
            squared_error FLOAT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        logger.info("✓ Created verification_scores table")
        
        # Create asset_thresholds table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS asset_thresholds (
            id SERIAL PRIMARY KEY,
            asset_type VARCHAR(100) NOT NULL,
            variable VARCHAR(50) NOT NULL,
            threshold_value FLOAT NOT NULL,
            threshold_operator VARCHAR(10) NOT NULL,
            impact_description TEXT,
            source VARCHAR(200),
            confidence VARCHAR(20),
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """)
        logger.info("✓ Created asset_thresholds table")
        
        # Create hypertables for TimescaleDB
        try:
            cur.execute("SELECT create_hypertable('model_forecasts', 'valid_time', if_not_exists => TRUE);")
            logger.info("✓ Created hypertable for model_forecasts")
        except Exception as e:
            logger.warning(f"Hypertable for model_forecasts may already exist")
        
        try:
            cur.execute("SELECT create_hypertable('observations', 'obs_time', if_not_exists => TRUE);")
            logger.info("✓ Created hypertable for observations")
        except Exception as e:
            logger.warning(f"Hypertable for observations may already exist")
        
        try:
            cur.execute("SELECT create_hypertable('verification_scores', 'valid_time', if_not_exists => TRUE);")
            logger.info("✓ Created hypertable for verification_scores")
        except Exception as e:
            logger.warning(f"Hypertable for verification_scores may already exist")
        
        # Create indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forecasts_model_time ON model_forecasts(model_name, valid_time);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_forecasts_location ON model_forecasts(location_lat, location_lon);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_obs_station_time ON observations(station_id, obs_time);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_obs_location ON observations(location_lat, location_lon);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_verification_model ON verification_scores(model_name, variable, valid_time);")
        logger.info("✓ Created indexes")
        
        # Insert sample asset thresholds
        cur.execute("""
        INSERT INTO asset_thresholds (asset_type, variable, threshold_value, threshold_operator, impact_description, source, confidence)
        VALUES 
            ('Heavy Truck', 'wind_speed', 35.0, '>', 'High-profile vehicle rollover risk', 'FHWA Guidelines', 'high'),
            ('Maritime Vessel', 'wind_speed', 34.0, '>', 'Port operations may be suspended', 'Harbor Pilot Rules', 'high'),
            ('Construction Crane', 'wind_speed', 25.0, '>', 'Crane operations restricted', 'OSHA 1926.1501', 'high')
        ON CONFLICT DO NOTHING;
        """)
        logger.info("✓ Inserted sample asset thresholds")
    
    logger.success("Database initialization complete!")

if __name__ == "__main__":
    init_database()
