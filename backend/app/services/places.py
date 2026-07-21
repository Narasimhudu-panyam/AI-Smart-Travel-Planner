"""Free OpenStreetMap services for destination geocoding and nearby places."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import Settings
from app.models import PlaceResult, PlacesResponse

logger = logging.getLogger(__name__)
_PLACES_CACHE: dict[str, tuple[datetime, PlacesResponse]] = {}
_GEOCODE_CACHE: dict[str, tuple[datetime, tuple[float, float]]] = {}
_CACHE_TTL = timedelta(minutes=30)
_MAX_ATTRACTIONS = 30
_RADIUS_METERS = 25_000
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OSM_HEADERS = {"User-Agent": "AI-Smart-Travel-Planner/1.0 (OpenStreetMap place search)"}


class OpenStreetMapServiceError(RuntimeError):
    """Safe error raised when a free OpenStreetMap service cannot respond."""


def _cache_key(destination: str, page_token: str | None = None) -> str:
    return f"{' '.join(destination.lower().split())}::{page_token or 'first'}"


def _distance_km(origin: tuple[float, float], latitude: float, longitude: float) -> float:
    d_lat = radians(latitude - origin[0])
    d_lng = radians(longitude - origin[1])
    a = sin(d_lat / 2) ** 2 + cos(radians(origin[0])) * cos(radians(latitude)) * sin(d_lng / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _format_distance(distance_km: float) -> str:
    return f"{round(distance_km * 1000)} m from destination center" if distance_km < 1 else f"{distance_km:.1f} km from destination center"


def _distance_sort_key(place: PlaceResult) -> float:
    if not place.distance:
        return float("inf")
    value, unit, *_ = place.distance.split()
    return float(value) / 1000 if unit == "m" else float(value)


def _place_category(tags: dict[str, str]) -> str:
    if tags.get("tourism") == "museum": return "Museum"
    if tags.get("tourism") == "viewpoint": return "Viewpoint"
    if tags.get("tourism") in {"attraction", "gallery", "zoo", "theme_park"}: return "Tourist attraction"
    if tags.get("natural") == "beach": return "Beach"
    if tags.get("leisure") in {"park", "garden", "nature_reserve"}: return "Park"
    if tags.get("amenity") in {"restaurant", "cafe", "fast_food", "bar", "pub"}: return "Restaurant"
    if tags.get("historic"): return "Historical place"
    if tags.get("shop"): return "Shopping"
    return "Place of interest"


def _address(tags: dict[str, str]) -> str | None:
    parts = [tags[key] for key in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city") if tags.get(key)]
    return ", ".join(parts) or None


def _coordinates(element: dict[str, Any]) -> tuple[float, float] | None:
    latitude = element.get("lat")
    longitude = element.get("lon")
    if latitude is None or longitude is None:
        center = element.get("center") or {}
        latitude, longitude = center.get("lat"), center.get("lon")
    if latitude is None or longitude is None:
        return None
    return float(latitude), float(longitude)


def _normalize(element: dict[str, Any], origin: tuple[float, float]) -> PlaceResult | None:
    tags = element.get("tags") or {}
    name = tags.get("name")
    coordinates = _coordinates(element)
    if not name or coordinates is None:
        return None
    latitude, longitude = coordinates
    element_type, osm_id = element.get("type"), element.get("id")
    if not element_type or osm_id is None:
        return None
    distance = _distance_km(origin, latitude, longitude)
    description = tags.get("description") or f"{_place_category(tags)} near your destination."
    return PlaceResult(
        id=f"{element_type}:{osm_id}",
        name=name,
        rating=None,
        user_reviews_count=None,
        category=_place_category(tags),
        description=description,
        distance=_format_distance(distance),
        address=_address(tags),
        image_url=None,
        photo_name=None,
        latitude=latitude,
        longitude=longitude,
        opening_hours=[tags["opening_hours"]] if tags.get("opening_hours") else [],
        # Retained solely to preserve the existing API response schema.
        google_maps_url=f"https://www.openstreetmap.org/{element_type}/{osm_id}",
    )


async def geocode_destination(destination: str, settings: Settings) -> tuple[float, float]:
    """Resolve a destination with Nominatim; no API key or billing is required."""
    key = " ".join(destination.lower().split())
    cached = _GEOCODE_CACHE.get(key)
    if cached and cached[0] > datetime.now(timezone.utc):
        return cached[1]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), headers=_OSM_HEADERS) as client:
            response = await client.get(_NOMINATIM_URL, params={"q": destination, "format": "jsonv2", "limit": 1, "addressdetails": 1})
            response.raise_for_status()
            results = response.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("Nominatim geocoding failed for %r: %s", destination, exc)
        raise OpenStreetMapServiceError("Destination search is temporarily unavailable.") from exc
    if not results:
        raise OpenStreetMapServiceError("OpenStreetMap could not find that destination.")
    coordinates = (float(results[0]["lat"]), float(results[0]["lon"]))
    _GEOCODE_CACHE[key] = (datetime.now(timezone.utc) + _CACHE_TTL, coordinates)
    return coordinates


def _overpass_query(latitude: float, longitude: float) -> str:
    return f"""
    [out:json][timeout:15];
    (
      nwr["tourism"~"attraction|museum|gallery|viewpoint|zoo|theme_park"](around:{_RADIUS_METERS},{latitude},{longitude});
      nwr["natural"="beach"](around:{_RADIUS_METERS},{latitude},{longitude});
      nwr["leisure"~"park|garden|nature_reserve"](around:{_RADIUS_METERS},{latitude},{longitude});
      nwr["amenity"~"restaurant|cafe|fast_food|bar|pub"](around:{_RADIUS_METERS},{latitude},{longitude});
      nwr["historic"](around:{_RADIUS_METERS},{latitude},{longitude});
      nwr["shop"~"mall|department_store|marketplace|boutique"](around:{_RADIUS_METERS},{latitude},{longitude});
    );
    out center tags;
    """


async def search_popular_places(destination: str, page_token: str | None, settings: Settings) -> PlacesResponse:
    """Return an API-compatible places payload from Nominatim and Overpass."""
    destination = destination.strip()
    if not destination:
        return PlacesResponse(places=[], next_page_token=None, source="empty")
    key = _cache_key(destination, page_token)
    cached = _PLACES_CACHE.get(key)
    if cached and cached[0] > datetime.now(timezone.utc):
        return cached[1]
    try:
        center = await geocode_destination(destination, settings)
    except OpenStreetMapServiceError as exc:
        logger.warning("Unable to geocode %r for place search: %s", destination, exc)
        return PlacesResponse(places=[], next_page_token=None, source="openstreetmap", destination_coordinates=None)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0), headers=_OSM_HEADERS) as client:
            response = await client.post(_OVERPASS_URL, data={"data": _overpass_query(*center)})
            response.raise_for_status()
            elements = response.json().get("elements", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Overpass place search failed for %r: %s", destination, exc)
        return PlacesResponse(places=[], next_page_token=None, source="openstreetmap", destination_coordinates={"lat": center[0], "lng": center[1]})
    unique: dict[str, PlaceResult] = {}
    for element in elements:
        place = _normalize(element, center)
        if place:
            unique.setdefault(place.id, place)
    places = sorted(unique.values(), key=_distance_sort_key)[:_MAX_ATTRACTIONS]
    result = PlacesResponse(places=places, next_page_token=None, source="openstreetmap", destination_coordinates={"lat": center[0], "lng": center[1]})
    _PLACES_CACHE[key] = (datetime.now(timezone.utc) + _CACHE_TTL, result)
    return result


async def fetch_place_photo(name: str, settings: Settings):
    """Preserve the existing endpoint without depending on a proprietary photo API."""
    raise HTTPException(status_code=404, detail="Place photo unavailable.")
