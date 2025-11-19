"""Region configuration system for weather data collection."""
from typing import Dict, List, Optional, Tuple, Any


# Regional configurations
REGIONS = {
    'southern_ca': {
        'name': 'Southern California',
        'description': 'Marine layer, Santa Ana winds, coastal weather',
        'bounds': {
            'lat_min': 30.0,
            'lat_max': 36.0,
            'lon_min': -122.0,
            'lon_max': -114.0
        },
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'San Diego', 'lat': 32.73, 'lon': -117.17, 'station': 'KSAN'},
            {'name': 'Los Angeles', 'lat': 34.05, 'lon': -118.24, 'station': 'KLAX'},
            {'name': 'Santa Barbara', 'lat': 34.43, 'lon': -119.84, 'station': 'KSBA'},
        ],
        'metar_stations': ['KSAN', 'KLAX', 'KONT', 'KSDM', 'KSBA', 'KBUR'],
        'buoys': [46086, 46232, 46254],
        'weather_features': ['marine_layer', 'santa_ana_winds', 'coastal_fog'],
    },
    'colorado': {
        'name': 'Colorado Rockies',
        'description': 'Complex terrain, rapid weather changes, winter storms',
        'bounds': {
            'lat_min': 37.0,
            'lat_max': 42.0,
            'lon_min': -110.0,
            'lon_max': -104.0
        },
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'Denver', 'lat': 39.86, 'lon': -104.67, 'station': 'KDEN'},
            {'name': 'Colorado Springs', 'lat': 38.81, 'lon': -104.70, 'station': 'KCOS'},
            {'name': 'Grand Junction', 'lat': 39.12, 'lon': -108.53, 'station': 'KGJT'},
        ],
        'metar_stations': ['KDEN', 'KCOS', 'KGJT', 'KAPA', 'KPUB'],
        'buoys': [],
        'weather_features': ['mountain_waves', 'upslope_snow', 'chinook_winds'],
    },
    'great_lakes': {
        'name': 'Great Lakes Region',
        'description': 'Lake effect snow, rapid weather changes',
        'bounds': {
            'lat_min': 40.0,
            'lat_max': 48.0,
            'lon_min': -92.0,
            'lon_max': -78.0
        },
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'Chicago', 'lat': 41.98, 'lon': -87.90, 'station': 'KORD'},
            {'name': 'Cleveland', 'lat': 41.41, 'lon': -81.85, 'station': 'KCLE'},
            {'name': 'Detroit', 'lat': 42.22, 'lon': -83.35, 'station': 'KDTW'},
            {'name': 'Milwaukee', 'lat': 42.95, 'lon': -87.90, 'station': 'KMKE'},
        ],
        'metar_stations': ['KORD', 'KCLE', 'KDTW', 'KMKE', 'KBUF'],
        'buoys': [45007, 45161, 45164],
        'weather_features': ['lake_effect_snow', 'rapid_frontal_passages', 'lake_breeze'],
    },
    'gulf_coast': {
        'name': 'Gulf Coast',
        'description': 'Tropical systems, convection, maritime weather',
        'bounds': {
            'lat_min': 26.0,
            'lat_max': 32.0,
            'lon_min': -98.0,
            'lon_max': -87.0
        },
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'Houston', 'lat': 29.98, 'lon': -95.34, 'station': 'KIAH'},
            {'name': 'New Orleans', 'lat': 29.99, 'lon': -90.26, 'station': 'KMSY'},
            {'name': 'Mobile', 'lat': 30.69, 'lon': -88.24, 'station': 'KMOB'},
        ],
        'metar_stations': ['KIAH', 'KMSY', 'KMOB', 'KHOU', 'KLCH'],
        'buoys': [42001, 42002, 42003, 42019, 42020],
        'weather_features': ['tropical_cyclones', 'sea_breeze', 'convection'],
    },
    'pacific_nw': {
        'name': 'Pacific Northwest',
        'description': 'Frontal systems, orographic precipitation',
        'bounds': {
            'lat_min': 43.0,
            'lat_max': 50.0,
            'lon_min': -128.0,
            'lon_max': -116.0
        },
        'priority': 'high',
        'models': ['GFS', 'NAM', 'HRRR'],
        'key_points': [
            {'name': 'Seattle', 'lat': 47.45, 'lon': -122.31, 'station': 'KSEA'},
            {'name': 'Portland', 'lat': 45.59, 'lon': -122.60, 'station': 'KPDX'},
            {'name': 'Spokane', 'lat': 47.62, 'lon': -117.53, 'station': 'KGEG'},
        ],
        'metar_stations': ['KSEA', 'KPDX', 'KGEG', 'KBLI', 'KEUG'],
        'buoys': [46041, 46050, 46029],
        'weather_features': ['atmospheric_rivers', 'orographic_enhancement', 'pineapple_express'],
    },
}


