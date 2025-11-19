#!/usr/bin/env python3
"""Interactive NAS setup wizard for weather model storage system."""
import sys
import os
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger

# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print a header with formatting."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def prompt_nas_type() -> str:
    """
    Prompt user to select NAS type.

    Returns:
        NAS type: 'nfs', 'smb', or 'local'
    """
    print_header("NAS Type Selection")
    print("Select your NAS type:")
    print("  1) NFS (Network File System)")
    print("  2) SMB/CIFS (Windows/Samba shares)")
    print("  3) Local directory (for testing)")
    print()

    while True:
        choice = input("Enter choice [1-3]: ").strip()
        if choice == '1':
            return 'nfs'
        elif choice == '2':
            return 'smb'
        elif choice == '3':
            return 'local'
        else:
            print_error("Invalid choice. Please enter 1, 2, or 3.")


def prompt_nfs_config() -> Dict[str, str]:
    """
    Prompt for NFS configuration.

    Returns:
        Dictionary with NFS configuration
    """
    print_header("NFS Configuration")

    server = input("NFS Server IP or hostname: ").strip()
    export_path = input("Export path (e.g., /volume1/weather-data): ").strip()
    mount_point = input("Local mount point [/mnt/nas/weather-data]: ").strip() or "/mnt/nas/weather-data"

    return {
        'type': 'nfs',
        'server': server,
        'export_path': export_path,
        'mount_point': mount_point
    }


def prompt_smb_config() -> Dict[str, str]:
    """
    Prompt for SMB/CIFS configuration.

    Returns:
        Dictionary with SMB configuration
    """
    print_header("SMB/CIFS Configuration")

    server = input("SMB Server IP or hostname: ").strip()
    share_name = input("Share name (e.g., weather-data): ").strip()
    username = input("Username: ").strip()
    password = input("Password: ").strip()
    mount_point = input("Local mount point [/mnt/nas/weather-data]: ").strip() or "/mnt/nas/weather-data"

    return {
        'type': 'smb',
        'server': server,
        'share_name': share_name,
        'username': username,
        'password': password,
        'mount_point': mount_point
    }


def prompt_local_config() -> Dict[str, str]:
    """
    Prompt for local directory configuration.

    Returns:
        Dictionary with local configuration
    """
    print_header("Local Directory Configuration")

    print_info("This mode uses a local directory to simulate NAS storage (for testing)")
    directory = input("Local directory path [/tmp/weather-nas-test]: ").strip() or "/tmp/weather-nas-test"

    return {
        'type': 'local',
        'mount_point': directory
    }


def test_connectivity(config: Dict[str, str]) -> bool:
    """
    Test NAS connectivity.

    Args:
        config: NAS configuration dictionary

    Returns:
        True if connectivity test passes, False otherwise
    """
    print_header("Connectivity Test")

    nas_type = config['type']
    mount_point = Path(config['mount_point'])

    if nas_type == 'local':
        # For local directory, just check if we can create it
        try:
            mount_point.mkdir(parents=True, exist_ok=True)
            print_success(f"Local directory created/verified: {mount_point}")
            return True
        except Exception as e:
            print_error(f"Failed to create local directory: {e}")
            return False

    elif nas_type == 'nfs':
        # For NFS, try to ping the server
        print_info(f"Testing connection to {config['server']}...")
        response = os.system(f"ping -c 1 -W 2 {config['server']} > /dev/null 2>&1")
        if response == 0:
            print_success(f"Server {config['server']} is reachable")
            return True
        else:
            print_error(f"Server {config['server']} is not reachable")
            return False

    elif nas_type == 'smb':
        # For SMB, try to ping the server
        print_info(f"Testing connection to {config['server']}...")
        response = os.system(f"ping -c 1 -W 2 {config['server']} > /dev/null 2>&1")
        if response == 0:
            print_success(f"Server {config['server']} is reachable")
            return True
        else:
            print_error(f"Server {config['server']} is not reachable")
            return False

    return False


