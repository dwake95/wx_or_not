# Implementation Instructions

This directory contains detailed instructions for Claude Code to implement the weather model selection system infrastructure.

## Implementation Order

Execute these tasks in sequence:

1. **01-storage-architecture.md** - Foundation: Multi-tier storage management system
2. **02-nas-integration.md** - Set up NAS connectivity and directory structure
3. **03-cloud-backup.md** - Cloud backup system for permanent metrics storage
4. **04-data-lifecycle-manager.md** - Automated data retention and backup scheduler
5. **05-updated-collectors.md** - Modify data collectors to use tiered storage
6. **06-region-configuration.md** - Geographic region configuration system
7. **07-monitoring-dashboard.md** - System monitoring and status dashboard

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
Read and implement the instructions in docs/implementation-instructions/01-storage-architecture.md
```

After completion, commit changes:
```bash
git add src/utils/storage.py
git commit -m "Implement Task 1: Storage architecture"
```

Then proceed to the next task:
```
Read and implement the instructions in docs/implementation-instructions/02-nas-integration.md
```

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

## Dependencies

After completing all tasks, install additional dependencies:

```bash
pip install boto3 azure-storage-blob pyyaml rich streamlit
pip freeze > requirements.txt
```

## What Each Task Creates

- **Task 1:** `src/utils/storage.py` - Storage management utilities
- **Task 2:** `scripts/setup_nas.py` - NAS setup wizard
- **Task 3:** `src/utils/cloud_backup.py` - Cloud backup functions
- **Task 4:** `scripts/data_lifecycle_manager.py` - Automated lifecycle management
- **Task 5:** Modified collectors + `src/collectors/nam_collector.py`
- **Task 6:** `src/config/regions.py` - Region configuration
- **Task 7:** `scripts/storage_dashboard.py` - Monitoring dashboard

## Expected Timeline

- Task 1: ~15-20 minutes
- Task 2: ~10-15 minutes  
- Task 3: ~20-25 minutes
- Task 4: ~20-25 minutes
- Task 5: ~25-30 minutes
- Task 6: ~10-15 minutes
- Task 7: ~15-20 minutes

**Total:** ~2-3 hours for complete implementation

## Post-Implementation Steps

1. **Configure NAS:**
   ```bash
   python scripts/setup_nas.py
   ```

2. **Update .env with credentials:**
   - Add AWS or Azure credentials
   - Configure NAS path
   - Set retention periods

3. **Initialize storage:**
   ```bash
   python -c "from src.utils.storage import get_storage_stats; print(get_storage_stats())"
   ```

4. **Set up cron jobs:**
   ```bash
   crontab -e
   # Add data collection and lifecycle management jobs
   ```

5. **Start collecting data:**
   ```bash
   python src/collectors/gfs_collector.py --region all
   ```

## Architecture Overview

```
┌─────────────────┐
│  Data Sources   │ (NOAA, observations)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Collectors    │ (GFS, NAM, METAR, Buoys)
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  LOCAL Storage  │────▶│ NAS Storage  │
│   (7 days hot)  │     │  (30 days)   │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│   PostgreSQL    │────▶│Cloud Backup  │
│   (metrics)     │     │  (forever)   │
└─────────────────┘     └──────────────┘
```

## Key Design Principles

1. **Start Simple, Scale Smart** - Begin with 5 regions, expand to full CONUS
2. **Tiered Storage** - Hot data local, warm on NAS, cold metrics in cloud
3. **Automated Lifecycle** - Data moves and cleans up automatically
4. **Geographic Flexibility** - Easy to add new regions/countries
5. **Cost Conscious** - Only keep what's needed, backup only metrics

## Support

If you encounter issues:
1. Check the specific task's Requirements section
2. Verify all dependencies are installed
3. Check logs in `logs/` directory
4. Review .env configuration
5. Test with dry-run modes where available