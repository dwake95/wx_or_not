#!/usr/bin/env python3
"""Storage and system monitoring dashboard for weather model selector."""
import sys
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.storage import get_storage_stats
from src.utils.cloud_backup import get_last_backup_time
from src.utils.database import get_db_connection
from loguru import logger


# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'


def format_size(bytes_value: float) -> str:
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def format_time_ago(dt: datetime) -> str:
    """Format datetime as time ago string."""
    now = datetime.now()
    if dt.tzinfo:
        from datetime import timezone
        now = datetime.now(timezone.utc)

    diff = now - dt

    if diff.total_seconds() < 60:
        return f"{int(diff.total_seconds())} sec ago"
    elif diff.total_seconds() < 3600:
        return f"{int(diff.total_seconds() / 60)} min ago"
    elif diff.total_seconds() < 86400:
        return f"{int(diff.total_seconds() / 3600)} hr ago"
    else:
        return f"{int(diff.total_seconds() / 86400)} days ago"


def get_status_icon(status: str) -> str:
    """Get colored status icon."""
    icons = {
        'good': f"{Colors.GREEN}✓{Colors.ENDC}",
        'warning': f"{Colors.YELLOW}⚠{Colors.ENDC}",
        'critical': f"{Colors.RED}✗{Colors.ENDC}",
    }
    return icons.get(status, '?')


def get_storage_status() -> Dict[str, Any]:
    """
    Get storage statistics for all tiers.

    Returns:
        Dictionary with storage stats for local, NAS, and cloud
    """
    stats = get_storage_stats()

    status = {}

    # Local storage
    if 'local' in stats and 'error' not in stats['local']:
        local = stats['local']
        free_gb = local['free_space_gb']

        # Determine health status
        if free_gb < 20:
            health = 'critical'
        elif free_gb < 50:
            health = 'warning'
        else:
            health = 'good'

        status['local'] = {
            'free_gb': free_gb,
            'total_gb': local['total_space_gb'],
            'used_percent': local['usage_percent'],
            'health': health,
            'files_count': local['files_count']
        }

    # NAS storage
    if 'nas' in stats and 'error' not in stats['nas']:
        nas = stats['nas']
        free_gb = nas['free_space_gb']

        # Determine health status
        if free_gb < 50:
            health = 'critical'
        elif free_gb < 100:
            health = 'warning'
        else:
            health = 'good'

        status['nas'] = {
            'free_gb': free_gb,
            'total_gb': nas['total_space_gb'],
            'used_percent': nas['usage_percent'],
            'health': health,
            'files_count': nas['files_count']
        }

    # Cloud storage (estimate from backups)
    # This is a placeholder - actual implementation would query cloud provider
    status['cloud'] = {
        'size_gb': 0.0,  # Would be calculated from actual cloud backups
        'monthly_cost': 0.00,  # $0.023/GB/month for S3
        'health': 'good'
    }

    return status