# Future expansion templates
REGION_TEMPLATES = {
    'conus_full': {
        'name': 'Continental United States',
        'description': 'Full CONUS coverage',
        'bounds': {
            'lat_min': 25.0,
            'lat_max': 50.0,
            'lon_min': -125.0,
            'lon_max': -65.0
        },
        'priority': 'medium',
        'models': ['GFS', 'NAM'],
        'key_points': [],
        'metar_stations': [],
        'buoys': [],
        'weather_features': [],
    },
    'alaska': {
        'name': 'Alaska',
        'description': 'Alaska region with extreme weather',
        'bounds': {
            'lat_min': 55.0,
            'lat_max': 72.0,
            'lon_min': -170.0,
            'lon_max': -130.0
        },
        'priority': 'low',
        'models': ['GFS'],
        'key_points': [
            {'name': 'Anchorage', 'lat': 61.22, 'lon': -149.90, 'station': 'PANC'},
            {'name': 'Fairbanks', 'lat': 64.82, 'lon': -147.86, 'station': 'PAFA'},
        ],
        'metar_stations': ['PANC', 'PAFA'],
        'buoys': [46001, 46080],
        'weather_features': ['polar_vortex', 'winter_storms'],
    },
    'hawaii': {
        'name': 'Hawaii',
        'description': 'Hawaiian Islands tropical weather',
        'bounds': {
            'lat_min': 18.0,
            'lat_max': 23.0,
            'lon_min': -161.0,
            'lon_max': -154.0
        },
        'priority': 'low',
        'models': ['GFS'],
        'key_points': [
            {'name': 'Honolulu', 'lat': 21.32, 'lon': -157.92, 'station': 'PHNL'},
        ],
        'metar_stations': ['PHNL', 'PHOG', 'PHTO'],
        'buoys': [51001, 51002, 51003],
        'weather_features': ['trade_winds', 'tropical_weather'],
    },
    'puerto_rico': {
        'name': 'Puerto Rico & USVI',
        'description': 'Caribbean tropical weather',
        'bounds': {
            'lat_min': 17.5,
            'lat_max': 18.7,
            'lon_min': -67.5,
            'lon_max': -64.5
        },
        'priority': 'low',
        'models': ['GFS'],
        'key_points': [
            {'name': 'San Juan', 'lat': 18.43, 'lon': -66.00, 'station': 'TJSJ'},
        ],
        'metar_stations': ['TJSJ', 'TJBQ'],
        'buoys': [41052, 42059],
        'weather_features': ['tropical_cyclones', 'trade_winds'],
    },
}


