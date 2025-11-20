#!/usr/bin/env python3
"""
Systemd Service Setup for Weather Model Selector

Creates and installs systemd service and timer files for:
- Data collection (every 6 hours)
- Verification (hourly)
- Lifecycle management (daily)
- System monitoring (every 15 minutes)

Must be run with sudo privileges.
"""

import os
import sys
import pwd
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Project configuration
PROJECT_DIR = Path(__file__).parent.parent.resolve()
VENV_DIR = PROJECT_DIR / "venv"
SCRIPTS_DIR = PROJECT_DIR / "scripts"
LOGS_DIR = PROJECT_DIR / "logs"

# Get actual user (not root when using sudo)
ACTUAL_USER = os.getenv('SUDO_USER') or os.getenv('USER') or 'dwake'
ACTUAL_GROUP = ACTUAL_USER  # Typically same as user

SYSTEMD_DIR = Path("/etc/systemd/system")


def check_privileges():
    """Ensure script is run with sudo privileges."""
    if os.geteuid() != 0:
        print("ERROR: This script must be run with sudo privileges")
        print("Usage: sudo python scripts/setup_systemd_services.py")
        sys.exit(1)
    print(f"✓ Running with sudo privileges")
    print(f"✓ Installing for user: {ACTUAL_USER}")
    print(f"✓ Project directory: {PROJECT_DIR}")


def create_service_file(name: str, description: str, exec_start: str,
                        memory_limit: str = "2G", cpu_quota: str = "150%") -> str:
    """
    Generate systemd service file content.

    Args:
        name: Service name
        description: Service description
        exec_start: Command to execute
        memory_limit: Memory limit (default: 2G)
        cpu_quota: CPU quota (default: 150%)

    Returns:
        Service file content as string
    """
    # Check if .env file exists
    env_file = PROJECT_DIR / ".env"
    env_line = f"EnvironmentFile={env_file}" if env_file.exists() else ""

    return f"""[Unit]
Description={description}
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
User={ACTUAL_USER}
Group={ACTUAL_GROUP}
WorkingDirectory={PROJECT_DIR}
Environment="PATH={VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin"
{env_line}

ExecStart={exec_start}

StandardOutput=append:{LOGS_DIR}/{name}.log
StandardError=append:{LOGS_DIR}/{name}.error.log

Restart=on-failure
RestartSec=300

MemoryLimit={memory_limit}
CPUQuota={cpu_quota}

[Install]
WantedBy=multi-user.target
"""


def create_timer_file(name: str, description: str, on_calendar: str,
                      on_boot_sec: str = "10min") -> str:
    """
    Generate systemd timer file content.

    Args:
        name: Timer name (matches service name)
        description: Timer description
        on_calendar: Calendar expression for scheduling
        on_boot_sec: Delay after boot (default: 10min)

    Returns:
        Timer file content as string
    """
    return f"""[Unit]
Description={description}
Requires={name}.service

[Timer]
OnCalendar={on_calendar}
OnBootSec={on_boot_sec}
Persistent=true
AccuracySec=5min

[Install]
WantedBy=timers.target
"""


def get_service_definitions() -> List[Dict]:
    """
    Define all services to be created.

    Returns:
        List of service definition dictionaries
    """
    return [
        {
            'name': 'weather-collector',
            'description': 'Weather Model Data Collection Service',
            'exec_start': f"{SCRIPTS_DIR}/automated_collection.sh",
            'memory_limit': '2G',
            'cpu_quota': '150%',
            'timer_description': 'Weather Model Data Collection Timer',
            'on_calendar': '00/6:00:00',  # Every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)
            'on_boot_sec': '10min'
        },
        {
            'name': 'weather-verification',
            'description': 'Weather Model Forecast Verification Service',
            'exec_start': f"{VENV_DIR}/bin/python {SCRIPTS_DIR}/run_verification.py --model GFS --hours-back 12 && "
                         f"{VENV_DIR}/bin/python {SCRIPTS_DIR}/run_verification.py --model NAM --hours-back 12",
            'memory_limit': '4G',
            'cpu_quota': '200%',
            'timer_description': 'Weather Model Forecast Verification Timer',
            'on_calendar': 'hourly',  # Every hour at :00
            'on_boot_sec': '30min'
        },
        {
            'name': 'weather-lifecycle',
            'description': 'Weather Data Lifecycle Management Service',
            'exec_start': f"{VENV_DIR}/bin/python {SCRIPTS_DIR}/data_lifecycle_manager.py",
            'memory_limit': '1G',
            'cpu_quota': '100%',
            'timer_description': 'Weather Data Lifecycle Management Timer',
            'on_calendar': '02:00:00',  # Daily at 02:00 UTC
            'on_boot_sec': '1h'
        },
        {
            'name': 'weather-monitor',
            'description': 'Weather System Health Monitoring Service',
            'exec_start': f"{VENV_DIR}/bin/python {SCRIPTS_DIR}/system_health_check.py",
            'memory_limit': '512M',
            'cpu_quota': '50%',
            'timer_description': 'Weather System Health Monitoring Timer',
            'on_calendar': '*:00/15',  # Every 15 minutes
            'on_boot_sec': '5min'
        }
    ]


