"""Server-side Google Maps Platform integration for attractions and geocoding."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from math import asin, cos, radians, sin, sqrt
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.config import Settings
from app.models import PlaceResult, PlacesResponse

logger = logging.getLogger(__name__)
_CACHE: dict[str, tuple[datetime, PlacesResponse]] = {}
_CACHE_TTL = timedelta(minutes=30)
_MAX_ATTRACTIONS = 30
_RADIUS_METERS = 50_000.0


class GoogleMapsServiceError(RuntimeError):
    """Safe failure from Google Maps Platform without leaking the API key."""


def _cache_key(destination: str, page_token: str | None) -> str:
    return f"{' '.join(destination.lower().split())}::{page_token or 'first'}"


def _field_mask() -> str:
    return ("places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,"
            "places.types,places.primaryTypeDisplayName,places.editorialSummary,places.photos,places.location,"
            "places.regularOpeningHours,places.googleMapsUri,places.businessStatus")


def _headers(api_key: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": _field_mask()}


def _distance_km(origin: tuple[float, float], place: dict[str, Any]) -> float | None:
    location = place.get("location") or {}
    if location.get("latitude") is None or location.get("longitude") is None:
        return None
    d_lat = radians(location["latitude"] - origin[0]); d_lng = radians(location["longitude"] - origin[1])
    a = sin(d_lat / 2) ** 2 + cos(radians(origin[0])) * cos(radians(location["latitude"])) * sin(d_lng / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _normalize(place: dict[str, Any], origin: tuple[float, float]) -> PlaceResult | None:
    if place.get("businessStatus") == "CLOSED_PERMANENTLY": return None
    name = place.get("displayName", {}).get("text"); place_id = place.get("id")
    if not name or not place_id: return None
    location = place.get("location") or {}; primary = place.get("primaryTypeDisplayName", {}).get("text")
    types = place.get("types") or []; category = primary or next((x.replace("_", " ").title() for x in types if x not in {"point_of_interest", "establishment"}), "Tourist attraction")
    photo_name = (place.get("photos") or [{}])[0].get("name")
    distance = _distance_km(origin, place)
    return PlaceResult(id=place_id, name=name, rating=place.get("rating"), user_reviews_count=place.get("userRatingCount"), category=category,
        description=place.get("editorialSummary", {}).get("text") or f"Popular tourist attraction near {place.get('formattedAddress', name)}.",
        distance=(f"{round(distance * 1000)} m from destination center" if distance is not None and distance < 1 else f"{distance:.1f} km from destination center" if distance is not None else None),
        address=place.get("formattedAddress"), image_url=f"/api/places/photo?name={quote(photo_name, safe='')}" if photo_name else None,
        photo_name=photo_name, latitude=location.get("latitude"), longitude=location.get("longitude"),
        opening_hours=(place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or [], google_maps_url=place.get("googleMapsUri"))


async def geocode_destination(destination: str, settings: Settings) -> tuple[float, float]:
    """Convert a user-entered destination into Google Geocoding coordinates."""
    if not settings.google_maps_api_key:
        raise GoogleMapsServiceError("Google Maps is not configured. Add GOOGLE_MAPS_API_KEY to backend/.env.")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://maps.googleapis.com/maps/api/geocode/json", params={"address": destination, "key": settings.google_maps_api_key})
            response.raise_for_status(); data = response.json()
    except httpx.HTTPError as exc:
        logger.exception("Google Geocoding request failed.")
        raise GoogleMapsServiceError("Google Geocoding is unavailable. Please try again.") from exc
    if data.get("status") in {"REQUEST_DENIED", "OVER_DAILY_LIMIT"}:
        logger.warning("Google Geocoding denied request: %s", data.get("status"))
        raise GoogleMapsServiceError("Google Maps rejected the configured API key or quota.")
    location = ((data.get("results") or [{}])[0].get("geometry") or {}).get("location")
    if not location: raise GoogleMapsServiceError("Google Maps could not find that destination.")
    return float(location["lat"]), float(location["lng"])


async def _places_search(client: httpx.AsyncClient, api_key: str, destination: str, center: tuple[float, float]) -> list[dict[str, Any]]:
    nearby = {"includedTypes": ["tourist_attraction"], "maxResultCount": 20, "rankPreference": "POPULARITY", "locationRestriction": {"circle": {"center": {"latitude": center[0], "longitude": center[1]}, "radius": _RADIUS_METERS}}}
    text = {"textQuery": f"top tourist attractions in {destination}", "maxResultCount": 20, "locationBias": {"circle": {"center": {"latitude": center[0], "longitude": center[1]}, "radius": _RADIUS_METERS}}}
    first = await client.post("https://places.googleapis.com/v1/places:searchNearby", headers=_headers(api_key), json=nearby); first.raise_for_status()
    second = await client.post("https://places.googleapis.com/v1/places:searchText", headers=_headers(api_key), json=text); second.raise_for_status()
    return first.json().get("places", []) + second.json().get("places", [])


async def search_popular_places(destination: str, page_token: str | None, settings: Settings) -> PlacesResponse:
    destination = destination.strip()
    if not destination: return PlacesResponse(places=[], next_page_token=None, source="empty")
    key = _cache_key(destination, page_token); cached = _CACHE.get(key)
    if cached and cached[0] > datetime.now(timezone.utc): return cached[1]
    if not settings.google_maps_api_key:
        raise GoogleMapsServiceError("Google Places is not configured. Add GOOGLE_MAPS_API_KEY to backend/.env.")
    center = await geocode_destination(destination, settings)
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            raw_places = await _places_search(client, settings.google_maps_api_key, destination, center)
    except httpx.HTTPStatusError as exc:
        logger.warning("Google Places rejected request with HTTP %s", exc.response.status_code)
        raise GoogleMapsServiceError("Google Places rejected the configured API key or quota.") from exc
    except httpx.HTTPError as exc:
        logger.exception("Google Places request failed.")
        raise GoogleMapsServiceError("Google Places is unavailable. Please try again.") from exc
    unique: dict[str, PlaceResult] = {}
    for raw in raw_places:
        place = _normalize(raw, center)
        if place: unique.setdefault(place.id, place)
    places = sorted(unique.values(), key=lambda item: (item.rating or 0, item.user_reviews_count or 0), reverse=True)[:_MAX_ATTRACTIONS]
    result = PlacesResponse(places=places, next_page_token=None, source="google_places", destination_coordinates={"lat": center[0], "lng": center[1]})
    _CACHE[key] = (datetime.now(timezone.utc) + _CACHE_TTL, result)
    return result


async def fetch_place_photo(name: str, settings: Settings) -> StreamingResponse:
    if not settings.google_maps_api_key: raise HTTPException(status_code=503, detail="Google Places is not configured.")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(f"https://places.googleapis.com/v1/{name}/media", params={"maxWidthPx": 640, "maxHeightPx": 420, "key": settings.google_maps_api_key})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=404, detail="Place photo unavailable.") from exc
    return StreamingResponse(BytesIO(response.content), media_type=response.headers.get("content-type", "image/jpeg"))