def generate_mount_config(config: Dict[str, str]) -> Tuple[str, str]:
    """
    Generate mount configuration.

    Args:
        config: NAS configuration dictionary

    Returns:
        Tuple of (fstab_entry, mount_command)
    """
    nas_type = config['type']
    mount_point = config['mount_point']

    if nas_type == 'nfs':
        fstab_entry = f"{config['server']}:{config['export_path']} {mount_point} nfs defaults,_netdev 0 0"
        mount_command = f"sudo mount -t nfs {config['server']}:{config['export_path']} {mount_point}"

    elif nas_type == 'smb':
        fstab_entry = (
            f"//{config['server']}/{config['share_name']} {mount_point} cifs "
            f"username={config['username']},password={config['password']},_netdev 0 0"
        )
        mount_command = (
            f"sudo mount -t cifs //{config['server']}/{config['share_name']} {mount_point} "
            f"-o username={config['username']},password={config['password']}"
        )

    elif nas_type == 'local':
        fstab_entry = "# Local directory - no fstab entry needed"
        mount_command = f"# Local directory at {mount_point} - no mount needed"

    return fstab_entry, mount_command


def create_directory_structure(config: Dict[str, str]) -> bool:
    """
    Create the required directory structure on NAS.

    Args:
        config: NAS configuration dictionary

    Returns:
        True if successful, False otherwise
    """
    print_header("Creating Directory Structure")

    mount_point = Path(config['mount_point'])

    # Define directory structure
    directories = [
        'raw/gfs',
        'raw/nam',
        'raw/hrrr',
        'raw/observations/metar',
        'raw/observations/buoy',
        'backups/database',
        'backups/verification',
        'archive',
    ]

    try:
        for dir_path in directories:
            full_path = mount_point / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            print_success(f"Created: {full_path}")

        print()
        print_success("Directory structure created successfully")
        return True

    except Exception as e:
        print_error(f"Failed to create directory structure: {e}")
        return False


def validate_access(config: Dict[str, str]) -> Dict[str, bool]:
    """
    Validate read/write access to NAS.

    Args:
        config: NAS configuration dictionary

    Returns:
        Dictionary with test results
    """
    print_header("Access Validation")

    mount_point = Path(config['mount_point'])
    results = {
        'read_access': False,
        'write_access': False,
        'delete_access': False,
    }

    # Test write access
    test_file = mount_point / 'test_write.txt'
    try:
        print_info("Testing write access...")
        test_file.write_text(f"Test file created at {datetime.now()}")
        results['write_access'] = True
        print_success("Write access: OK")
    except Exception as e:
        print_error(f"Write access: FAILED ({e})")
        return results

    # Test read access
    try:
        print_info("Testing read access...")
        content = test_file.read_text()
        results['read_access'] = True
        print_success("Read access: OK")
    except Exception as e:
        print_error(f"Read access: FAILED ({e})")
        return results

    # Test delete access
    try:
        print_info("Testing delete access...")
        test_file.unlink()
        results['delete_access'] = True
        print_success("Delete access: OK")
    except Exception as e:
        print_error(f"Delete access: FAILED ({e})")
        return results

    return results


def check_available_space(config: Dict[str, str]) -> Optional[float]:
    """
    Check available space on NAS.

    Args:
        config: NAS configuration dictionary

    Returns:
        Available space in GB, or None if check fails
    """
    print_header("Storage Space Check")

    mount_point = Path(config['mount_point'])

    try:
        import psutil
        usage = psutil.disk_usage(str(mount_point))

        total_gb = usage.total / (1024 ** 3)
        free_gb = usage.free / (1024 ** 3)
        used_percent = usage.percent

        print_info(f"Total space: {total_gb:.1f} GB")
        print_info(f"Free space: {free_gb:.1f} GB")
        print_info(f"Used: {used_percent:.1f}%")

        if free_gb < 100:
            print_warning(f"Warning: Less than 100 GB free space available")
        else:
            print_success(f"Sufficient space available")

        return free_gb

    except Exception as e:
        print_error(f"Failed to check space: {e}")
        return None


