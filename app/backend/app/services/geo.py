import math
from typing import Tuple


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth
    (specified in decimal degrees). Returns distance in kilometers (km).
    """
    r = 6371.0  # Earth's radius in kilometers

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return round(r * c, 2)


def estimate_travel_time_minutes(distance_km: float) -> int:
    """
    Estimates city traffic travel time in minutes based on distance.
    Assumes average urban travel speed with traffic lights (~25 km/h).
    """
    if distance_km <= 0.1:
        return 1
    # 2.5 minutes per km (~24 km/h) with a minimum base time
    return max(2, int(round(distance_km * 2.4)))