def validate_region(region_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate region configuration.

    Args:
        region_data: Region configuration dictionary

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check required fields
    required_fields = ['name', 'description', 'bounds', 'priority', 'models']
    for field in required_fields:
        if field not in region_data:
            errors.append(f"Missing required field: {field}")

    if errors:
        return False, errors

    # Validate bounds
    bounds = region_data['bounds']
    required_bounds = ['lat_min', 'lat_max', 'lon_min', 'lon_max']
    for bound in required_bounds:
        if bound not in bounds:
            errors.append(f"Missing bound: {bound}")
            continue

        value = bounds[bound]
        if 'lat' in bound:
            if not (-90 <= value <= 90):
                errors.append(f"Invalid {bound}: {value} (must be -90 to 90)")
        elif 'lon' in bound:
            if not (-180 <= value <= 180):
                errors.append(f"Invalid {bound}: {value} (must be -180 to 180)")

    # Check min < max
    if 'lat_min' in bounds and 'lat_max' in bounds:
        if bounds['lat_min'] >= bounds['lat_max']:
            errors.append(f"lat_min ({bounds['lat_min']}) must be < lat_max ({bounds['lat_max']})")

    if 'lon_min' in bounds and 'lon_max' in bounds:
        if bounds['lon_min'] >= bounds['lon_max']:
            errors.append(f"lon_min ({bounds['lon_min']}) must be < lon_max ({bounds['lon_max']})")

    # Validate priority
    valid_priorities = ['high', 'medium', 'low']
    if region_data['priority'] not in valid_priorities:
        errors.append(f"Invalid priority: {region_data['priority']} (must be one of {valid_priorities})")

    # Validate key points are within bounds
    if 'key_points' in region_data and bounds:
        for point in region_data['key_points']:
            if 'lat' in point and 'lon' in point:
                lat, lon = point['lat'], point['lon']
                if not (bounds['lat_min'] <= lat <= bounds['lat_max']):
                    errors.append(f"Key point {point.get('name', 'unknown')} lat {lat} outside bounds")
                if not (bounds['lon_min'] <= lon <= bounds['lon_max']):
                    errors.append(f"Key point {point.get('name', 'unknown')} lon {lon} outside bounds")

    # Validate station IDs format (basic check)
    if 'metar_stations' in region_data:
        for station in region_data['metar_stations']:
            if not isinstance(station, str) or len(station) != 4:
                errors.append(f"Invalid METAR station ID: {station} (should be 4 characters)")

    return len(errors) == 0, errors


def get_region(name: str) -> Optional[Dict[str, Any]]:
    """
    Get region configuration by name.

    Args:
        name: Region identifier

    Returns:
        Region configuration dictionary, or None if not found
    """
    return REGIONS.get(name)


def get_all_regions(priority: Optional[str] = None, include_templates: bool = False) -> List[str]:
    """
    Get list of all region names, optionally filtered by priority.

    Args:
        priority: Filter by priority level ('high', 'medium', 'low')
        include_templates: Include future expansion templates

    Returns:
        List of region identifiers
    """
    regions_dict = REGIONS.copy()

    if include_templates:
        regions_dict.update(REGION_TEMPLATES)

    if priority is None:
        return list(regions_dict.keys())

    return [
        name for name, config in regions_dict.items()
        if config.get('priority') == priority
    ]


def get_region_bounds(name: str) -> Optional[Tuple[float, float, float, float]]:
    """
    Get region bounds.

    Args:
        name: Region identifier

    Returns:
        Tuple of (lat_min, lat_max, lon_min, lon_max), or None if not found
    """
    region = get_region(name)
    if region and 'bounds' in region:
        bounds = region['bounds']
        return (
            bounds['lat_min'],
            bounds['lat_max'],
            bounds['lon_min'],
            bounds['lon_max']
        )
    return None


def get_region_key_points(name: str) -> List[Dict[str, Any]]:
    """
    Get list of key observation points for a region.

    Args:
        name: Region identifier

    Returns:
        List of key point dictionaries with name, lat, lon, station
    """
    region = get_region(name)
    if region and 'key_points' in region:
        return region['key_points']
    return []


def get_region_stations(name: str, obs_type: str = 'metar') -> List[Any]:
    """
    Get list of station IDs for a region.

    Args:
        name: Region identifier
        obs_type: Type of observation station ('metar' or 'buoy')

    Returns:
        List of station IDs (strings for METAR, integers for buoys)
    """
    region = get_region(name)
    if not region:
        return []

    if obs_type == 'metar':
        return region.get('metar_stations', [])
    elif obs_type == 'buoy':
        return region.get('buoys', [])
    else:
        return []


def get_region_models(name: str) -> List[str]:
    """
    Get list of models configured for a region.

    Args:
        name: Region identifier

    Returns:
        List of model names
    """
    region = get_region(name)
    if region and 'models' in region:
        return region['models']
    return []


def get_region_info(name: str) -> str:
    """
    Get formatted information about a region.

    Args:
        name: Region identifier

    Returns:
        Formatted string with region details
    """
    region = get_region(name)
    if not region:
        return f"Region '{name}' not found"

    info = []
    info.append(f"Region: {region['name']}")
    info.append(f"Description: {region['description']}")

    if 'bounds' in region:
        bounds = region['bounds']
        info.append(f"Bounds: {bounds['lat_min']}°N to {bounds['lat_max']}°N, "
                   f"{bounds['lon_min']}°E to {bounds['lon_max']}°E")

    info.append(f"Priority: {region['priority']}")
    info.append(f"Models: {', '.join(region.get('models', []))}")

    if 'key_points' in region:
        info.append(f"Key Points: {len(region['key_points'])}")
        for point in region['key_points']:
            info.append(f"  - {point['name']} ({point['station']})")

    if 'metar_stations' in region:
        info.append(f"METAR Stations: {len(region['metar_stations'])}")

    if 'buoys' in region:
        info.append(f"Buoys: {len(region['buoys'])}")

    if 'weather_features' in region:
        info.append(f"Weather Features: {', '.join(region['weather_features'])}")

    return '\n'.join(info)


def validate_all_regions() -> Dict[str, Tuple[bool, List[str]]]:
    """
    Validate all region configurations.

    Returns:
        Dictionary mapping region names to (is_valid, errors) tuples
    """
    results = {}

    for name, config in REGIONS.items():
        is_valid, errors = validate_region(config)
        results[name] = (is_valid, errors)

    return results


# Validate regions on module import
_validation_results = validate_all_regions()
_invalid_regions = [name for name, (valid, _) in _validation_results.items() if not valid]

if _invalid_regions:
    import warnings
    warnings.warn(f"Invalid region configurations detected: {', '.join(_invalid_regions)}")
