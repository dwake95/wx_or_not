# CLAUDE CODE QUICK-START: Task 10 - Systemd Automation

## CONTEXT
You are implementing Task 10 of Phase 0 for the Weather Model Selection System. This task creates production-ready systemd services for automated data collection, verification, and lifecycle management.

## PREREQUISITES VERIFICATION

Before starting, verify these exist:
```bash
ls -l scripts/automated_collection.sh
ls -l scripts/data_lifecycle_manager.py
ls -l scripts/run_verification.py
python -c "from src.utils.storage import get_storage_stats"
python -c "from src.config.regions import get_all_regions"
```

All should exist without errors. If not, complete earlier tasks first.

---

## IMPLEMENTATION STEPS

### Step 1: Create Health Check Script

**File:** `scripts/system_health_check.py`

**Purpose:** Monitor system health (database, data freshness, disk space, verification status)

**Key functions to implement:**
```python
def check_database_connectivity() -> bool
def check_data_freshness() -> bool
def check_disk_space() -> bool
def check_verification_status() -> bool
def generate_health_report() -> bool
```

**Requirements:**
- Use psycopg2 for database checks
- Check latest forecast/observation age
- Warn if disk space < 50GB local, < 100GB NAS
- Generate report to `logs/health_report_TIMESTAMP.txt`
- Return True if all checks pass, False otherwise
- Exit code 0 on healthy, 1 on issues

**Test:**
```bash
chmod +x scripts/system_health_check.py
python scripts/system_health_check.py
cat logs/health_report_*.txt
```

---

### Step 2: Create Systemd Setup Script

**File:** `scripts/setup_systemd_services.py`

**Purpose:** Automatically create and install all systemd service and timer files

**Service/Timer pairs to create:**
1. `weather-collector.service` + `weather-collector.timer`
   - Runs: Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)
   - Executes: `scripts/automated_collection.sh`
   - Memory limit: 2GB

2. `weather-verification.service` + `weather-verification.timer`
   - Runs: Every hour at :15 past
   - Executes: `scripts/run_verification.py --auto --lag-hours 6`
   - Memory limit: 4GB

3. `weather-lifecycle.service` + `weather-lifecycle.timer`
   - Runs: Daily at 02:00 UTC
   - Executes: `scripts/data_lifecycle_manager.py`
   - Memory limit: 1GB

4. `weather-monitor.service` + `weather-monitor.timer`
   - Runs: Every 15 minutes
   - Executes: `scripts/system_health_check.py`
   - Memory limit: 512MB

**Key functions:**
```python
def check_privileges() - Ensure sudo
def create_service_files() - Write to /etc/systemd/system/
def reload_systemd() - systemctl daemon-reload
def enable_and_start_timers() - Enable and start all timers
def show_status() - Display timer and service status
```

**Service file template:**
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

ExecStart=/home/weather-user/projects/weather-model-selector/scripts/automated_collection.sh

StandardOutput=append:/home/weather-user/projects/weather-model-selector/logs/collector.log
StandardError=append:/home/weather-user/projects/weather-model-selector/logs/collector.error.log

Restart=on-failure
RestartSec=300

MemoryLimit=2G
CPUQuota=150%

[Install]
WantedBy=multi-user.target
```

**Timer file template:**
```ini
[Unit]
Description=Weather Model Data Collection Timer
Requires=weather-collector.service

[Timer]
OnCalendar=00/6:00:00
OnBootSec=10min
Persistent=true
AccuracySec=5min

[Install]
WantedBy=timers.target
```

**Requirements:**
- Must be run with sudo
- Write files to `/etc/systemd/system/`
- All files chmod 0644
- User/group must match actual system user
- Paths must be absolute and match project location
- Log setup to `logs/systemd_setup.log`

**Test:**
```bash
# Test without sudo (should fail gracefully)
python scripts/setup_systemd_services.py

# Review before actual install
cat scripts/setup_systemd_services.py
```

---

### Step 3: Make Scripts Executable

```bash
chmod +x scripts/system_health_check.py
chmod +x scripts/setup_systemd_services.py
chmod +x scripts/automated_collection.sh
```

---

### Step 4: Test Health Check Independently

```bash
# Run health check
python scripts/system_health_check.py

