# Task 6: Region Configuration System

Create `src/config/regions.py` that defines collection regions as structured configuration.

## 1. Region Data Structure

Define 5 initial regions plus future expansion templates:

```python
REGIONS = {
    'southern_ca': {
        'name': 'Southern California',
        'description': 'Marine layer, Santa Ana winds, coastal weather',
        'bounds': {'lat_min': 30.0, 'lat_max': 36.0, 'lon_min': -122.0, 'lon_max': -114.0},
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'San Diego', 'lat': 32.73, 'lon': -117.17, 'station': 'KSAN'},
            {'name': 'Los Angeles', 'lat': 34.05, 'lon': -118.24, 'station': 'KLAX'},
        ],
        'metar_stations': ['KSAN', 'KLAX', 'KONT', 'KSDM'],
        'buoys': [46086, 46232, 46254],
        'weather_features': ['marine_layer', 'santa_ana_winds'],
    },
    'colorado': {
        'name': 'Colorado Rockies',
        'description': 'Complex terrain, rapid weather changes, winter storms',
        'bounds': {'lat_min': 37.0, 'lat_max': 42.0, 'lon_min': -110.0, 'lon_max': -104.0},
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'Denver', 'lat': 39.86, 'lon': -104.67, 'station': 'KDEN'},
            {'name': 'Colorado Springs', 'lat': 38.81, 'lon': -104.70, 'station': 'KCOS'},
        ],
        'metar_stations': ['KDEN', 'KCOS', 'KGJT'],
        'buoys': [],
        'weather_features': ['mountain_waves', 'upslope_snow'],
    },
    'great_lakes': {
        'name': 'Great Lakes Region',
        'description': 'Lake effect snow, rapid weather changes',
        'bounds': {'lat_min': 40.0, 'lat_max': 48.0, 'lon_min': -92.0, 'lon_max': -78.0},
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'Chicago', 'lat': 41.98, 'lon': -87.90, 'station': 'KORD'},
            {'name': 'Cleveland', 'lat': 41.41, 'lon': -81.85, 'station': 'KCLE'},
        ],
        'metar_stations': ['KORD', 'KCLE', 'KDTW', 'KMKE'],
        'buoys': [45007, 45161],
        'weather_features': ['lake_effect_snow', 'rapid_frontal_passages'],
    },
    'gulf_coast': {
        'name': 'Gulf Coast',
        'description': 'Tropical systems, convection, maritime weather',
        'bounds': {'lat_min': 26.0, 'lat_max': 32.0, 'lon_min': -98.0, 'lon_max': -87.0},
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'Houston', 'lat': 29.98, 'lon': -95.34, 'station': 'KIAH'},
            {'name': 'New Orleans', 'lat': 29.99, 'lon': -90.26, 'station': 'KMSY'},
        ],
        'metar_stations': ['KIAH', 'KMSY', 'KMOB'],
        'buoys': [42001, 42002, 42003],
        'weather_features': ['tropical_cyclones', 'sea_breeze'],
    },
    'pacific_nw': {
        'name': 'Pacific Northwest',
        'description': 'Frontal systems, orographic precipitation',
        'bounds': {'lat_min': 43.0, 'lat_max': 50.0, 'lon_min': -125.0, 'lon_max': -120.0},
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'Seattle', 'lat': 47.45, 'lon': -122.31, 'station': 'KSEA'},
            {'name': 'Portland', 'lat': 45.59, 'lon': -122.60, 'station': 'KPDX'},
        ],
        'metar_stations': ['KSEA', 'KPDX', 'KGEG'],
        'buoys': [46041, 46050],
        'weather_features': ['atmospheric_rivers', 'orographic_enhancement'],
    },
}
```

## 2. Helper Functions

```python
def get_region(name: str) -> dict:
    """Return region configuration by name"""
    
def get_all_regions(priority: str = None) -> list:
    """Return list of all region names, optionally filtered by priority"""
    
def get_region_bounds(name: str) -> tuple:
    """Return (lat_min, lat_max, lon_min, lon_max)"""
    
def get_region_key_points(name: str) -> list:
    """Return list of key observation points"""
    
def get_region_stations(name: str, obs_type: str = 'metar') -> list:
    """Return list of station IDs (METAR or buoy)"""
```

## 3. Validation

Check that:
- Bounds are valid (lat: -90 to 90, lon: -180 to 180)
- lat_min < lat_max, lon_min < lon_max
- Key points are within bounds
- Station IDs are valid format
- Priority is one of: high, medium, low

## 4. Future Expansion Templates

Include templates for:
- `conus_full`: Full Continental US
- `alaska`: Alaska region
- `hawaii`: Hawaii region
- `puerto_rico`: Puerto Rico & USVI

## Requirements

- Use Python dictionaries
- Include comprehensive docstrings
- Add type hints
- Make it trivial to add new regions

## File Location

Create: `src/config/regions.py`
Create: `src/config/__init__.py`