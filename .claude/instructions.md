# Weather Model Selector - Project Instructions

**Auto-read by Claude Code at start of every conversation**

---

## Project Overview

This is a weather model verification system that collects forecasts from GFS and NAM models, gathers observations from METAR and NDBC buoys, and verifies forecast accuracy using both statistical metrics (MAE, RMSE) and decision-relevant metrics (CSI, Hit Rate, FAR).

**Current Phase:** Phase 0 (MVP) - ~85% complete
**Last Completed:** Task 8/9 - Observation collectors + Verification engine
**Next Task:** Dashboard and model selection logic

---

## System Architecture

### Database
- **PostgreSQL with TimescaleDB** extension (database: weather_nas)
- Always use `src.utils.database.get_db_connection()` for database access
- Hypertables: `model_forecasts`, `observations`, `verification_scores`

### Storage Tiers
- **Local** (7 days hot data): `data/raw/`, `data/processed/`
- **NAS** (30 days): `/tmp/weather-nas-test` (or configured path)
- **Cloud** (permanent metrics only): S3/Azure via `src.utils.cloud_backup`

### Models
- **GFS**: Global model, 0.25° resolution, 4 runs/day (00, 06, 12, 18 UTC)
- **NAM**: Regional high-res, 12km resolution, 4 runs/day
- **Regions**: Southern CA, Colorado, Great Lakes, Gulf Coast, Pacific NW

### Observations
- **METAR**: Airport observations (temperature, wind, pressure)
- **NDBC**: Buoy observations (marine conditions)

---

## Important Conventions

### Data Standards
- **MSLP values**: Stored in Pascals (101300 Pa = 1013 hPa)
- **Temperature**: Kelvin in database, convert for display
- **Wind**: m/s in database, convert to knots as needed
- **Spatial matching**: 50km threshold (haversine distance)
- **Temporal matching**: 1 hour threshold

### Verification Metrics
- **Statistical**: MAE, RMSE, Bias (for model diagnosis)
- **Decision**: CSI, Hit Rate, FAR (for operational value)
- **Priority**: Decision metrics > statistical metrics
- **Focus**: Threshold-based verification (32°F, 34kt, etc.)

### Verification System (Completed ✅)
- **Spatial matching**: Haversine distance ≤ 50km between forecast and observation
- **Temporal matching**: |Δt| ≤ 1 hour between forecast valid time and observation time
- **Database records**: 473 verification pairs (GFS: 170, NAM: 303)
- **Performance baseline**: NAM slightly better (MAE: 3.2 hPa vs GFS: 3.3 hPa for MSLP)
- **CLI tool**: `scripts/run_verification.py` with decision metrics display
- **Automated**: Integrated into `scripts/automated_collection.sh`

---

## Git Workflow - MANDATORY RULES

### 🔴 Critical Rules (Never Break)

1. **NEVER commit directly to `main` branch** _(enforced going forward - previous work committed to main for initial setup)_
2. **ALWAYS work on feature branches**
3. **ALWAYS use conventional commit format**
4. **ALWAYS commit after each logical unit of work (3-5 commits per session)**
5. **ALWAYS push at end of session**

> **Note**: Initial verification system (commit 4f40265) was committed directly to `main` during setup phase. Going forward, ALL work must be on feature branches following the workflow below.

### Before Starting Work

```bash
# 1. Check status
git status
git branch

# 2. Ensure main is updated
git checkout main
git pull origin main

# 3. Create feature branch
git checkout -b task-XX-description

# Examples:
git checkout -b task-08-metar-collector
git checkout -b fix-storage-path-bug
git checkout -b feat-verification-metrics
```

### Conventional Commit Format

**Format:** `type(scope): description`

**Valid Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `test` - Tests
- `refactor` - Code restructuring
- `chore` - Maintenance
- `style` - Formatting
- `perf` - Performance

**Valid Scopes:**
- `collectors` - GFS, NAM, METAR, buoys
- `verification` - Metrics, verification engine
- `storage` - Local, NAS, cloud
- `database` - Schema, queries
- `api` - REST endpoints
- `ml` - ML models
- `utils` - Utilities
- `config` - Configuration
- `tests` - Test suites
- `docs` - Documentation

