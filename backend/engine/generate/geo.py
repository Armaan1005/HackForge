"""States, cities, rural towns and distance helpers. Coordinates are real city centroids;
every point generated around them is synthetic."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

KM_PER_MILE = 1.609344


@dataclass(frozen=True)
class City:
    name: str
    state: str
    lat: float
    lon: float
    weight: float  # share of members/providers
    is_rural: bool = False
    catchment: int = 0  # population served (used by exoneration EX1)


CITIES: list[City] = [
    City("Mumbai", "MH", 19.0760, 72.8777, 20, catchment=12_400_000),
    City("Pune", "MH", 18.5204, 73.8567, 10, catchment=6_600_000),
    City("Nagpur", "MH", 21.1458, 79.0882, 6, catchment=2_900_000),
    City("Gadchiroli", "MH", 20.1849, 79.9948, 2.5, True, 1_100_000),
    City("Bengaluru", "KA", 12.9716, 77.5946, 14, catchment=11_000_000),
    City("Mysuru", "KA", 12.2958, 76.6394, 4, catchment=1_100_000),
    City("Hubballi", "KA", 15.3647, 75.1240, 3, catchment=1_000_000),
    City("Chennai", "TN", 13.0827, 80.2707, 12, catchment=9_000_000),
    City("Coimbatore", "TN", 11.0168, 76.9558, 5, catchment=2_200_000),
    City("Madurai", "TN", 9.9252, 78.1198, 4, catchment=1_600_000),
    City("Ramanathapuram", "TN", 9.3639, 78.8395, 2.5, True, 1_350_000),
    City("Delhi", "DL", 28.6139, 77.2090, 16, catchment=19_000_000),
    City("Lucknow", "UP", 26.8467, 80.9462, 7, catchment=3_600_000),
    City("Kanpur", "UP", 26.4499, 80.3319, 6, catchment=3_000_000),
    City("Varanasi", "UP", 25.3176, 82.9739, 4, catchment=1_700_000),
    City("Bahraich", "UP", 27.5743, 81.5959, 2.5, True, 3_500_000),
    City("Ahmedabad", "GJ", 23.0225, 72.5714, 9, catchment=8_000_000),
    City("Surat", "GJ", 21.1702, 72.8311, 7, catchment=6_500_000),
    City("Vadodara", "GJ", 22.3072, 73.1812, 4, catchment=2_100_000),
    City("Dahod", "GJ", 22.8352, 74.2553, 2.5, True, 2_100_000),
]
CITY_BY_NAME = {c.name: c for c in CITIES}
STATES = ["MH", "KA", "TN", "DL", "UP", "GJ"]
PIN_PREFIX = {"MH": 4, "KA": 5, "TN": 6, "DL": 1, "UP": 2, "GJ": 3}


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km; works on scalars or numpy arrays."""
    lat1, lon1, lat2, lon2 = (np.radians(x) for x in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def offset_point(lat: float, lon: float, km: float, bearing_rad: float) -> tuple[float, float]:
    """Point `km` away from (lat, lon) along a bearing (flat-earth approximation, fine < 100 km)."""
    dlat = (km * math.cos(bearing_rad)) / 110.574
    dlon = (km * math.sin(bearing_rad)) / (111.320 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def jitter(rng: np.random.Generator, city: City, max_km: float) -> tuple[float, float]:
    """Random point within max_km of the city centroid, rounded to 5 decimals."""
    km = max_km * math.sqrt(rng.random())
    lat, lon = offset_point(city.lat, city.lon, km, rng.random() * 2 * math.pi)
    return round(lat, 5), round(lon, 5)


def pincode(rng: np.random.Generator, city: City) -> str:
    """Synthetic 6-digit pincode with the state's leading digit and a stable city block."""
    block = sum(ord(ch) for ch in city.name) % 90 + 10
    if city.state == "DL":
        return f"11{block % 100:02d}{int(rng.integers(0, 100)):02d}"
    return f"{PIN_PREFIX[city.state]}{block:02d}{int(rng.integers(0, 1000)):03d}"
