# Weather Model Selection System

**Phase 0 MVP - Production Ready** ✅

Asset-centric weather forecast verification system with intelligent model selection based on decision-relevant metrics.

---

## 🎯 Overview

This system collects weather forecasts from multiple models (GFS, NAM), gathers real-world observations (METAR, NDBC buoys), and verifies forecast accuracy using both traditional statistical metrics and operationally-relevant decision metrics. The goal is to select the best forecast model for each situation based on actual operational value, not just statistical accuracy.

**Core Principle:** *"A forecast's value is measured by the decisions it enables, not just its statistical accuracy."*

---

## ✨ Features

### Data Collection
- **GFS (Global)**: 0.25° resolution, 4 runs/day (00, 06, 12, 18 UTC)
- **NAM (Regional)**: 12km high-resolution, 4 runs/day
- **5 Regions**: Southern CA, Colorado, Great Lakes, Gulf Coast, Pacific NW
- **Observations**: METAR (airports) + NDBC (marine buoys)

### Verification System
- **Statistical Metrics**: MAE, RMSE, Bias (for model diagnosis)
- **Decision Metrics**: CSI, Hit Rate, FAR (for operational value)
- **Threshold-Based**: Evaluates forecasts at decision-critical thresholds
- **Spatial/Temporal Matching**: 50km, 1-hour windows

### Automation
- **Systemd Services**: Production-ready automated scheduling
- **Health Monitoring**: System checks every 15 minutes
- **Data Collection**: Automated every 6 hours
- **Verification**: Hourly for both models
- **Lifecycle Management**: Daily data cleanup

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL with TimescaleDB extension
- 200GB+ disk space (local + NAS)

### Installation

```bash
# Clone repository
git clone https://github.com/dwake95/wx_or_not.git
cd wx_or_not

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your database credentials
```

### Database Setup

```bash
# Initialize database
psql -U postgres -f scripts/init_db.sql

# Apply verification schema
psql -U postgres -d weather_nas -f scripts/update_verification_schema.sql
```

### Install Systemd Services (Production)

```bash
# Install automated services (requires sudo)
sudo venv/bin/python scripts/setup_systemd_services.py

# Verify installation
systemctl list-timers weather-*
```

---

## 📊 System Status

Check system health:

```bash
# Run health check
python scripts/system_health_check.py

# View latest health report
cat $(ls -t logs/health_report_*.txt | head -1)

# Check systemd services
systemctl status weather-*.timer
```

---

## 💻 Usage

### Manual Data Collection

```bash
# Collect all data (GFS, NAM, observations)
bash scripts/automated_collection.sh

# Collect specific model
python src/collectors/gfs_collector_v2.py --region southern_ca
python src/collectors/nam_collector.py --region all

# Collect observations
python src/collectors/metar_collector.py --region all --hours 12
python src/collectors/buoy_collector.py --region all --hours 12

# Quick test collection (single region, 3 forecast hours)
bash scripts/test_collection.sh
```

### Verification

```bash
# Run verification for GFS (last 24 hours)
python scripts/run_verification.py --model GFS --hours-back 24 --show-decision-metrics

# Run verification for NAM
python scripts/run_verification.py --model NAM --hours-back 24 --show-decision-metrics

# Show 7-day skill summary
python scripts/run_verification.py --model GFS --hours-back 1 --skill-summary --dry-run

# Verify specific variable
python scripts/run_verification.py --model GFS --variable temperature_2m --hours-back 48
```

### Monitoring

