const configuredApiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_BASE = import.meta.env.PROD ? "" : (configuredApiBase.startsWith("/") ? "http://localhost:8000" : configuredApiBase.replace(/\/+$/, ""));

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

  const url = new URL(`${API_BASE}/api/places`, window.location.origin);
  url.searchParams.set("destination", destination);
  if (pageToken) url.searchParams.set("page_token", pageToken);

  try {
    const res = await fetch(url.toString());
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || "Unable to load popular places.");
    }
    const data = await res.json();
    _cache.set(key, { expires: Date.now() + TTL_MS, data });
    return data;
  } catch {
    return { places: [], next_page_token: null, source: "error" };
  }
}

export { searchPlaces };