def measure_write_speed(config: Dict[str, str]) -> Optional[float]:
    """
    Measure write speed to NAS.

    Args:
        config: NAS configuration dictionary

    Returns:
        Write speed in MB/s, or None if test fails
    """
    print_header("Write Speed Test")

    mount_point = Path(config['mount_point'])
    test_file = mount_point / 'speed_test.dat'

    try:
        # Write 10 MB test file
        test_size_mb = 10
        test_data = b'X' * (1024 * 1024)  # 1 MB of data

        print_info(f"Writing {test_size_mb} MB test file...")
        start_time = time.time()

        with open(test_file, 'wb') as f:
            for _ in range(test_size_mb):
                f.write(test_data)

        end_time = time.time()
        elapsed = end_time - start_time
        speed_mbps = test_size_mb / elapsed

        # Clean up
        test_file.unlink()

        print_success(f"Write speed: {speed_mbps:.1f} MB/s")

        if speed_mbps < 10:
            print_warning("Warning: Write speed is below 10 MB/s")
        else:
            print_success("Write speed is acceptable")

        return speed_mbps

    except Exception as e:
        print_error(f"Failed to measure write speed: {e}")
        # Clean up if test file exists
        if test_file.exists():
            test_file.unlink()
        return None


def update_env_file(config: Dict[str, str]) -> bool:
    """
    Update .env file with NAS configuration.

    Args:
        config: NAS configuration dictionary

    Returns:
        True if successful, False otherwise
    """
    print_header("Updating Configuration")

    env_file = Path(__file__).parent.parent / '.env'

    try:
        # Read existing .env content
        if env_file.exists():
            content = env_file.read_text()
        else:
            content = ""

        # Update NAS settings
        lines = content.split('\n')
        updated_lines = []
        nas_settings_found = False

        for line in lines:
            if line.startswith('NAS_STORAGE_PATH='):
                updated_lines.append(f"NAS_STORAGE_PATH={config['mount_point']}")
                nas_settings_found = True
            elif line.startswith('NAS_ENABLED='):
                updated_lines.append("NAS_ENABLED=true")
            elif line.startswith('NAS_TYPE='):
                updated_lines.append(f"NAS_TYPE={config['type']}")
            elif line.startswith('NAS_SERVER='):
                if 'server' in config:
                    updated_lines.append(f"NAS_SERVER={config['server']}")
                else:
                    updated_lines.append(line)
            else:
                updated_lines.append(line)

        # Add NAS settings if not found
        if not nas_settings_found:
            # Find the Storage Tiers section
            for i, line in enumerate(updated_lines):
                if '# Storage Tiers' in line:
                    # Update existing section
                    j = i + 1
                    while j < len(updated_lines) and updated_lines[j].strip() and not updated_lines[j].startswith('#'):
                        j += 1
                    # Insert new lines
                    if 'server' in config:
                        updated_lines.insert(j, f"NAS_SERVER={config['server']}")
                    updated_lines.insert(j, f"NAS_TYPE={config['type']}")
                    break

        # Write updated content
        env_file.write_text('\n'.join(updated_lines))
        print_success(f"Updated .env file: {env_file}")

        return True

    except Exception as e:
        print_error(f"Failed to update .env file: {e}")
        return False