**Examples:**
```bash
git commit -m "feat(collectors): add METAR data collection for 5 regions"
git commit -m "fix(storage): correct NAS path resolution for raw data"
git commit -m "test(collectors): add unit tests for GFS data parsing"
git commit -m "docs(readme): add verification methodology explanation"
```

### During Development

- Commit every 30-60 minutes OR after completing a logical unit
- Run tests before committing: `python -m pytest tests/`
- Keep commits focused (one logical change per commit)
- Write descriptive commit messages

### At End of Session

```bash
# 1. Ensure all work committed
git status  # Should be clean

# 2. Push feature branch
git push origin task-XX-description

# 3. Update SESSION_NOTES.md
# Document what you accomplished and what's next
```

### Merging to Main (Only When Complete)

```bash
# 1. Tests must pass
python -m pytest tests/

# 2. Update main and rebase
git checkout main
git pull origin main
git checkout task-XX-description
git rebase main

# 3. Merge via fast-forward
git checkout main
git merge --ff-only task-XX-description

# 4. Push and cleanup
git push origin main
git branch -d task-XX-description
git push origin --delete task-XX-description
```

---

## File Structure

```
weather-model-selector/
├── src/
│   ├── collectors/          # Data collection scripts
│   │   ├── gfs_collector.py      # ✅ Global model (0.25°)
│   │   ├── nam_collector.py      # ✅ Regional high-res (12km)
│   │   ├── metar_collector.py    # ✅ Airport observations
│   │   └── buoy_collector.py     # ✅ Marine buoy observations
│   ├── verification/        # Forecast verification ✅
│   │   └── forecast_verification.py  # Dual-metric verification engine
│   ├── utils/              # Utilities
│   │   ├── storage.py      # Storage management
│   │   ├── database.py     # Database connections
│   │   └── cloud_backup.py # Cloud backup
│   └── config/             # Configuration
│       ├── settings.py
│       └── regions.py
├── scripts/                # Operational scripts
│   ├── automated_collection.sh
│   ├── run_verification.py
│   └── data_lifecycle_manager.py
├── tests/                  # Test suites
├── docs/                   # Documentation
│   └── implementation-instructions/  # Task instructions
├── data/                   # Data storage (not in git)
└── logs/                   # Log files (not in git)
```

---

## Common Commands

### Data Collection
```bash
# Automated collection (all models)
bash scripts/automated_collection.sh

# Manual GFS collection
python src/collectors/gfs_collector.py --region southern_ca

# Manual NAM collection
python src/collectors/nam_collector.py --region all
```

### Verification
```bash
# Run verification with decision metrics
python scripts/run_verification.py --model GFS --hours-back 24 --show-decision-metrics

# Quick verification test
bash scripts/test_collection.sh
```

### Database
```bash
# Check record counts
psql $DATABASE_URL -c "SELECT COUNT(*) FROM model_forecasts;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM observations;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM verification_scores;"

# Initialize/reset database
python scripts/init_db.py
python scripts/fix_db.py
```

### Storage Management
```bash
# Check storage status
python scripts/storage_dashboard.py

# Run lifecycle management
python scripts/data_lifecycle_manager.py --dry-run

# Emergency cleanup (free 50 GB)
python scripts/data_lifecycle_manager.py --emergency-cleanup 50
```

### Testing
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_metar_collector.py -v

# Run with coverage
python -m pytest --cov=src tests/
```

### Git Workflow Helper
```bash
# Check status
./git_workflow.sh status

# Start new task
./git_workflow.sh start task-name

# Commit with validation
./git_workflow.sh commit "feat(scope): description"

# End session
./git_workflow.sh session-end
```

---

## Development Standards

### Code Quality

1. **Type Hints**: Use for all function parameters and returns
2. **Docstrings**: Required for all public functions
3. **Error Handling**: Always use try-except with logging
4. **Logging**: Use `loguru` logger, not print statements
5. **Testing**: Write tests for new functionality

### Example Good Code

```python
from typing import Dict, List, Optional
from datetime import datetime
from loguru import logger

