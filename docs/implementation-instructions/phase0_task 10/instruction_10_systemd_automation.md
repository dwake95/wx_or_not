# Task 10: Systemd Service Automation & Deployment

## Overview

Create systemd services and timers for production-ready automated data collection, verification, and lifecycle management. This replaces cron-based scheduling with more robust systemd units that provide better logging, dependency management, and failure handling.

---

## 1. Data Collection Service

### File: `/etc/systemd/system/weather-collector.service`

```ini
[Unit]
Description=Weather Model Data Collection Service
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
User=weather-user
Group=weather-user
WorkingDirectory=/home/weather-user/projects/weather-model-selector
Environment="PATH=/home/weather-user/projects/weather-model-selector/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/weather-user/projects/weather-model-selector/.env

# Run the collection script
ExecStart=/home/weather-user/projects/weather-model-selector/venv/bin/python -u /home/weather-user/projects/weather-model-selector/scripts/automated_collection.sh

# Logging
StandardOutput=append:/home/weather-user/projects/weather-model-selector/logs/collector.log
StandardError=append:/home/weather-user/projects/weather-model-selector/logs/collector.error.log

# Restart policy
Restart=on-failure
RestartSec=300

# Resource limits
MemoryLimit=2G
CPUQuota=150%

[Install]
WantedBy=multi-user.target
```

### File: `/etc/systemd/system/weather-collector.timer`

```ini
[Unit]
Description=Weather Model Data Collection Timer
Requires=weather-collector.service

[Timer]
# Run every 6 hours at 00:00, 06:00, 12:00, 18:00 UTC
OnCalendar=00/6:00:00
# Also run on boot (after 10 minutes)
OnBootSec=10min
# If missed, run immediately
Persistent=true
AccuracySec=5min

[Install]
WantedBy=timers.target
```

---

## 2. Verification Service

### File: `/etc/systemd/system/weather-verification.service`

```ini
[Unit]
Description=Weather Forecast Verification Service
After=network-online.target postgresql.service weather-collector.service
Wants=network-online.target

[Service]
Type=oneshot
User=weather-user
Group=weather-user
WorkingDirectory=/home/weather-user/projects/weather-model-selector
Environment="PATH=/home/weather-user/projects/weather-model-selector/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/weather-user/projects/weather-model-selector/.env

# Run verification with 6-hour lag
ExecStart=/home/weather-user/projects/weather-model-selector/venv/bin/python /home/weather-user/projects/weather-model-selector/scripts/run_verification.py --auto --lag-hours 6

StandardOutput=append:/home/weather-user/projects/weather-model-selector/logs/verification.log
StandardError=append:/home/weather-user/projects/weather-model-selector/logs/verification.error.log

Restart=on-failure
RestartSec=300

MemoryLimit=4G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

### File: `/etc/systemd/system/weather-verification.timer`

```ini
[Unit]
Description=Weather Forecast Verification Timer
Requires=weather-verification.service

[Timer]
# Run hourly at 15 minutes past the hour
OnCalendar=*-*-* *:15:00
OnBootSec=20min
Persistent=true
AccuracySec=2min

[Install]
WantedBy=timers.target
```

---

## 3. Data Lifecycle Management Service

### File: `/etc/systemd/system/weather-lifecycle.service`

```ini
[Unit]
Description=Weather Data Lifecycle Management
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
User=weather-user
Group=weather-user
WorkingDirectory=/home/weather-user/projects/weather-model-selector
Environment="PATH=/home/weather-user/projects/weather-model-selector/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/weather-user/projects/weather-model-selector/.env

# Daily cleanup and backup operations
ExecStart=/home/weather-user/projects/weather-model-selector/venv/bin/python /home/weather-user/projects/weather-model-selector/scripts/data_lifecycle_manager.py

StandardOutput=append:/home/weather-user/projects/weather-model-selector/logs/lifecycle.log
StandardError=append:/home/weather-user/projects/weather-model-selector/logs/lifecycle.error.log

Restart=on-failure
RestartSec=600

MemoryLimit=1G
CPUQuota=100%

[Install]
WantedBy=multi-user.target
```

### File: `/etc/systemd/system/weather-lifecycle.timer`

```ini
[Unit]
Description=Weather Data Lifecycle Management Timer
Requires=weather-lifecycle.service