def generate_documentation(config: Dict[str, str], test_results: Dict) -> bool:
    """
    Generate NAS setup documentation.

    Args:
        config: NAS configuration dictionary
        test_results: Dictionary with test results

    Returns:
        True if successful, False otherwise
    """
    print_header("Generating Documentation")

    docs_dir = Path(__file__).parent.parent / 'docs'
    docs_dir.mkdir(exist_ok=True)
    doc_file = docs_dir / 'nas-setup.md'

    fstab_entry, mount_command = generate_mount_config(config)

    try:
        documentation = f"""# NAS Setup Documentation

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Configuration

- **NAS Type:** {config['type'].upper()}
- **Mount Point:** {config['mount_point']}
"""

        if 'server' in config:
            documentation += f"- **Server:** {config['server']}\n"

        if 'export_path' in config:
            documentation += f"- **Export Path:** {config['export_path']}\n"

        if 'share_name' in config:
            documentation += f"- **Share Name:** {config['share_name']}\n"

        documentation += f"""
## Manual Mount Commands

### Mount Command
```bash
{mount_command}
```

### fstab Entry
Add this line to `/etc/fstab` for automatic mounting at boot:
```
{fstab_entry}
```

### Create Mount Point
```bash
sudo mkdir -p {config['mount_point']}
```

## Directory Structure

```
{config['mount_point']}/
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

"""

        if 'write_speed' in test_results and test_results['write_speed']:
            documentation += f"- **Write Speed:** {test_results['write_speed']:.1f} MB/s\n"

        if 'free_space' in test_results and test_results['free_space']:
            documentation += f"- **Available Space:** {test_results['free_space']:.1f} GB\n"

        documentation += """
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
"""

        doc_file.write_text(documentation)
        print_success(f"Documentation generated: {doc_file}")

        return True

    except Exception as e:
        print_error(f"Failed to generate documentation: {e}")
        return False


def main():
    """Main function for NAS setup wizard."""
    parser = argparse.ArgumentParser(description='NAS Setup Wizard')
    parser.add_argument('--non-interactive', action='store_true',
                      help='Non-interactive mode (for automated setups)')
    parser.add_argument('--type', choices=['nfs', 'smb', 'local'],
                      help='NAS type')
    parser.add_argument('--mount-point', help='Mount point path')

    args = parser.parse_args()

    print_header("Weather Model NAS Setup Wizard")
    print_info("This wizard will help you configure NAS storage for weather data")

    # Get configuration
    if args.non_interactive and args.type and args.mount_point:
        config = {
            'type': args.type,
            'mount_point': args.mount_point
        }
    else:
        # Interactive mode
        nas_type = prompt_nas_type()

        if nas_type == 'nfs':
            config = prompt_nfs_config()
        elif nas_type == 'smb':
            config = prompt_smb_config()
        else:
            config = prompt_local_config()

    # Test connectivity
    if not test_connectivity(config):
        print_error("Connectivity test failed. Setup cannot continue.")
        print_info("You can run this script again to retry.")
        sys.exit(1)

    # Create directory structure
    if not create_directory_structure(config):
        print_error("Failed to create directory structure")
        sys.exit(1)

    # Validate access
    access_results = validate_access(config)
    if not all(access_results.values()):
        print_error("Access validation failed")
        sys.exit(1)

    # Check space
    free_space = check_available_space(config)

    # Measure write speed
    write_speed = measure_write_speed(config)

    # Collect test results
    test_results = {
        'free_space': free_space,
        'write_speed': write_speed,
        **access_results
    }

    # Update .env file
    if not update_env_file(config):
        print_warning("Failed to update .env file - you'll need to update it manually")

    # Generate documentation
    generate_documentation(config, test_results)

    # Print mount instructions
    if config['type'] != 'local':
        print_header("Setup Complete!")
        fstab_entry, mount_command = generate_mount_config(config)

        print_success("NAS setup completed successfully")
        print()
        print_info("Next steps:")
        print(f"  1. Create mount point: sudo mkdir -p {config['mount_point']}")
        print(f"  2. Mount NAS: {mount_command}")
        print(f"  3. Add to fstab for automatic mounting:")
        print(f"     {fstab_entry}")
        print()
        print_info(f"Documentation saved to: docs/nas-setup.md")
    else:
        print_header("Setup Complete!")
        print_success(f"Local directory configured at: {config['mount_point']}")
        print_info("NAS enabled in .env file for testing")


if __name__ == "__main__":
    main()
