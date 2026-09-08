"""Server-side Google Maps Platform integration for attractions and geocoding."""
from __future__ import annotations

import logging
import re
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


def _redact_key(url: str) -> str:
    """Remove API key parameters from URL for safe logging."""
    return re.sub(r"([?&]key=)[^&]+", r"\1[REDACTED]", url)


def _cache_key(destination: str, page_token: str | None) -> str:
    return f"{' '.join(destination.lower().split())}::{page_token or 'first'}"


def _field_mask() -> str:
    return (
        "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,"
        "places.types,places.primaryTypeDisplayName,places.editorialSummary,places.photos,places.location,"
        "places.regularOpeningHours,places.googleMapsUri,places.businessStatus"
    )


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _field_mask(),
    }


def _distance_km(origin: tuple[float, float] | None, place: dict[str, Any]) -> float | None:
    if not origin:
        return None
    location = place.get("location") or {}
    if location.get("latitude") is None or location.get("longitude") is None:
        return None
    d_lat = radians(location["latitude"] - origin[0])
    d_lng = radians(location["longitude"] - origin[1])
    a = sin(d_lat / 2) ** 2 + cos(radians(origin[0])) * cos(radians(location["latitude"])) * sin(d_lng / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def _normalize(place: dict[str, Any], origin: tuple[float, float] | None = None) -> PlaceResult | None:
    if place.get("businessStatus") == "CLOSED_PERMANENTLY":
        return None
    
    # Handle New Places API format
    name = place.get("displayName", {}).get("text")
    place_id = place.get("id")
    location = place.get("location") or {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    address = place.get("formattedAddress")
    rating = place.get("rating")
    user_reviews_count = place.get("userRatingCount")
    description = place.get("editorialSummary", {}).get("text")
    photo_list = place.get("photos") or []
    photo_name = photo_list[0].get("name") if photo_list else None
    opening_hours = (place.get("regularOpeningHours") or {}).get("weekdayDescriptions") or []
    google_maps_url = place.get("googleMapsUri")
    
    # Handle Legacy Places API format fallback if encountered
    if not name and "name" in place:
        name = place.get("name")
        place_id = place.get("place_id")
        geo_loc = (place.get("geometry") or {}).get("location") or {}
        latitude = geo_loc.get("lat")
        longitude = geo_loc.get("lng")
        address = place.get("formatted_address") or place.get("vicinity")
        rating = place.get("rating")
        user_reviews_count = place.get("user_ratings_total")
        google_maps_url = f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else None

    if not name or not place_id:
        return None

    primary = place.get("primaryTypeDisplayName", {}).get("text")
    types = place.get("types") or []
    category = primary or next(
        (x.replace("_", " ").title() for x in types if x not in {"point_of_interest", "establishment"}),
        "Tourist attraction",
    )

    distance = _distance_km(origin, place) if origin else None
    distance_str = None
    if distance is not None:
        if distance < 1:
            distance_str = f"{round(distance * 1000)} m from destination center"
        else:
            distance_str = f"{distance:.1f} km from destination center"

    desc = description or f"Popular tourist attraction in {address or name}."
    image_url = f"/api/places/photo?name={quote(photo_name, safe='')}" if photo_name else None

    return PlaceResult(
        id=place_id,
        name=name,
        rating=rating,
        user_reviews_count=user_reviews_count,
        category=category,
        description=desc,
        distance=distance_str,
        address=address,
        image_url=image_url,
        photo_name=photo_name,
        latitude=latitude,
        longitude=longitude,
        opening_hours=opening_hours,
        google_maps_url=google_maps_url,
    )


async def geocode_destination(destination: str, settings: Settings) -> tuple[float, float] | None:
    """Convert a user-entered destination into coordinates using Google Geocoding."""
    if not settings.google_maps_api_key:
        logger.info("Google Maps API key not configured; skipping geocoding.")
        return None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": destination, "key": settings.google_maps_api_key}
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params)
            data = response.json()
            
            if response.status_code != 200 or data.get("status") != "OK":
                safe_url = _redact_key(str(response.url))
                logger.warning(
                    "Google Geocoding non-OK response: url=%s status_code=%s api_status=%s error_message=%s",
                    safe_url,
                    response.status_code,
                    data.get("status"),
                    data.get("error_message", "None"),
                )
                return None
                
            location = ((data.get("results") or [{}])[0].get("geometry") or {}).get("location")
            if location and "lat" in location and "lng" in location:
                return float(location["lat"]), float(location["lng"])
            return None
    except Exception as exc:
        logger.warning("Google Geocoding request failed for destination '%s': %s", destination, exc)
        return None


async def _places_search(
    client: httpx.AsyncClient,
    api_key: str,
    destination: str,
    center: tuple[float, float] | None,
) -> list[dict[str, Any]]:
    places: list[dict[str, Any]] = []

    # 1. Places API (New) Text Search
    text_url = "https://places.googleapis.com/v1/places:searchText"
    text_payload: dict[str, Any] = {
        "textQuery": f"top tourist attractions in {destination}",
        "maxResultCount": 20,
    }
    if center:
        text_payload["locationBias"] = {
            "circle": {"center": {"latitude": center[0], "longitude": center[1]}, "radius": _RADIUS_METERS}
        }

    try:
        res = await client.post(text_url, headers=_headers(api_key), json=text_payload)
        if res.status_code == 200:
            places.extend(res.json().get("places", []))
        else:
            safe_url = _redact_key(text_url)
            logger.warning(
                "Google Places Text Search error: url=%s status=%s body=%s",
                safe_url,
                res.status_code,
                res.text[:500],
            )
    except Exception as exc:
        logger.warning("Google Places Text Search request failed: %s", exc)

    # 2. Places API (New) Search Nearby if center coordinates exist
    if center:
        nearby_url = "https://places.googleapis.com/v1/places:searchNearby"
        nearby_payload = {
            "includedTypes": ["tourist_attraction"],
            "maxResultCount": 20,
            "rankPreference": "POPULARITY",
            "locationRestriction": {
                "circle": {"center": {"latitude": center[0], "longitude": center[1]}, "radius": _RADIUS_METERS}
            },
        }
        try:
            res_nearby = await client.post(nearby_url, headers=_headers(api_key), json=nearby_payload)
            if res_nearby.status_code == 200:
                places.extend(res_nearby.json().get("places", []))
            else:
                logger.warning(
                    "Google Places Nearby Search error: status=%s body=%s",
                    res_nearby.status_code,
                    res_nearby.text[:500],
                )
        except Exception as exc:
            logger.warning("Google Places Nearby Search request failed: %s", exc)

    return places


async def search_popular_places(destination: str, page_token: str | None, settings: Settings) -> PlacesResponse:
    destination = destination.strip()
    if not destination:
        return PlacesResponse(places=[], next_page_token=None, source="empty")

    key = _cache_key(destination, page_token)
    cached = _CACHE.get(key)
    if cached and cached[0] > datetime.now(timezone.utc):
        return cached[1]

    if not settings.google_maps_api_key:
        logger.info("Google Maps key not configured. Returning empty places with status note.")
        return PlacesResponse(
            places=[],
            next_page_token=None,
            source="maps_not_configured",
            destination_coordinates=None,
        )

    center = await geocode_destination(destination, settings)
    dest_coords = {"lat": center[0], "lng": center[1]} if center else None

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            raw_places = await _places_search(client, settings.google_maps_api_key, destination, center)
    except Exception as exc:
        logger.exception("Google Places search encountered an unexpected exception: %s", exc)
        raw_places = []

    unique: dict[str, PlaceResult] = {}
    for raw in raw_places:
        place = _normalize(raw, center)
        if place:
            unique.setdefault(place.id, place)

    places = sorted(
        unique.values(),
        key=lambda item: (item.rating or 0, item.user_reviews_count or 0),
        reverse=True,
    )[:_MAX_ATTRACTIONS]

    source = "google_places" if places else ("google_places_empty" if center else "google_places_unavailable")
    result = PlacesResponse(
        places=places,
        next_page_token=None,
        source=source,
        destination_coordinates=dest_coords,
    )
    _CACHE[key] = (datetime.now(timezone.utc) + _CACHE_TTL, result)
    return result


async def fetch_place_photo(name: str, settings: Settings) -> StreamingResponse:
    if not settings.google_maps_api_key:
        raise HTTPException(status_code=503, detail="Google Places is not configured.")
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            response = await client.get(
                f"https://places.googleapis.com/v1/{name}/media",
                params={"maxWidthPx": 640, "maxHeightPx": 420, "key": settings.google_maps_api_key},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=404, detail="Place photo unavailable.") from exc
    return StreamingResponse(BytesIO(response.content), media_type=response.headers.get("content-type", "image/jpeg"))

