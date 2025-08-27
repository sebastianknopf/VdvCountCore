import math

def haversine_distance(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    EARTH_RADIUS_M = 6371000
    
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = (math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    
    distance = EARTH_RADIUS_M * c
    
    return distance