def get_collection_status() -> Dict[str, Any]:
    """
    Get data collection status.

    Returns:
        Dictionary with collection statistics
    """
    status = {
        'models': {},
        'today_forecasts': 0,
        'today_observations': 0,
        'success_rate_7day': 0.0
    }

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # Get last collection time by model
            cur.execute("""
                SELECT model_name, MAX(created_at) as last_run
                FROM model_forecasts
                GROUP BY model_name
            """)

            for row in cur.fetchall():
                model, last_run = row
                time_ago = format_time_ago(last_run) if last_run else 'Never'

                # Check if recent (within 6 hours)
                if last_run:
                    diff = datetime.now() - last_run.replace(tzinfo=None)
                    health = 'good' if diff.total_seconds() < 21600 else 'warning'
                else:
                    health = 'critical'

                status['models'][model] = {
                    'last_run': last_run,
                    'time_ago': time_ago,
                    'health': health
                }

            # Count today's forecasts
            cur.execute("""
                SELECT COUNT(*) FROM model_forecasts
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            status['today_forecasts'] = cur.fetchone()[0] or 0

            # Count today's observations (if table exists)
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'observations'
                )
            """)
            if cur.fetchone()[0]:
                cur.execute("""
                    SELECT COUNT(*) FROM observations
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                status['today_observations'] = cur.fetchone()[0] or 0

            cur.close()

    except Exception as e:
        logger.error(f"Failed to get collection status: {e}")

    return status


def get_verification_status() -> Dict[str, Any]:
    """
    Get verification statistics.

    Returns:
        Dictionary with verification stats
    """
    status = {
        'total_pairs': 0,
        'coverage_by_region': {},
        'model_performance': {},
        'best_model': None
    }

    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # Check if verification_scores table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'verification_scores'
                )
            """)

            if not cur.fetchone()[0]:
                cur.close()
                return status

            # Count total forecast-observation pairs
            cur.execute("""
                SELECT COUNT(*) FROM verification_scores
                WHERE observed_value IS NOT NULL
            """)
            status['total_pairs'] = cur.fetchone()[0] or 0

            # Get recent MAE by model and lead time (last 7 days)
            cur.execute("""
                SELECT
                    model_name,
                    lead_time_hours,
                    AVG(absolute_error) as mae,
                    SQRT(AVG(squared_error)) as rmse
                FROM verification_scores
                WHERE valid_time > NOW() - INTERVAL '7 days'
                  AND observed_value IS NOT NULL
                  AND forecast_value IS NOT NULL
                  AND lead_time_hours <= 24
                GROUP BY model_name, lead_time_hours
                ORDER BY model_name, lead_time_hours
            """)

            for row in cur.fetchall():
                model, lead_time, mae, rmse = row
                if model not in status['model_performance']:
                    status['model_performance'][model] = {}
                status['model_performance'][model][lead_time] = {
                    'mae': float(mae) if mae else 0.0,
                    'rmse': float(rmse) if rmse else 0.0
                }

            # Determine best model (lowest MAE for 0-24hr forecasts)
            if status['model_performance']:
                best_mae = float('inf')
                for model, lead_times in status['model_performance'].items():
                    # Average MAE for 0-24 hour forecasts
                    mae_values = [lt['mae'] for lt in lead_times.values()]
                    if mae_values:
                        avg_mae = sum(mae_values) / len(mae_values)
                        if avg_mae < best_mae and avg_mae > 0:
                            best_mae = avg_mae
                            status['best_model'] = model

            cur.close()

    except Exception as e:
        logger.error(f"Failed to get verification status: {e}")

    return status


def get_backup_status() -> Dict[str, Any]:
    """
    Get backup status.

    Returns:
        Dictionary with backup information
    """
    status = {
        'nas_backup': {},
        'cloud_backup': {},
        'health': 'good'
    }

    try:
        # Check for NAS database backups
        nas_backup_dir = Path('data/backups/database')
        if nas_backup_dir.exists():
            backups = list(nas_backup_dir.glob('pgdump_*.sql.gz'))
            if backups:
                latest = max(backups, key=lambda p: p.stat().st_mtime)
                mtime = datetime.fromtimestamp(latest.stat().st_mtime)
                size = latest.stat().st_size

                # Check if backup is recent (within 36 hours)
                age_hours = (datetime.now() - mtime).total_seconds() / 3600
                health = 'good' if age_hours < 36 else 'warning'

                status['nas_backup'] = {
                    'last_backup': mtime,
                    'time_ago': format_time_ago(mtime),
                    'size': format_size(size),
                    'health': health
                }

        # Check for cloud backups
        last_cloud_backup = get_last_backup_time()
        if last_cloud_backup:
            age_hours = (datetime.now() - last_cloud_backup).total_seconds() / 3600
            health = 'good' if age_hours < 168 else 'warning'  # 7 days

            status['cloud_backup'] = {
                'last_backup': last_cloud_backup,
                'time_ago': format_time_ago(last_cloud_backup),
                'health': health
            }

        # Overall health
        nas_health = status['nas_backup'].get('health', 'critical')
        cloud_health = status['cloud_backup'].get('health', 'warning')

        if nas_health == 'critical' or cloud_health == 'critical':
            status['health'] = 'critical'
        elif nas_health == 'warning' or cloud_health == 'warning':
            status['health'] = 'warning'
        else:
            status['health'] = 'good'

    except Exception as e:
        logger.error(f"Failed to get backup status: {e}")
        status['health'] = 'critical'

    return status