def calculate_csi(
    forecasts: List[float],
    observations: List[float],
    threshold: float
) -> float:
    """
    Calculate Critical Success Index for threshold-based decisions.
    
    Args:
        forecasts: List of forecast values
        observations: List of observed values
        threshold: Decision threshold
        
    Returns:
        CSI value between 0 and 1
        
    Raises:
        ValueError: If lists have different lengths
    """
    try:
        if len(forecasts) != len(observations):
            raise ValueError("Lists must have same length")
        
        hits = sum(1 for f, o in zip(forecasts, observations) 
                  if f >= threshold and o >= threshold)
        misses = sum(1 for f, o in zip(forecasts, observations)
                    if f < threshold and o >= threshold)
        false_alarms = sum(1 for f, o in zip(forecasts, observations)
                          if f >= threshold and o < threshold)
        
        total = hits + misses + false_alarms
        csi = hits / total if total > 0 else 0.0
        
        logger.info(f"CSI calculated: {csi:.3f} for threshold {threshold}")
        return csi
        
    except Exception as e:
        logger.error(f"CSI calculation failed: {e}")
        raise
```

---

## Session Workflow

### Starting a Session

1. Check git status: `git status`
2. Review SESSION_NOTES.md for last session's progress
3. Create/switch to feature branch
4. Begin work

### During Session

1. Commit frequently (every 30-60 min)
2. Run tests before each commit
3. Keep commits focused and well-described
4. Update documentation as you go

### Ending Session

1. Commit all changes
2. Push feature branch
3. Update SESSION_NOTES.md with:
   - What you accomplished
   - What's next
   - Any blockers or issues
4. Run final checks: `git status`, `./git_workflow.sh status`

---

## Current Priorities

### Completed (Phase 0)
- ✅ Storage architecture (local, NAS, cloud)
- ✅ GFS collector (5 regions, 0.25° resolution)
- ✅ NAM collector (5 regions, 12km resolution, fixed 2D lat/lon handling)
- ✅ Database schema with TimescaleDB hypertables
- ✅ Region configuration system
- ✅ Storage lifecycle management
- ✅ Verification methodology documentation
- ✅ **METAR observation collector** (284 observations collected)
- ✅ **NDBC buoy observation collector** (414 observations collected)
- ✅ **Verification engine** with spatial/temporal matching (haversine distance)
- ✅ **Decision metrics** (CSI, Hit Rate, FAR) + statistical metrics (MAE, RMSE, Bias)
- ✅ **Automated collection script** with forecasts + observations
- ✅ **Verification CLI tool** (`scripts/run_verification.py`)
- ✅ **Database schema updates** (threshold_verification table, skill_metrics_summary view)

### Next Tasks (Priority Order)
1. **Dashboard**: Monitoring and visualization of verification metrics
2. **Model Selection Logic**: Use decision metrics to choose best model for each situation
3. **Additional Variables**: Extend beyond MSLP to temperature, wind, precipitation
4. **Expand Coverage**: Add more regions and observation sources
5. **ML Enhancement**: Train models to predict forecast skill

### Current Focus
Dashboard development and model selection algorithm based on verification results.

---

## Key Resources

- **Roadmap**: `Weather_Model_Selection_System_-_Development_Roadmap.tsx`
- **Verification Methodology**: `verification_methodology.md`
- **Git Quick Reference**: `git_quick_reference.md`
- **Session Notes**: `SESSION_NOTES.md`

---

## Troubleshooting

### Database Connection Issues
```python
# Always use context manager
from src.utils.database import get_db_connection

with get_db_connection() as conn:
    cur = conn.cursor()
    # Your queries here
    cur.close()
```

### Storage Issues
```bash
# Check available space
df -h

# Check storage stats
python scripts/storage_dashboard.py

# Emergency cleanup
python scripts/data_lifecycle_manager.py --emergency-cleanup 50
```

### Git Issues
```bash
# Accidentally committed to main?
git reset --soft HEAD~1
git checkout -b fix-my-mistake
git commit -m "proper message"

# Need to fix commit message?
git commit --amend -m "corrected message"

# Lost changes?
git reflog  # See recent actions
```

---

## Remember

- **Decision value > Statistical accuracy**: We care about helping users make better decisions, not just lower RMSE
- **Threshold-based verification**: Focus on decision points (32°F, 34kt, etc.)
- **Professional Git practices**: Every commit matters for future maintainability
- **Test before committing**: Broken code doesn't go into the repo
- **Document as you go**: Future you will thank present you

---

**This file is automatically read at the start of every Claude Code conversation. No need to remind me about these practices!**