```bash
# Watch timers in real-time
watch -n 60 'systemctl list-timers weather-*'

# Follow all service logs
journalctl -u weather-* -f

# Follow specific service
journalctl -u weather-collector.service -f
journalctl -u weather-verification.service -f

# Check database statistics
psql -d weather_nas -c "
  SELECT model_name, COUNT(*), MAX(init_time)
  FROM model_forecasts
  GROUP BY model_name;
"

psql -d weather_nas -c "
  SELECT obs_type, COUNT(*), MAX(obs_time)
  FROM observations
  GROUP BY obs_type;
"
```

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Collection Layer                    │
├─────────────────────────────────────────────────────────────┤
│  GFS Collector  │  NAM Collector  │  METAR  │  Buoy Data   │
│   (NOMADS)      │    (NOMADS)     │  (IEM)  │   (NDBC)     │
└────────┬────────────────┬──────────────┬────────────┬───────┘
         │                │              │            │
         └────────────────┴──────────────┴────────────┘
                          │
                ┌─────────▼──────────┐
                │  PostgreSQL +      │
                │  TimescaleDB       │
                │  (weather_nas)     │
                └─────────┬──────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                 │
    ┌────▼─────────┐            ┌─────────▼────────┐
    │ Verification │            │  Storage Tiers   │
    │   Engine     │            ├──────────────────┤
    ├──────────────┤            │ Local: 7 days    │
    │ • Statistical│            │ NAS: 30 days     │
    │ • Decision   │            │ Cloud: Metrics   │
    │ • Spatial    │            └──────────────────┘
    │   Matching   │
    └──────────────┘
```

### Storage Tiers
1. **Local** (7 days hot data): `data/raw/`, `data/processed/`
2. **NAS** (30 days): `/tmp/weather-nas-test` (or configured path)
3. **Cloud** (permanent metrics): S3/Azure via `src.utils.cloud_backup`

### Database Schema
- **model_forecasts**: Forecast data from GFS and NAM
- **observations**: METAR and buoy observations
- **verification_scores**: Statistical verification results
- **threshold_verification**: Decision metric results
- **skill_metrics_summary**: Materialized view for quick queries

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/weather_nas

# Storage
LOCAL_DATA_DIR=./data
NAS_MOUNT_PATH=/tmp/weather-nas-test

# Regions (comma-separated)
REGIONS=southern_ca,colorado,great_lakes,gulf_coast,pacific_nw
```

### Regions Configuration

Located in `src/config/regions.py`:
- Southern California (32-35°N, 115-121°W)
- Colorado (37-41°N, 102-109°W)
- Great Lakes (41-49°N, 75-92°W)
- Gulf Coast (24-31°N, 80-98°W)
- Pacific Northwest (42-49°N, 116-125°W)

---

## 📈 Verification Metrics

### Statistical Metrics (Model Diagnosis)
- **MAE** (Mean Absolute Error): Average forecast error magnitude
- **RMSE** (Root Mean Square Error): Penalizes large errors
- **Bias**: Systematic over/under forecasting

### Decision Metrics (Operational Value) - *Weighted Higher*
- **CSI** (Critical Success Index): Key metric for decision-making (0-1, higher better)
- **Hit Rate (POD)**: Probability of detection (want HIGH for safety)
- **False Alarm Rate**: Fraction of warnings that were false (want LOW)
- **False Alarm Ratio**: FAR relative to all forecasts (want LOW)

**Example Interpretation:**
- CSI = 0.7 → Excellent operational forecast
- Hit Rate = 0.9 → Catches 90% of events (good for safety)
- FAR = 0.2 → 20% false alarms (acceptable operational cost)

---

## 🤖 Systemd Services

### Active Services

| Service | Schedule | Purpose | Resources |
|---------|----------|---------|-----------|
| **weather-collector** | Every 6 hours | Collect GFS + NAM forecasts + observations | 2GB mem, 150% CPU |
| **weather-verification** | Hourly | Verify both models against observations | 4GB mem, 200% CPU |
| **weather-lifecycle** | Daily 02:00 UTC | Cleanup old data, manage storage | 1GB mem, 100% CPU |
| **weather-monitor** | Every 15 minutes | System health checks | 512MB mem, 50% CPU |

### Service Management

```bash
# Start/stop services
sudo systemctl start weather-collector.service
sudo systemctl stop weather-collector.timer

# Enable/disable (for boot)
sudo systemctl enable weather-collector.timer
sudo systemctl disable weather-collector.timer

# Restart service
sudo systemctl restart weather-collector.service

# Check status
systemctl status weather-collector.timer
systemctl is-active weather-monitor.timer

# Reload after configuration changes
sudo systemctl daemon-reload
```

---

## 📁 Project Structure

