#!/bin/bash
# Automated weather data collection script
# Runs GFS and NAM model collections for all regions
# Intended to be run via cron every 6 hours

# Exit on error
set -e

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment
source venv/bin/activate

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Set up logging
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/collection_$(date +%Y%m%d_%H%M%S).log"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========================================="
log "Starting automated data collection"
log "========================================="

# Collect GFS data for all regions
log "Collecting GFS forecasts for all regions..."
if python src/collectors/gfs_collector_v2.py --region all >> "$LOG_FILE" 2>&1; then
    log "✓ GFS collection completed successfully"
else
    log "✗ GFS collection failed (exit code: $?)"
fi

# Wait a bit to avoid overloading NOAA servers
sleep 10

# Collect NAM data for all regions
log "Collecting NAM forecasts for all regions..."
if python src/collectors/nam_collector.py --region all >> "$LOG_FILE" 2>&1; then
    log "✓ NAM collection completed successfully"
else
    log "✗ NAM collection failed (exit code: $?)"
fi

# Wait a bit to avoid overloading NOAA servers
sleep 10

# Collect HRRR data for all regions
log "Collecting HRRR forecasts for all regions..."
if python src/collectors/hrrr_collector.py --region all >> "$LOG_FILE" 2>&1; then
    log "✓ HRRR collection completed successfully"
else
    log "✗ HRRR collection failed (exit code: $?)"
fi

# Wait a bit before observations
sleep 5

# Collect METAR observations for all regions
log "Collecting METAR observations for all regions..."
if python src/collectors/metar_collector.py --region all --hours 12 >> "$LOG_FILE" 2>&1; then
    log "✓ METAR collection completed successfully"
else
    log "✗ METAR collection failed (exit code: $?)"
fi

# Wait a bit between observation sources
sleep 5

# Collect buoy observations for all regions
log "Collecting buoy observations for all regions..."
if python src/collectors/buoy_collector.py --region all --hours 12 >> "$LOG_FILE" 2>&1; then
    log "✓ Buoy collection completed successfully"
else
    log "✗ Buoy collection failed (exit code: $?)"
fi

log "========================================="
log "Collection cycle complete"
log "========================================="

# Clean up old log files (keep last 30 days)
find "$LOG_DIR" -name "collection_*.log" -mtime +30 -delete

# Optional: Run data lifecycle manager for cleanup (if configured)
if [ "${RUN_LIFECYCLE_MANAGER:-false}" = "true" ]; then
    log "Running data lifecycle manager..."
    python scripts/data_lifecycle_manager.py --cleanup-only >> "$LOG_FILE" 2>&1
    log "✓ Lifecycle manager completed"
fi

log "Done!"
