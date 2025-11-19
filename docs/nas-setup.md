# NAS Setup Documentation

Generated: 2025-11-18 11:58:52

## Configuration

- **NAS Type:** LOCAL
- **Mount Point:** /tmp/weather-nas-test

## Manual Mount Commands

### Mount Command
```bash
# Local directory at /tmp/weather-nas-test - no mount needed
```

### fstab Entry
Add this line to `/etc/fstab` for automatic mounting at boot:
```
# Local directory - no fstab entry needed
```

### Create Mount Point
```bash
sudo mkdir -p /tmp/weather-nas-test
```

## Directory Structure

```
/tmp/weather-nas-test/
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

## Performance Benchmarks

- **Write Speed:** 1985.6 MB/s
- **Available Space:** 200.6 GB

## Troubleshooting

### NFS Issues

1. **Mount fails with "access denied"**
   - Check NFS export permissions on the server
   - Ensure client IP is allowed in exports file

2. **Mount hangs**
   - Verify network connectivity
   - Check firewall rules (NFS uses ports 111, 2049)

3. **Permission denied when writing**
   - Check NFS export options (should include `rw`)
   - Verify user/group permissions match

### SMB/CIFS Issues

1. **Authentication fails**
   - Verify username and password
   - Check SMB server version compatibility

2. **Mount fails**
   - Install cifs-utils: `sudo apt install cifs-utils`
   - Verify SMB ports (445) are accessible

3. **Slow performance**
   - Try different SMB protocol versions
   - Check network latency

### General

1. **Check if NAS is mounted**
   ```bash
   df -h | grep {config['mount_point']}
   ```

2. **Test write access**
   ```bash
   touch {config['mount_point']}/test.txt
   ```

3. **Check logs**
   ```bash
   dmesg | tail -50
   journalctl -xe
   ```

## Verification

Run these commands to verify the setup:

```bash
# Check if mounted
mount | grep {config['mount_point']}

# Check available space
df -h {config['mount_point']}

# Test write access
echo "test" > {config['mount_point']}/test.txt && rm {config['mount_point']}/test.txt

# Verify directory structure
ls -la {config['mount_point']}
```
