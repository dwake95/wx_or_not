# Task 2: NAS Integration Setup

Create `scripts/setup_nas.py` that helps configure NAS integration.

## 1. Interactive Setup Wizard

Prompt for:
- NAS type (NFS, SMB/CIFS, or local directory for testing)
- Connection parameters:
  - NFS: Server IP, export path
  - SMB: Server IP, share name, username, password
  - Local: Directory path
- Test connectivity before proceeding

## 2. Mount Configuration

For NFS:
```python
# Generate fstab entry like:
# 192.168.1.100:/volume1/weather-data /mnt/nas/weather-data nfs defaults 0 0
```

For SMB/CIFS:
```python
# Generate fstab entry like:
# //192.168.1.100/weather-data /mnt/nas/weather-data cifs username=user,password=pass 0 0
```

Offer to:
- Add to `/etc/fstab` (requires sudo)
- Provide manual mount command
- Create systemd mount unit

## 3. Directory Structure Creation

Create on NAS:
```
/mnt/nas/weather-data/
├── raw/
│   ├── gfs/
│   ├── nam/
│   ├── hrrr/
│   └── observations/
│       ├── metar/
│       └── buoy/
├── backups/
│   ├── database/
│   └── verification/
└── archive/
```

## 4. Validation Tests

- Verify read/write access
- Test file creation and deletion
- Check available space (warn if < 100 GB free)
- Measure write speed (should be > 10 MB/s)

## 5. Configuration Update

Update `.env` with:
```
NAS_STORAGE_PATH=/mnt/nas/weather-data
NAS_ENABLED=true
NAS_TYPE=nfs
NAS_SERVER=192.168.1.100
```

## 6. Documentation Output

Generate `docs/nas-setup.md` with:
- Configuration used
- Manual mount commands
- Troubleshooting steps
- Performance benchmarks

## Requirements

- Interactive prompts using `input()`
- Color output using `colorama` or ANSI codes
- Support both interactive and non-interactive modes (command-line args)
- Graceful handling if NAS unavailable
- Fallback to local-only mode

## File Location

Create: `scripts/setup_nas.py`