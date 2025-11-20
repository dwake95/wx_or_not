# Phase 0 Implementation Instructions - COMPLETE TASK LIST

This directory contains detailed instructions for Claude Code to implement the Weather Model Selection System infrastructure for Phase 0: Foundation & MVP.

---

## Implementation Order

Execute these tasks in sequence to complete Phase 0:

### Infrastructure Tasks (1-7)

1. **01-storage-architecture.md** - Foundation: Multi-tier storage management system
2. **02-nas-integration.md** - Set up NAS connectivity and directory structure
3. **03-cloud-backup.md** - Cloud backup system for permanent metrics storage
4. **04-data-lifecycle-manager.md** - Automated data retention and backup scheduler
5. **05-updated-collectors.md** - Modify data collectors to use tiered storage
6. **06-region-configuration.md** - Geographic region configuration system
7. **07-monitoring-dashboard.md** - System monitoring and status dashboard

### Verification & Quality Tasks (8-9)

8. **08-verification-engine.md** - Enhanced verification with threshold-based decision metrics
9. **09-threshold-database.md** - Asset-specific threshold configuration and management

### Deployment & Automation Task (10)

10. **10-systemd-automation.md** - Production systemd services and automated scheduling

---

## Phase 0 Component Mapping

Based on the roadmap, here's how tasks map to Phase 0 deliverables:

| Deliverable | Implemented By | Status |
|------------|----------------|--------|
| Automated data collection for GFS, NAM, HRRR | Tasks 5, 10 | ✓ |
| METAR and buoy observation ingestion | Tasks 5, 10 | ✓ |
| PostgreSQL + TimescaleDB database | Task 1 (init_db.py) | ✓ |
| Basic verification engine | Task 8 | ✓ |
| Simple conditional skill database | Task 8 | ✓ |
| Proof-of-concept dashboard | Task 7 | ✓ |
| Initial threshold database (3-5 asset types) | Task 9 | ✓ |
| Documentation and deployment scripts | All tasks | ✓ |
| Automated scheduling (cron/systemd) | Task 10 | **← YOU ARE HERE** |

---

## How to Use with Claude Code

### Setup
```bash
cd ~/projects/weather-model-selector
source venv/bin/activate
claude-code
```

### Execute Tasks

In Claude Code, for each task:
```
Read and implement the instructions in docs/implementation-instructions/10-systemd-automation.md
```

After completion, commit changes:
```bash
git add scripts/setup_systemd_services.py scripts/system_health_check.py
git commit -m "Implement Task 10: Systemd automation"
```

---

## Testing After Each Task

After implementing each task:

1. **Syntax check:**
   ```bash
   python -m py_compile src/path/to/file.py
   ```

2. **Import test:**
   ```bash
   python -c "from src.path.to.module import *"
   ```

3. **Run verification:**
   Follow the requirements section in each instruction file

---

## Dependencies

Core dependencies (should already be installed):
```bash
# Already in requirements.txt
pip install psycopg2-binary sqlalchemy pandas numpy xarray
pip install metpy requests loguru python-dotenv
pip install fastapi uvicorn streamlit plotly
```

Additional for Tasks 1-10:
```bash
pip install boto3 azure-storage-blob pyyaml rich psutil
pip freeze > requirements.txt
```

---

## What Each Task Creates

### Infrastructure Layer (Tasks 1-7)
- **Task 1:** `src/utils/storage.py` - Storage management utilities
- **Task 2:** `scripts/setup_nas.py` - NAS setup wizard
- **Task 3:** `src/utils/cloud_backup.py` - Cloud backup functions
- **Task 4:** `scripts/data_lifecycle_manager.py` - Automated lifecycle management
- **Task 5:** Modified collectors + `src/collectors/nam_collector.py`
- **Task 6:** `src/config/regions.py` - Region configuration
- **Task 7:** `scripts/storage_dashboard.py` - Monitoring dashboard

### Verification Layer (Tasks 8-9)
- **Task 8:** `src/verification/threshold_metrics.py` - Decision-relevant verification
- **Task 8:** `scripts/update_verification_schema.sql` - Database schema updates
- **Task 9:** `src/config/thresholds.py` - Threshold configuration system
- **Task 9:** `scripts/populate_thresholds.py` - Initial threshold data

