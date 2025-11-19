# Task 5: Updated Collectors with Storage Tiers

Modify `src/collectors/gfs_collector.py` to use the new storage architecture.

## 1. Import Storage Management

```python
from src.utils.storage import get_storage_path, move_to_nas, get_storage_stats
from src.config.regions import get_region, get_all_regions
```

## 2. Download Full Regional Grids

Instead of extracting points, download complete GRIB2 files:

**Regions to collect:**
1. Southern California: 30-36°N, 114-122°W
2. Colorado Rockies: 37-42°N, 104-110°W
3. Great Lakes: 40-48°N, 78-92°W
4. Gulf Coast: 26-32°N, 87-98°W
5. Pacific Northwest: 43-50°N, 120-128°W

**For each region:**
- Download full GRIB2 file using NOMADS filter
- Save initially to LOCAL storage
- Convert to NetCDF using xarray for easier analysis
- Extract point data at key cities for database
- After 24 hours, move raw GRIB2 to NAS

## 3. Updated Data Flow

```python
def collect_forecast(model: str, init_time: datetime, region: str):
    """
    1. Download GRIB2 to local storage
    2. Convert to NetCDF
    3. Extract point data and save to PostgreSQL
    4. Store file metadata (path, size) in database
    5. Schedule move to NAS after 24 hours
    """
```

## 4. File Organization

**Local storage pattern:**
```
data/raw/gfs/YYYYMMDD/gfs_YYYYMMDD_HHz_fHHH_REGION.grb2
data/raw/gfs/YYYYMMDD/gfs_YYYYMMDD_HHz_fHHH_REGION.nc
```

**NAS storage pattern:**
```
/mnt/nas/weather-data/raw/gfs/YYYYMMDD/...
```

**Database records:**
- Store file location (local or NAS path)
- Store file size, checksum (MD5)
- Allows retrieval for reprocessing

## 5. Command-Line Arguments

```python
parser.add_argument('--region', choices=['all', 'southern_ca', 'colorado', 'great_lakes', 'gulf_coast', 'pacific_nw'], default='all')
parser.add_argument('--storage-tier', choices=['local', 'nas'], default='local')
parser.add_argument('--keep-local-hours', type=int, default=24)
parser.add_argument('--forecast-hours', nargs='+', type=int, default=[0, 6, 12, 24, 48, 72])
parser.add_argument('--models', nargs='+', default=['GFS'])
parser.add_argument('--init-time', help='YYYYMMDDHH or "latest"')
```

## 6. Storage Logging

Log for each file:
- Download size and time
- Conversion time
- Storage tier and path
- Available disk space after operation
- Estimated time until local disk full

## 7. Error Handling

- Retry failed downloads up to 3 times
- Skip if file already exists (check by name and size)
- Continue with other regions/times if one fails
- Log all errors with context
- Don't crash on individual failures

## 8. Apply Same Pattern to NAM Collector

Create `src/collectors/nam_collector.py` following the same structure:
- NAM specific: 12km resolution, 4 runs/day (00Z, 06Z, 12Z, 18Z)
- Forecast hours: 0, 3, 6, 12, 18, 24, 36, 48, 60, 72, 84
- Same regions and storage tier approach
- Model name in database: 'NAM'

## Requirements

- Use `pygrib` or `cfgrib` to read GRIB2
- Use `xarray` for NetCDF conversion
- Check available space before downloading
- Add progress indicators (file X of Y)
- Support resume/restart (skip already downloaded)

## File Locations

Modify: `src/collectors/gfs_collector.py`
Create: `src/collectors/nam_collector.py`