def print_dashboard():
    """Print formatted dashboard to terminal."""
    # Get all status information
    storage = get_storage_status()
    collection = get_collection_status()
    verification = get_verification_status()
    backup = get_backup_status()

    # Clear screen (optional)
    # print("\033[2J\033[H")

    # Header
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}╔{'═' * 58}╗{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{'Weather Model Selection System - Dashboard':^58}║{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}║{datetime.now().strftime('%Y-%m-%d %H:%M:%S'):^58}║{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚{'═' * 58}╝{Colors.ENDC}")
    print()

    # Storage Status
    print(f"{Colors.BOLD}STORAGE STATUS{Colors.ENDC}")
    if 'local' in storage:
        local = storage['local']
        icon = get_status_icon(local['health'])
        print(f"├─ Local:  {local['free_gb']:.1f} GB / {local['total_gb']:.1f} GB "
              f"({local['used_percent']:.1f}% used) {icon}")

    if 'nas' in storage:
        nas = storage['nas']
        icon = get_status_icon(nas['health'])
        print(f"├─ NAS:    {nas['free_gb']:.1f} GB / {nas['total_gb']:.1f} GB "
              f"({nas['used_percent']:.1f}% used) {icon}")

    if 'cloud' in storage:
        cloud = storage['cloud']
        print(f"└─ Cloud:  {cloud['size_gb']:.1f} GB  (${cloud['monthly_cost']:.2f}/month)")

    print()

    # Data Collection
    print(f"{Colors.BOLD}DATA COLLECTION{Colors.ENDC}")
    if collection['models']:
        for model, info in collection['models'].items():
            icon = get_status_icon(info['health'])
            print(f"├─ {model:5s} Last run: {info['time_ago']:20s} {icon}")
    else:
        print(f"├─ No collection data available")

    print(f"└─ Today: {collection['today_forecasts']} forecast records, "
          f"{collection['today_observations']} observations")
    print()

    # Verification
    print(f"{Colors.BOLD}VERIFICATION{Colors.ENDC}")
    print(f"├─ Total pairs: {verification['total_pairs']:,}")

    if verification['model_performance']:
        for model, lead_times in verification['model_performance'].items():
            # Show average MAE for 0-24hr
            mae_values = [lt['mae'] for lt in lead_times.values()]
            if mae_values:
                avg_mae = sum(mae_values) / len(mae_values)
                best_tag = f"{Colors.GREEN}[BEST]{Colors.ENDC}" if model == verification['best_model'] else ""
                print(f"├─ {model} MAE (0-24hr): {avg_mae:.2f} {best_tag}")
    else:
        print(f"├─ No verification data available")

    print()

    # Backups
    print(f"{Colors.BOLD}BACKUPS{Colors.ENDC}")
    if backup['nas_backup']:
        nas = backup['nas_backup']
        icon = get_status_icon(nas['health'])
        print(f"├─ NAS:   {nas['last_backup'].strftime('%Y-%m-%d %H:%M')} "
              f"({nas['time_ago']}) {icon}")
    else:
        print(f"├─ NAS:   No backups found {get_status_icon('critical')}")

    if backup['cloud_backup']:
        cloud = backup['cloud_backup']
        icon = get_status_icon(cloud['health'])
        print(f"└─ Cloud: {cloud['last_backup'].strftime('%Y-%m-%d %H:%M')} "
              f"({cloud['time_ago']}) {icon}")
    else:
        print(f"└─ Cloud: No backups found {get_status_icon('warning')}")

    print()
    print(f"{Colors.BOLD}Overall System Health: {get_status_icon(backup['health'])}{Colors.ENDC}")
    print()


def watch_mode(refresh_seconds: int):
    """
    Run dashboard in watch mode with periodic refresh.

    Args:
        refresh_seconds: Seconds between refreshes
    """
    try:
        while True:
            # Clear screen
            print("\033[2J\033[H")
            print_dashboard()
            print(f"Refreshing every {refresh_seconds} seconds... (Ctrl+C to exit)")
            time.sleep(refresh_seconds)
    except KeyboardInterrupt:
        print("\nExiting watch mode...")


def generate_html_report(output_path: str = 'docs/status.html'):
    """
    Generate HTML report with dashboard information.

    Args:
        output_path: Path to save HTML file
    """
    # Get all status information
    storage = get_storage_status()
    collection = get_collection_status()
    verification = get_verification_status()
    backup = get_backup_status()

    # Simple HTML template
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weather Model System Status</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .status-card {{
            border: 1px solid #ddd;
            padding: 20px;
            border-radius: 5px;
        }}
        .status-good {{ border-left: 4px solid #4CAF50; }}
        .status-warning {{ border-left: 4px solid #FF9800; }}
        .status-critical {{ border-left: 4px solid #F44336; }}
        .metric {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        .metric:last-child {{ border-bottom: none; }}
        .label {{ font-weight: bold; }}
        .value {{ color: #666; }}
        .timestamp {{
            text-align: center;
            color: #999;
            margin-top: 30px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Weather Model Selection System - Status Dashboard</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <h2>Storage Status</h2>
        <div class="status-grid">
"""

    # Add storage cards
    for tier, info in storage.items():
        if tier == 'cloud':
            health_class = f"status-{info['health']}"
            html += f"""
            <div class="status-card {health_class}">
                <h3>{tier.upper()}</h3>
                <div class="metric">
                    <span class="label">Size:</span>
                    <span class="value">{info['size_gb']:.1f} GB</span>
                </div>
                <div class="metric">
                    <span class="label">Monthly Cost:</span>
                    <span class="value">${info['monthly_cost']:.2f}</span>
                </div>
            </div>
"""
        elif 'health' in info:
            health_class = f"status-{info['health']}"
            html += f"""
            <div class="status-card {health_class}">
                <h3>{tier.upper()}</h3>
                <div class="metric">
                    <span class="label">Free:</span>
                    <span class="value">{info['free_gb']:.1f} GB</span>
                </div>
                <div class="metric">
                    <span class="label">Total:</span>
                    <span class="value">{info['total_gb']:.1f} GB</span>
                </div>
                <div class="metric">
                    <span class="label">Used:</span>
                    <span class="value">{info['used_percent']:.1f}%</span>
                </div>
            </div>
"""

    html += """
        </div>

        <h2>Data Collection</h2>
        <div class="status-grid">
"""

    # Add collection cards
    for model, info in collection['models'].items():
        health_class = f"status-{info['health']}"
        html += f"""
            <div class="status-card {health_class}">
                <h3>{model}</h3>
                <div class="metric">
                    <span class="label">Last Run:</span>
                    <span class="value">{info['time_ago']}</span>
                </div>
            </div>
"""

    html += f"""
        </div>
        <p>Today: {collection['today_forecasts']} forecasts, {collection['today_observations']} observations</p>

        <div class="timestamp">
            Generated by Weather Model Selection System
        </div>
    </div>
</body>
</html>
"""

    # Write HTML file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html)

    print(f"HTML report generated: {output_file}")


def main():
    """Main entry point for storage dashboard."""
    parser = argparse.ArgumentParser(description='Storage and System Monitoring Dashboard')
    parser.add_argument('--format', choices=['terminal', 'html'], default='terminal',
                       help='Output format')
    parser.add_argument('--output', default='docs/status.html',
                       help='Output filepath for HTML report')
    parser.add_argument('--refresh', type=int, metavar='SECONDS',
                       help='Watch mode: refresh every N seconds')

    args = parser.parse_args()

    if args.refresh:
        # Watch mode
        watch_mode(args.refresh)
    elif args.format == 'html':
        # HTML report
        generate_html_report(args.output)
    else:
        # Terminal output
        print_dashboard()


if __name__ == "__main__":
    main()