### Automation Layer (Task 10)
- **Task 10:** `scripts/setup_systemd_services.py` - Service installer
- **Task 10:** `scripts/system_health_check.py` - Health monitoring
- **Task 10:** `/etc/systemd/system/weather-*.service` - Service definitions
- **Task 10:** `/etc/systemd/system/weather-*.timer` - Timer definitions

---

## Expected Timeline

### Infrastructure Setup (Tasks 1-7): ~2-3 hours
- Task 1: ~15-20 minutes
- Task 2: ~10-15 minutes  
- Task 3: ~20-25 minutes
- Task 4: ~20-25 minutes
- Task 5: ~25-30 minutes
- Task 6: ~10-15 minutes
- Task 7: ~15-20 minutes

### Verification & Quality (Tasks 8-9): ~1-1.5 hours
- Task 8: ~30-40 minutes
- Task 9: ~20-30 minutes

### Automation & Deployment (Task 10): ~30-45 minutes
- Task 10: ~30-45 minutes

**Total Phase 0 Implementation:** ~4-5 hours

---

## Post-Implementation Steps

### 1. Configure NAS
```bash
python scripts/setup_nas.py
```

### 2. Update .env with credentials
```bash
# Add to .env file
NAS_STORAGE_PATH=/mnt/nas/weather-data
NAS_ENABLED=true
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
CLOUD_PROVIDER=aws
RETENTION_RAW_FORECASTS_DAYS=14
RETENTION_OBSERVATIONS_DAYS=30
```

### 3. Initialize storage
```bash
python -c "from src.utils.storage import get_storage_stats; print(get_storage_stats())"
```

### 4. Populate threshold database
```bash
python scripts/populate_thresholds.py
```

### 5. Install systemd services (requires sudo)
```bash
sudo python scripts/setup_systemd_services.py
```

### 6. Verify automated operations
```bash
# Check timers
systemctl list-timers weather-*

# Check service status
systemctl status weather-collector.service

# Follow logs
journalctl -u weather-collector.service -f
```

---

## System Architecture After Phase 0

```
┌─────────────────────────────────────────────────────────┐
│                   SYSTEMD ORCHESTRATION                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Collector   │  │ Verification │  │  Lifecycle   │ │
│  │  (6 hours)   │  │  (hourly)    │  │   (daily)    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│               DATA COLLECTION LAYER                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │   GFS    │  │   NAM    │  │   METAR  │             │
│  │  (6hr)   │  │  (6hr)   │  │  (hourly)│             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│               STORAGE MANAGEMENT                         │
│  ┌───────────┐  ┌──────────┐  ┌──────────┐            │
│  │   LOCAL   │→ │   NAS    │→ │  CLOUD   │            │
│  │  (7 days) │  │ (30 days)│  │ (forever)│            │
│  └───────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│         POSTGRESQL + TIMESCALEDB DATABASE                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Forecasts  │  │Observations │  │Verification │   │
│  │  (time-     │  │  (time-     │  │  Metrics    │   │
│  │  series)    │  │   series)   │  │  (rolled up)│   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│            VERIFICATION ENGINE                           │
│  ┌─────────────────┐  ┌─────────────────┐             │
│  │  Statistical    │  │  Decision       │             │
│  │  Metrics        │  │  Metrics        │             │
│  │  (MAE, RMSE)    │  │  (CSI, Hit Rate)│             │
│  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│            THRESHOLD DATABASE                            │
│  Asset-specific decision thresholds for:                 │
│  • Heavy Trucks (wind > 35 kt)                          │
│  • Maritime (wind > 34 kt)                              │
│  • Construction (wind > 25 kt)                          │
│  • Road Treatment (temp < 32°F)                         │
│  • Agriculture (temp < 32°F)                            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│          MONITORING & DASHBOARDS                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Storage    │  │  Streamlit  │  │  Health     │   │
│  │  Dashboard  │  │  Dashboard  │  │  Checks     │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Verification Checklist

Before considering Phase 0 complete, verify:

### Data Collection
- [ ] GFS forecasts collecting every 6 hours
- [ ] NAM forecasts collecting every 6 hours  
- [ ] METAR observations collecting hourly
- [ ] Buoy observations collecting hourly
- [ ] 5-10 geographic regions configured
- [ ] Data stored in PostgreSQL/TimescaleDB

### Storage Management
- [ ] Local storage tier operational
- [ ] NAS storage tier configured (if enabled)
- [ ] Cloud backup configured (for metrics)
- [ ] Data lifecycle manager running daily
- [ ] Retention policies enforced

### Verification System
- [ ] Verification runs hourly with 6-hour lag
- [ ] Statistical metrics calculated (MAE, RMSE, bias)
- [ ] Decision metrics calculated (CSI, hit rate, FAR)
- [ ] Threshold verification operational
- [ ] Results stored in database

### Thresholds & Configuration
- [ ] At least 3-5 asset types configured
- [ ] Wind thresholds defined
- [ ] Temperature thresholds defined
- [ ] Thresholds linked to operational decisions

### Automation
- [ ] Systemd services installed and enabled
- [ ] Timers running on schedule
- [ ] Health checks running every 15 minutes
- [ ] Logs accessible via journalctl
- [ ] Services restart on failure

### Monitoring
- [ ] Storage dashboard accessible
- [ ] Streamlit dashboard showing model performance
- [ ] Health reports generated automatically
- [ ] Disk space monitored
- [ ] Data freshness monitored

### Success Metrics (Phase 0 Goals)
- [ ] Data collection reliability: >95% uptime
- [ ] Forecast-observation pairs collected: >1000/week
- [ ] Verification latency: <6 hours after valid time
- [ ] Dashboard response time: <2 seconds
- [ ] System demonstrates skill difference between models

---

## Troubleshooting Guide

### Common Issues

**Issue: Service won't start**
```bash
# Check logs
sudo journalctl -u weather-collector.service -n 100