```
weather-model-selector/
├── src/
│   ├── collectors/          # Data collection (GFS, NAM, METAR, Buoy)
│   ├── verification/        # Forecast verification engine
│   ├── utils/              # Utilities (storage, database, cloud)
│   ├── config/             # Configuration (settings, regions)
│   ├── processors/         # Data processing
│   ├── api/                # REST API (future)
│   └── ml/                 # ML models (future)
├── scripts/                # Operational scripts
│   ├── automated_collection.sh      # Main collection script
│   ├── run_verification.py          # Verification CLI
│   ├── system_health_check.py       # Health monitoring
│   ├── setup_systemd_services.py    # Service installer
│   ├── data_lifecycle_manager.py    # Storage management
│   └── test_collection.sh           # Quick test script
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── docs/                   # Documentation
│   └── implementation-instructions/  # Phase guides
├── logs/                   # Log files
│   ├── health_report_*.txt          # Health check reports
│   ├── collector.log                # Collection logs
│   └── verification.log             # Verification logs
├── data/                   # Data storage (not in git)
├── .claude/               # Claude Code configuration
│   └── instructions.md    # Project instructions
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
└── README.md             # This file
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test suite
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v

# Run with coverage
python -m pytest --cov=src tests/

# Test health check
python scripts/system_health_check.py

# Test collection (single region, fast)
bash scripts/test_collection.sh
```

---

## 🔍 Troubleshooting

### Database Connection Issues
```bash
# Test connection
psql -d weather_nas -c "SELECT 1;"

# Check if PostgreSQL is running
sudo systemctl status postgresql

# Verify database exists
psql -U postgres -l | grep weather
```

### Service Not Running
```bash
# Check service logs
sudo journalctl -u weather-collector.service -n 100

# Verify paths in service file
sudo cat /etc/systemd/system/weather-collector.service

# Check file permissions
ls -la scripts/automated_collection.sh

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart weather-collector.timer
```

### Disk Space Issues
```bash
# Check available space
df -h

# Check storage stats
python scripts/storage_dashboard.py

# Emergency cleanup (free 50GB)
python scripts/data_lifecycle_manager.py --emergency-cleanup 50
```

---

## 📊 Performance Baselines (Phase 0)

Current system performance with ~473 verification pairs:

| Model | MAE (hPa) | RMSE (hPa) | Pairs | Performance |
|-------|-----------|------------|-------|-------------|
| **NAM** | 3.2 | 4.2 | 303 | ⭐ Better (higher resolution) |
| **GFS** | 3.3 | 4.5 | 170 | Good (global coverage) |

**Note**: NAM shows slightly better accuracy due to higher spatial resolution (12km vs 25km).

---

## 🗺️ Development Roadmap

### ✅ Phase 0: MVP (Complete)
- Multi-model data collection (GFS, NAM)
- Observation systems (METAR, Buoy)
- Dual-metric verification (Statistical + Decision)
- Production automation with systemd
- Health monitoring and lifecycle management

### 🔜 Phase 1: Enhanced Intelligence (Next)
- Dashboard and visualization
- Real-time model selection based on verification metrics
- Additional weather variables (temperature, wind, precipitation)
- Expanded geographical coverage
- API endpoints for forecast delivery

### 🔮 Phase 2: ML Enhancement (Future)
- Machine learning models to predict forecast skill
- Ensemble forecast generation
- Adaptive threshold tuning
- Historical skill-based weighting

---

## 🤝 Contributing

See [.claude/instructions.md](.claude/instructions.md) for development guidelines including:
- Git workflow (feature branches, conventional commits)
- Code quality standards
- Testing requirements
- Documentation practices

---

## 📄 License

[Your License Here]

---

## 🔗 Links

- **Repository**: https://github.com/dwake95/wx_or_not
- **NOAA Data Sources**:
  - NOMADS: https://nomads.ncep.noaa.gov/
  - Iowa State Mesonet: https://mesonet.agron.iastate.edu/
  - NDBC Buoys: https://www.ndbc.noaa.gov/

---

## 📞 Support

For issues and questions:
- Open an issue on GitHub
- Check health reports: `logs/health_report_*.txt`
- Review service logs: `journalctl -u weather-*`

---

**Built with Claude Code** 🤖
