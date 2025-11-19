# Task 7: Monitoring Dashboard

Create `scripts/storage_dashboard.py` that provides visibility into system status.

## 1. Real-Time Storage Monitoring

```python
def get_storage_status() -> dict:
    """
    Return storage statistics for all tiers
    """
```

## 2. Data Collection Status

```python
def get_collection_status() -> dict:
    """
    Track last successful collection by model
    Count today's forecast hours and observations
    Identify missing data gaps
    Calculate 7-day success rate
    """
```

## 3. Verification Statistics

```python
def get_verification_status() -> dict:
    """
    Total forecast-observation pairs
    Coverage by region
    Recent MAE/RMSE by model and lead time
    Best performing model by forecast hour
    """
```

## 4. Backup Status

```python
def get_backup_status() -> dict:
    """
    Last backup timestamps (NAS and cloud)
    Backup sizes
    Health status (healthy/warning/critical)
    Estimated monthly cloud costs
    """
```

## 5. Terminal Display

```python
def print_dashboard():
    """
    Print formatted dashboard to terminal:
    
    ╔════════════════════════════════════════════════════════════╗
    ║         Weather Model Selection System - Dashboard         ║
    ║                    2024-11-18 14:30:00                     ║
    ╚════════════════════════════════════════════════════════════╝
    
    STORAGE STATUS
    ├─ Local:  45.2 GB / 196.0 GB (23% used)
    ├─ NAS:    230.5 GB / 8000.0 GB (3% used)
    └─ Cloud:  2.3 GB  ($0.05/month)
    
    DATA COLLECTION
    ├─ GFS:   Last run: 12:30 (30 min ago) ✓
    ├─ NAM:   Last run: 12:45 (15 min ago) ✓
    └─ Today: 240 forecast hours, 4580 observations
    
    VERIFICATION
    ├─ Total pairs: 125,430
    ├─ GFS MAE (0-24hr): 1.8°F
    └─ NAM MAE (0-24hr): 1.6°F  [BEST]
    
    BACKUPS
    ├─ NAS:   2024-11-18 02:00 ✓
    └─ Cloud: 2024-11-17 02:00 ✓
    """
```

## 6. HTML Report (Optional)

```python
def generate_html_report(output_path: str = 'docs/status.html'):
    """
    Generate HTML report with same information
    Include charts using Chart.js or Plotly
    Responsive design
    """
```

## 7. Command-Line Interface

```python
def main():
    """
    Support arguments:
    --format [terminal|html]
    --output [filepath]
    --refresh [seconds] (watch mode)
    """
```

## Usage Examples

```bash
# Simple terminal output
python scripts/storage_dashboard.py

# Watch mode (refresh every 30 seconds)
python scripts/storage_dashboard.py --refresh 30

# Generate HTML report
python scripts/storage_dashboard.py --format html --output docs/status.html
```

## Requirements

- Use `rich` library for beautiful terminal output (or ANSI codes)
- Optional: `jinja2` for HTML templating
- Query PostgreSQL for statistics
- Format numbers with proper units (GB, MB, etc.)
- Color-code status (green=good, yellow=warning, red=critical)

## File Location

Create: `scripts/storage_dashboard.py`