#!/bin/bash
# Quick test collection script - collects small sample from one region
# Useful for testing without waiting for full collection

set -e

cd "$(dirname "$0")/.."
source venv/bin/activate

echo "========================================="
echo "Test Collection - Southern California"
echo "========================================="
echo ""

echo "1. GFS Forecasts (3 forecast hours)..."
python src/collectors/gfs_collector_v2.py --region southern_ca --forecast-hours 0 6 12

echo ""
echo "2. NAM Forecasts (3 forecast hours)..."
python src/collectors/nam_collector.py --region southern_ca --forecast-hours 0 6 12

echo ""
echo "3. METAR Observations (last 6 hours)..."
python src/collectors/metar_collector.py --region southern_ca --hours 6

echo ""
echo "4. Buoy Observations (last 6 hours)..."
python src/collectors/buoy_collector.py --region southern_ca --hours 6

echo ""
echo "========================================="
echo "Test Collection Complete!"
echo "========================================="

# Show summary
python -c "
from src.utils.database import get_db_connection

with get_db_connection() as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT model_name, COUNT(*) FROM model_forecasts GROUP BY model_name;')
        forecasts = cur.fetchall()
        cur.execute('SELECT obs_type, COUNT(*) FROM observations GROUP BY obs_type;')
        obs = cur.fetchall()

        print()
        print('Database Summary:')
        print('  Forecasts:')
        for model, count in forecasts:
            print(f'    {model}: {count:,}')
        print('  Observations:')
        for otype, count in obs:
            print(f'    {otype}: {count:,}')
"