def create_service_files() -> List[Path]:
    """
    Create all systemd service and timer files.

    Returns:
        List of created file paths
    """
    services = get_service_definitions()
    created_files = []

    print("\n" + "=" * 70)
    print("Creating systemd service files...")
    print("=" * 70)

    for svc in services:
        # Create service file
        service_path = SYSTEMD_DIR / f"{svc['name']}.service"
        service_content = create_service_file(
            svc['name'],
            svc['description'],
            svc['exec_start'],
            svc['memory_limit'],
            svc['cpu_quota']
        )

        with open(service_path, 'w') as f:
            f.write(service_content)
        os.chmod(service_path, 0o644)
        created_files.append(service_path)
        print(f"✓ Created {service_path}")

        # Create timer file
        timer_path = SYSTEMD_DIR / f"{svc['name']}.timer"
        timer_content = create_timer_file(
            svc['name'],
            svc['timer_description'],
            svc['on_calendar'],
            svc['on_boot_sec']
        )

        with open(timer_path, 'w') as f:
            f.write(timer_content)
        os.chmod(timer_path, 0o644)
        created_files.append(timer_path)
        print(f"✓ Created {timer_path}")

    return created_files


def reload_systemd():
    """Reload systemd daemon to recognize new files."""
    print("\n" + "=" * 70)
    print("Reloading systemd daemon...")
    print("=" * 70)

    result = subprocess.run(['systemctl', 'daemon-reload'],
                          capture_output=True, text=True)

    if result.returncode == 0:
        print("✓ Systemd daemon reloaded")
    else:
        print(f"✗ Failed to reload systemd: {result.stderr}")
        sys.exit(1)


def enable_and_start_timers():
    """Enable and start all timer units."""
    services = get_service_definitions()

    print("\n" + "=" * 70)
    print("Enabling and starting timers...")
    print("=" * 70)

    for svc in services:
        timer_name = f"{svc['name']}.timer"

        # Enable timer (start on boot)
        result = subprocess.run(['systemctl', 'enable', timer_name],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Enabled {timer_name}")
        else:
            print(f"✗ Failed to enable {timer_name}: {result.stderr}")

        # Start timer immediately
        result = subprocess.run(['systemctl', 'start', timer_name],
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Started {timer_name}")
        else:
            print(f"✗ Failed to start {timer_name}: {result.stderr}")


def show_status():
    """Display status of all services and timers."""
    print("\n" + "=" * 70)
    print("Service and Timer Status")
    print("=" * 70)

    result = subprocess.run(['systemctl', 'list-timers', 'weather-*'],
                          capture_output=True, text=True)
    print(result.stdout)

    print("\n" + "=" * 70)
    print("Installation Complete!")
    print("=" * 70)
    print("\nUseful commands:")
    print("  systemctl list-timers weather-*      # List all weather timers")
    print("  systemctl status weather-*.timer     # Check timer status")
    print("  journalctl -u weather-* -f           # Follow all weather service logs")
    print("  systemctl start weather-collector.service  # Manually trigger collection")
    print("\nHealth reports: {}/health_report_*.txt".format(LOGS_DIR))
    print("Service logs: {}/weather-*.log".format(LOGS_DIR))


def main():
    """Main entry point."""
    print("=" * 70)
    print("Weather Model Selector - Systemd Service Setup")
    print("=" * 70)

    # Check privileges
    check_privileges()

    # Ensure logs directory exists
    LOGS_DIR.mkdir(exist_ok=True)
    # Change ownership to actual user
    os.chown(LOGS_DIR, pwd.getpwnam(ACTUAL_USER).pw_uid, pwd.getpwnam(ACTUAL_USER).pw_gid)

    # Create service files
    created_files = create_service_files()

    # Reload systemd
    reload_systemd()

    # Enable and start timers
    enable_and_start_timers()

    # Show status
    show_status()

    # Log installation
    log_file = LOGS_DIR / "systemd_setup.log"
    with open(log_file, 'a') as f:
        f.write(f"\n{'=' * 70}\n")
        f.write(f"Systemd services installed: {datetime.now()}\n")
        f.write(f"User: {ACTUAL_USER}\n")
        f.write(f"Project: {PROJECT_DIR}\n")
        f.write(f"Files created:\n")
        for path in created_files:
            f.write(f"  - {path}\n")
        f.write(f"{'=' * 70}\n")

    print(f"\nSetup log written to: {log_file}")


if __name__ == '__main__':
    main()
