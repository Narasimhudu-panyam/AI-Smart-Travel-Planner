import { API_BASE_URL } from "./api";

// Simple in-memory cache with TTL to reduce API calls during a session
const _cache = new Map(); // key -> {expires, data}
const TTL_MS = 1000 * 60 * 10; // 10 minutes

function _cacheKey(destination, pageToken) {
  return `${destination?.trim().toLowerCase() || ""}::${pageToken || "first"}`;
}

async function searchPlaces(destination, pageToken = null) {
  if (!destination || !destination.trim()) {
    return { places: [], next_page_token: null, source: "empty" };
  }

  const key = _cacheKey(destination, pageToken);
  const cached = _cache.get(key);
  if (cached && cached.expires > Date.now()) {
    return cached.data;
  }

  const url = new URL(`${API_BASE_URL}/api/places`, window.location.origin);
  url.searchParams.set("destination", destination.trim());
  if (pageToken) url.searchParams.set("page_token", pageToken);

  try {
    const res = await fetch(url.toString());
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      const msg = errorData.detail || `Server returned HTTP ${res.status}`;
      return { places: [], next_page_token: null, source: "unavailable", message: msg };
    }
    const data = await res.json();
    _cache.set(key, { expires: Date.now() + TTL_MS, data });
    return data;
  } catch (err) {
    return { places: [], next_page_token: null, source: "error", message: err.message || "Network error loading places." };
  }
}

export { searchPlaces };