[Timer]
# Run daily at 02:00 UTC
OnCalendar=*-*-* 02:00:00
OnBootSec=30min
Persistent=true
AccuracySec=10min

[Install]
WantedBy=timers.target
```

---

## 4. Monitoring & Health Check Service

### File: `/etc/systemd/system/weather-monitor.service`

```ini
[Unit]
Description=Weather System Health Monitor
After=network-online.target postgresql.service

[Service]
Type=oneshot
User=weather-user
Group=weather-user
WorkingDirectory=/home/weather-user/projects/weather-model-selector
Environment="PATH=/home/weather-user/projects/weather-model-selector/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/home/weather-user/projects/weather-model-selector/.env

# Run health checks and generate status report
ExecStart=/home/weather-user/projects/weather-model-selector/venv/bin/python /home/weather-user/projects/weather-model-selector/scripts/system_health_check.py

StandardOutput=append:/home/weather-user/projects/weather-model-selector/logs/health.log
StandardError=append:/home/weather-user/projects/weather-model-selector/logs/health.error.log

[Install]
WantedBy=multi-user.target
```

### File: `/etc/systemd/system/weather-monitor.timer`

```ini
[Unit]
Description=Weather System Health Monitor Timer
Requires=weather-monitor.service

[Timer]
# Run every 15 minutes
OnCalendar=*-*-* *:00,15,30,45:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
```

---

## 5. Setup Script

Create `scripts/setup_systemd_services.py`:

```python
#!/usr/bin/env python3
"""
Setup script for systemd services and timers.
Run with sudo privileges.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from loguru import logger

# Configuration
PROJECT_DIR = Path.home() / "projects" / "weather-model-selector"
SYSTEMD_DIR = Path("/etc/systemd/system")
USER = os.getenv("SUDO_USER", "weather-user")
GROUP = USER

SERVICE_FILES = {
    "weather-collector.service": """[Unit]
Description=Weather Model Data Collection Service
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
User={user}
Group={group}
WorkingDirectory={project_dir}
Environment="PATH={project_dir}/venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile={project_dir}/.env

ExecStart={project_dir}/scripts/automated_collection.sh

StandardOutput=append:{project_dir}/logs/collector.log
StandardError=append:{project_dir}/logs/collector.error.log

Restart=on-failure
RestartSec=300

MemoryLimit=2G
CPUQuota=150%

[Install]
WantedBy=multi-user.target
""",
    
    "weather-collector.timer": """[Unit]
Description=Weather Model Data Collection Timer
Requires=weather-collector.service

[Timer]
OnCalendar=00/6:00:00
OnBootSec=10min
Persistent=true
AccuracySec=5min

