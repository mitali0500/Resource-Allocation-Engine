from math import asin, cos, radians, sin, sqrt

from .models import Location

EARTH_RADIUS_KM = 6371.0


def haversine_km(a: Location, b: Location) -> float:
    """Great-circle distance. Straight-line, so it underestimates road distance;
    acceptable for comparing algorithms because every algorithm sees the same distances."""
    dlat = radians(b.lat - a.lat)
    dlon = radians(b.lon - a.lon)
    h = sin(dlat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(b.lat)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


def travel_minutes(km: float, speed_kmh: float) -> float:
    return km / speed_kmh * 60.0