# Should create:
# - logs/health.log (general log)
# - logs/health_report_YYYYMMDD_HHMMSS.txt (detailed report)

# Verify report exists and is readable
ls -lh logs/health_report_*.txt
cat logs/health_report_*.txt
```

**Expected output:**
```
======================================================================
WEATHER MODEL SELECTOR - SYSTEM HEALTH REPORT
Generated: 2024-11-18T10:30:00
======================================================================

CHECK RESULTS:
----------------------------------------------------------------------
Database Connectivity.................................... PASS
Data Freshness........................................... PASS
Disk Space............................................... PASS
Verification Status...................................... PASS

======================================================================
OVERALL STATUS: HEALTHY ✓
======================================================================
```

---

### Step 5: Install Systemd Services

**WARNING: Requires sudo privileges**

```bash
# Install services
sudo python scripts/setup_systemd_services.py

# Expected output:
# - Creating systemd service files...
# - Created /etc/systemd/system/weather-collector.service
# - Created /etc/systemd/system/weather-collector.timer
# - [... more services ...]
# - Reloading systemd daemon...
# - Enabling weather-collector.timer...
# - Starting weather-collector.timer...
# - [... more timers ...]
# - Systemd services configured successfully!
```

---

### Step 6: Verify Installation

```bash
# List all weather timers
systemctl list-timers weather-*

# Should show:
# NEXT                         LEFT          LAST PASSED UNIT                        ACTIVATES
# Mon 2024-11-18 12:00:00 UTC  1h 30min left -    -      weather-collector.timer    weather-collector.service
# Mon 2024-11-18 10:45:00 UTC  15min left    -    -      weather-monitor.timer      weather-monitor.service
# [...]

# Check service status
systemctl status weather-collector.service
systemctl status weather-verification.service
systemctl status weather-lifecycle.service
systemctl status weather-monitor.service

# All should show "loaded" and timers should show "active (waiting)"
```

---

### Step 7: Manual Service Test

```bash
# Test data collection service
sudo systemctl start weather-collector.service

# Wait for completion (~5-10 minutes), then check
sudo systemctl status weather-collector.service

# View logs
sudo journalctl -u weather-collector.service -n 100

# Verify data was collected
psql -d weather_db -c "SELECT COUNT(*), MAX(init_time) FROM model_forecasts WHERE init_time > NOW() - INTERVAL '1 hour';"

# Test verification service
sudo systemctl start weather-verification.service
sudo journalctl -u weather-verification.service -n 50

# Test lifecycle service
sudo systemctl start weather-lifecycle.service
sudo journalctl -u weather-lifecycle.service -n 50

# Test monitoring service
sudo systemctl start weather-monitor.service
sudo journalctl -u weather-monitor.service -n 20
```

---

### Step 8: Monitoring Commands

```bash
# Watch timers in real-time (updates every 60 seconds)
watch -n 60 'systemctl list-timers weather-*'

# Follow collector logs in real-time
journalctl -u weather-collector.service -f

# Follow all weather service logs
journalctl -u weather-* -f

# Check last health report
cat $(ls -t logs/health_report_*.txt | head -1)
```

---

## SUCCESS CRITERIA

Verify all these before considering Task 10 complete:

- [ ] `scripts/system_health_check.py` exists and runs successfully
- [ ] `scripts/setup_systemd_services.py` exists and can generate service files
- [ ] Health check generates report in `logs/health_report_*.txt`
- [ ] 4 service files created in `/etc/systemd/system/`
- [ ] 4 timer files created in `/etc/systemd/system/`
- [ ] `systemctl list-timers weather-*` shows all 4 timers active
- [ ] Manual test of each service succeeds
- [ ] Logs visible via `journalctl -u weather-*`
- [ ] Data collection runs and stores data in database
- [ ] Verification runs and calculates metrics
- [ ] System survives reboot (timers start automatically)

---

## COMMON ISSUES & SOLUTIONS

### Issue: "Permission denied" when running setup script
**Solution:** Must run with sudo: `sudo python scripts/setup_systemd_services.py`

### Issue: Service fails immediately
**Solution:** 
```bash
# Check logs
sudo journalctl -u weather-collector.service -n 100