[Install]
WantedBy=timers.target
""",
    
    # Add other services and timers here...
}


def check_privileges():
    """Ensure script is run with sudo."""
    if os.geteuid() != 0:
        logger.error("This script must be run with sudo privileges")
        sys.exit(1)


def create_service_files():
    """Create systemd service and timer files."""
    logger.info("Creating systemd service files...")
    
    for filename, content in SERVICE_FILES.items():
        file_path = SYSTEMD_DIR / filename
        
        # Format content with actual paths
        formatted_content = content.format(
            user=USER,
            group=GROUP,
            project_dir=str(PROJECT_DIR)
        )
        
        # Write file
        file_path.write_text(formatted_content)
        file_path.chmod(0o644)
        
        logger.info(f"Created {file_path}")


def reload_systemd():
    """Reload systemd daemon."""
    logger.info("Reloading systemd daemon...")
    subprocess.run(["systemctl", "daemon-reload"], check=True)


def enable_and_start_timers():
    """Enable and start all timer units."""
    timers = [
        "weather-collector.timer",
        "weather-verification.timer",
        "weather-lifecycle.timer",
        "weather-monitor.timer"
    ]
    
    for timer in timers:
        logger.info(f"Enabling {timer}...")
        subprocess.run(["systemctl", "enable", timer], check=True)
        
        logger.info(f"Starting {timer}...")
        subprocess.run(["systemctl", "start", timer], check=True)


def show_status():
    """Display status of all timers."""
    logger.info("\n" + "="*70)
    logger.info("Systemd Timer Status")
    logger.info("="*70)
    
    subprocess.run(["systemctl", "list-timers", "--all", "weather-*"])
    
    logger.info("\n" + "="*70)
    logger.info("Service Status")
    logger.info("="*70)
    
    subprocess.run(["systemctl", "status", "weather-*.service", "--no-pager"])


def main():
    """Main setup function."""
    logger.add("logs/systemd_setup.log")
    logger.info("Starting systemd service setup...")
    
    check_privileges()
    create_service_files()
    reload_systemd()
    enable_and_start_timers()
    show_status()
    
    logger.success("\nSystemd services configured successfully!")
    logger.info("\nUseful commands:")
    logger.info("  View all timers:    systemctl list-timers weather-*")
    logger.info("  Check service logs: journalctl -u weather-collector.service -f")
    logger.info("  Stop a timer:       systemctl stop weather-collector.timer")
    logger.info("  Start a timer:      systemctl start weather-collector.timer")
    logger.info("  Run service now:    systemctl start weather-collector.service")


if __name__ == "__main__":
    main()
```

---

## 6. Health Check Script

Create `scripts/system_health_check.py`:

```python
#!/usr/bin/env python3
"""
System health monitoring script for weather model selector.
Checks data freshness, service status, disk space, and database connectivity.
"""

import sys
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from src.utils.storage import check_available_space, get_storage_stats
from src.config.db_config import get_db_config

def check_database_connectivity():
    """Verify database is accessible."""
    try:
        config = get_db_config()
        conn = psycopg2.connect(**config)
        conn.close()
        logger.info("✓ Database connectivity OK")
        return True
    except Exception as e:
        logger.error(f"✗ Database connectivity FAILED: {e}")
        return False


def check_data_freshness():
    """Check if recent data is being collected."""
    try:
        config = get_db_config()
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        # Check latest forecast
        cur.execute("""
            SELECT MAX(init_time) FROM model_forecasts
        """)
        latest_forecast = cur.fetchone()[0]
        
        # Check latest observation
        cur.execute("""
            SELECT MAX(obs_time) FROM observations
        """)
        latest_obs = cur.fetchone()[0]
        
        conn.close()
        
        now = datetime.utcnow()
        forecast_age = (now - latest_forecast).total_seconds() / 3600 if latest_forecast else 999
        obs_age = (now - latest_obs).total_seconds() / 3600 if latest_obs else 999
        
        if forecast_age < 12:
            logger.info(f"✓ Latest forecast: {forecast_age:.1f} hours old")
        else:
            logger.warning(f"⚠ Latest forecast: {forecast_age:.1f} hours old (STALE)")
        
        if obs_age < 2:
            logger.info(f"✓ Latest observation: {obs_age:.1f} hours old")
        else:
            logger.warning(f"⚠ Latest observation: {obs_age:.1f} hours old (STALE)")
        
        return forecast_age < 12 and obs_age < 2
        
    except Exception as e:
        logger.error(f"✗ Data freshness check FAILED: {e}")
        return False


def check_disk_space():
    """Check available disk space on all tiers."""
    try:
        stats = get_storage_stats()
        
        local_free = check_available_space('local')
        if local_free['free_gb'] > 50:
            logger.info(f"✓ Local storage: {local_free['free_gb']:.1f} GB free")
        else:
            logger.warning(f"⚠ Local storage: {local_free['free_gb']:.1f} GB free (LOW)")
        
        nas_free = check_available_space('nas')
        if nas_free and nas_free['free_gb'] > 100:
            logger.info(f"✓ NAS storage: {nas_free['free_gb']:.1f} GB free")
        elif nas_free:
            logger.warning(f"⚠ NAS storage: {nas_free['free_gb']:.1f} GB free (LOW)")
        
        return local_free['free_gb'] > 50
        
    except Exception as e:
        logger.error(f"✗ Disk space check FAILED: {e}")
        return False


def check_verification_status():
    """Check if verification is running regularly."""
    try:
        config = get_db_config()
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT MAX(created_at) FROM verification_scores
        """)
        latest_verification = cur.fetchone()[0]
        conn.close()
        
        if latest_verification:
            age_hours = (datetime.utcnow() - latest_verification).total_seconds() / 3600
            if age_hours < 2:
                logger.info(f"✓ Latest verification: {age_hours:.1f} hours ago")
                return True
            else:
                logger.warning(f"⚠ Latest verification: {age_hours:.1f} hours ago (DELAYED)")
                return False
        else:
            logger.warning("⚠ No verification records found")
            return False
            
    except Exception as e:
        logger.error(f"✗ Verification status check FAILED: {e}")
        return False