# Verify file permissions
ls -la scripts/automated_collection.sh

# Test script manually
bash scripts/automated_collection.sh
```

**Issue: Timer not triggering**
```bash
# Verify timer is active
systemctl is-active weather-collector.timer

# Check next run time
systemctl list-timers weather-collector.timer

# Restart timer
sudo systemctl restart weather-collector.timer
```

**Issue: Database connection fails**
```bash
# Test database connectivity
psql -d weather_db -c "SELECT 1;"

# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify .env configuration
cat .env | grep DB_
```

**Issue: Storage full**
```bash
# Check disk usage
df -h

# Run cleanup manually
python scripts/data_lifecycle_manager.py --emergency-cleanup 50

# Check retention settings
cat .env | grep RETENTION
```

---

## Next Steps: Phase 1

After Phase 0 is complete and stable, Phase 1 focuses on:

1. **Vehicle sensor data integration** (temperature, pressure, wiper activity)
2. **Expanded marine observations** (additional buoys, ship reports)
3. **ML-based model selection engine** (initial version)
4. **Weather regime classification system**
5. **Multi-vintage forecast comparison**
6. **Enhanced conditional skill database**
7. **API v1.0 for external access**

Phase 1 implementation instructions will be in a separate directory.

---

## Support & Resources

**Documentation:**
- Architecture: `docs/architecture/`
- Verification: `verification_methodology.md`
- API: `docs/api/` (Phase 1)

**Scripts:**
- All automation: `scripts/`
- Configuration: `src/config/`
- Utilities: `src/utils/`

**Logs:**
- System logs: `journalctl -u weather-*`
- Application logs: `logs/*.log`
- Health reports: `logs/health_report_*.txt`

**Database:**
- Connection: See `.env` for credentials
- Schema: `scripts/init_db.py`
- Backup: Automated daily via lifecycle manager

---

## Contact & Contribution

This is an internal project. For questions or issues:

1. Check logs: `journalctl -u weather-* -n 100`
2. Run health check: `python scripts/system_health_check.py`
3. Review relevant instruction file
4. Check troubleshooting guide above

**System Status Command:**
```bash
# Quick status check
systemctl status weather-*.service weather-*.timer && \
df -h / /mnt/nas/weather-data && \
python scripts/system_health_check.py
```

---

**Phase 0 Status: READY FOR TASK 10 IMPLEMENTATION**

Upon completion of Task 10, Phase 0 will be production-ready for 24/7 automated operations.