# Verify paths in service file match actual project location
sudo cat /etc/systemd/system/weather-collector.service

# Verify user exists
id weather-user

# Check file permissions
ls -la scripts/automated_collection.sh
```

### Issue: Timer not triggering
**Solution:**
```bash
# Reload systemd
sudo systemctl daemon-reload

# Restart timer
sudo systemctl restart weather-collector.timer

# Verify timer is active
systemctl is-active weather-collector.timer
```

### Issue: Database connection fails in service
**Solution:**
```bash
# Verify .env file exists and is readable
ls -la .env

# Test database connectivity manually
psql -d weather_db -c "SELECT 1;"

# Ensure PostgreSQL starts before services
sudo systemctl status postgresql
```

---

## COMPLETION CHECKLIST

Task 10 is complete when:

1. **Scripts created:**
   - ✅ `scripts/system_health_check.py` (executable)
   - ✅ `scripts/setup_systemd_services.py` (executable)

2. **Systemd files installed:**
   - ✅ `/etc/systemd/system/weather-collector.service`
   - ✅ `/etc/systemd/system/weather-collector.timer`
   - ✅ `/etc/systemd/system/weather-verification.service`
   - ✅ `/etc/systemd/system/weather-verification.timer`
   - ✅ `/etc/systemd/system/weather-lifecycle.service`
   - ✅ `/etc/systemd/system/weather-lifecycle.timer`
   - ✅ `/etc/systemd/system/weather-monitor.service`
   - ✅ `/etc/systemd/system/weather-monitor.timer`

3. **Services operational:**
   - ✅ All timers enabled and active
   - ✅ Manual service tests pass
   - ✅ Logs accessible via journalctl
   - ✅ Data being collected automatically

4. **Validation:**
   - ✅ Health check passes
   - ✅ Latest forecast < 12 hours old
   - ✅ Latest observation < 2 hours old
   - ✅ Disk space adequate
   - ✅ Verification running

---

## NEXT STEPS AFTER COMPLETION

1. **Monitor for 24 hours:**
   ```bash
   # Check every few hours
   systemctl list-timers weather-*
   cat $(ls -t logs/health_report_*.txt | head -1)
   ```

2. **Verify data accumulation:**
   ```bash
   psql -d weather_db -c "SELECT model_name, COUNT(*), MAX(init_time) FROM model_forecasts GROUP BY model_name;"
   ```

3. **Update project status:**
   - Mark Task 10 complete
   - Document any custom configurations
   - Note any issues for future reference

4. **Phase 0 completion:**
   - Review all 10 tasks complete
   - Run comprehensive system test
   - Prepare for Phase 1 planning

---

## USEFUL SYSTEMD COMMANDS

```bash
# Start/stop services
sudo systemctl start weather-collector.service
sudo systemctl stop weather-collector.timer

# Enable/disable (for boot)
sudo systemctl enable weather-collector.timer
sudo systemctl disable weather-collector.timer

# Restart
sudo systemctl restart weather-collector.service

# View logs
journalctl -u weather-collector.service -n 100
journalctl -u weather-collector.service --since "1 hour ago"
journalctl -u weather-collector.service -f

# Check status
systemctl status weather-*.service weather-*.timer
systemctl is-active weather-collector.timer
systemctl list-timers --all

# Reload after changes
sudo systemctl daemon-reload
```

---

## ESTIMATED TIME

**Total:** 30-45 minutes

- Create health check script: 15-20 min
- Create setup script: 15-20 min  
- Install and test: 10-15 min

---

## DETAILED INSTRUCTION REFERENCE

For complete implementation details, see:
- Full instructions: `instruction_10_systemd_automation.md`
- Complete task list: `instruction_readme_COMPLETE.md`
- Phase 0 roadmap: `Weather_Model_Selection_System_-_Development_Roadmap.tsx`

---

**START IMPLEMENTATION NOW**

Begin with Step 1: Create `scripts/system_health_check.py`