def generate_health_report():
    """Generate and save health report."""
    report_path = Path("logs") / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(report_path, 'w') as f:
        f.write("="*70 + "\n")
        f.write("WEATHER MODEL SELECTOR - SYSTEM HEALTH REPORT\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("="*70 + "\n\n")
        
        # Run all checks
        checks = {
            "Database Connectivity": check_database_connectivity(),
            "Data Freshness": check_data_freshness(),
            "Disk Space": check_disk_space(),
            "Verification Status": check_verification_status()
        }
        
        f.write("CHECK RESULTS:\n")
        f.write("-" * 70 + "\n")
        for check_name, result in checks.items():
            status = "PASS" if result else "FAIL"
            f.write(f"{check_name:.<50} {status}\n")
        
        f.write("\n" + "="*70 + "\n")
        
        overall = all(checks.values())
        if overall:
            f.write("OVERALL STATUS: HEALTHY ✓\n")
        else:
            f.write("OVERALL STATUS: ISSUES DETECTED ✗\n")
        
        f.write("="*70 + "\n")
    
    logger.info(f"Health report saved to: {report_path}")
    return all(checks.values())


def main():
    """Main health check function."""
    logger.info("Starting system health check...")
    
    healthy = generate_health_report()
    
    if healthy:
        logger.success("System is healthy!")
        sys.exit(0)
    else:
        logger.error("System health issues detected!")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

---

## 7. Installation Instructions for Claude Code

### Step 1: Verify Prerequisites

```bash
# Ensure all previous tasks are completed
python -c "from src.utils.storage import get_storage_stats; print('Storage OK')"
python -c "from src.config.regions import get_all_regions; print('Regions OK')"

# Check that scripts exist
ls -l scripts/automated_collection.sh
ls -l scripts/data_lifecycle_manager.py
ls -l scripts/run_verification.py
```

### Step 2: Create Health Check Script

```bash
# Create the health check script
python scripts/system_health_check.py

# Verify it works
chmod +x scripts/system_health_check.py
python scripts/system_health_check.py
```

### Step 3: Create Systemd Setup Script

```bash
# Create the setup script
chmod +x scripts/setup_systemd_services.py

# Review the service definitions
cat scripts/setup_systemd_services.py
```

### Step 4: Install Systemd Services (Requires Sudo)

```bash
# Run with sudo
sudo python scripts/setup_systemd_services.py

# Verify timers are running
systemctl list-timers weather-*

# Check service status
systemctl status weather-collector.service
```

### Step 5: Test Services Manually

```bash
# Test collector service
sudo systemctl start weather-collector.service
sudo journalctl -u weather-collector.service -n 50

# Test verification service
sudo systemctl start weather-verification.service
sudo journalctl -u weather-verification.service -n 50

# Test lifecycle service
sudo systemctl start weather-lifecycle.service
sudo journalctl -u weather-lifecycle.service -n 50

# Test monitoring service
sudo systemctl start weather-monitor.service
sudo journalctl -u weather-monitor.service -n 50
```

### Step 6: Monitor Operations

```bash
# Watch all timers
watch -n 60 'systemctl list-timers weather-*'

# Follow logs in real-time
journalctl -u weather-collector.service -f

# Check health reports
tail -f logs/health.log
```

---

## 8. Management Commands Reference

### Starting and Stopping

```bash
# Stop a specific timer
sudo systemctl stop weather-collector.timer

# Start a specific timer
sudo systemctl start weather-collector.timer

# Restart a timer
sudo systemctl restart weather-collector.timer

# Disable a timer (won't start on boot)
sudo systemctl disable weather-collector.timer
```

### Triggering Services Manually

```bash
# Run data collection now
sudo systemctl start weather-collector.service

# Run verification now
sudo systemctl start weather-verification.service

# Run lifecycle management now
sudo systemctl start weather-lifecycle.service

# Run health check now
sudo systemctl start weather-monitor.service
```

### Viewing Logs

```bash
# View recent logs for a service
sudo journalctl -u weather-collector.service -n 100

# Follow logs in real-time
sudo journalctl -u weather-collector.service -f

# View logs since a specific time
sudo journalctl -u weather-collector.service --since "1 hour ago"

# View logs for all weather services
sudo journalctl -u weather-* --since today
```

### Checking Status

```bash
# List all weather timers
systemctl list-timers weather-*

# Check if a service is active
systemctl is-active weather-collector.service

# Check if a timer is enabled
systemctl is-enabled weather-collector.timer

# Full status report
systemctl status weather-*.service weather-*.timer
```

---

## 9. Troubleshooting

### Service Fails to Start

```bash
# Check for errors
sudo journalctl -u weather-collector.service -n 100 --no-pager

# Check service file syntax
sudo systemd-analyze verify /etc/systemd/system/weather-collector.service

# Reload if you made changes
sudo systemctl daemon-reload
sudo systemctl restart weather-collector.service
```

### Timer Not Triggering

```bash
# Check timer is active
systemctl is-active weather-collector.timer

# List upcoming runs
systemctl list-timers --all

# Check timer logs
journalctl -u weather-collector.timer
```

### Permission Issues

```bash
# Verify file ownership
ls -la /home/weather-user/projects/weather-model-selector/scripts/

# Fix ownership if needed
sudo chown -R weather-user:weather-user /home/weather-user/projects/weather-model-selector/

# Verify service user
systemctl show weather-collector.service | grep User
```

---

## 10. Post-Implementation Validation

After completing Task 10, verify:

1. **All timers are enabled and active**
   ```bash
   systemctl list-timers weather-* --all
   ```

2. **Services can run successfully**
   ```bash
   sudo systemctl start weather-collector.service
   sudo systemctl status weather-collector.service
   ```

3. **Logs are being written**
   ```bash
   ls -lh logs/collector.log logs/verification.log logs/lifecycle.log
   ```

4. **Health checks are passing**
   ```bash
   python scripts/system_health_check.py
   ```

5. **Data is being collected**
   ```bash
   psql -d weather_db -c "SELECT MAX(init_time) FROM model_forecasts;"
   ```

---

## 11. Success Criteria

- ✓ All 4 systemd services created and installed
- ✓ All 4 timers enabled and running
- ✓ Data collection runs every 6 hours automatically
- ✓ Verification runs hourly with proper lag
- ✓ Lifecycle management runs daily at 02:00 UTC
- ✓ Health monitoring runs every 15 minutes
- ✓ All services restart automatically on failure
- ✓ Logs are accessible via journalctl
- ✓ System survives reboot (services start automatically)

---

## 12. Integration with Phase 0 Completion

This task completes the Phase 0 "Automated scheduling (cron/systemd)" requirement and provides:

- **Reliability**: Systemd provides better failure handling than cron
- **Logging**: Centralized logging via journald
- **Dependencies**: Services wait for network and database
- **Resource Control**: Memory and CPU limits prevent runaway processes
- **Monitoring**: Built-in status checking and health reports

With Task 10 complete, Phase 0 infrastructure is production-ready for 24/7 automated operations.

---

## File Locations Summary

**Created files:**
- `scripts/setup_systemd_services.py` - Setup automation script
- `scripts/system_health_check.py` - Health monitoring script
- `/etc/systemd/system/weather-collector.service` - Data collection service
- `/etc/systemd/system/weather-collector.timer` - Collection timer
- `/etc/systemd/system/weather-verification.service` - Verification service
- `/etc/systemd/system/weather-verification.timer` - Verification timer
- `/etc/systemd/system/weather-lifecycle.service` - Lifecycle management service
- `/etc/systemd/system/weather-lifecycle.timer` - Lifecycle timer
- `/etc/systemd/system/weather-monitor.service` - Health monitoring service
- `/etc/systemd/system/weather-monitor.timer` - Monitoring timer

**Expected execution time:** 30-45 minutes
