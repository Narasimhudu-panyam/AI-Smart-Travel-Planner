import React, { useEffect, useMemo, useRef, useState } from "react";
import { searchPlaces } from "./placesService";
import { Loader2, Sparkles, MapPin } from "lucide-react";
import "./places.css";

function SkeletonCard() {
  return (
    <div className="place-card skeleton">
      <div className="place-image" />
      <div className="place-info">
        <div className="s-line short" />
        <div className="s-line" />
        <div className="s-line" />
      </div>
    </div>
  );
}

function toSelectedAttraction(place) {
  return {
    id: place.id,
    name: place.name,
    rating: place.rating ?? null,
    category: place.category ?? null,
    description: place.description ?? null,
    distance: place.distance ?? null,
    user_reviews_count: place.user_reviews_count ?? null,
    latitude: place.latitude ?? null,
    longitude: place.longitude ?? null,
    opening_hours: place.opening_hours ?? [],
    google_maps_url: place.google_maps_url ?? null,
  };
}

export default function PopularPlaces({ destination, selected = [], onChange }) {
  const [loading, setLoading] = useState(false);
  const [places, setPlaces] = useState([]);
  const [nextPageToken, setNextPageToken] = useState(null);
  const [statusSource, setStatusSource] = useState(null);
  const [statusMessage, setStatusMessage] = useState(null);
  const [query, setQuery] = useState("");
  const [sortByRating, setSortByRating] = useState(false);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      if (!destination || !destination.trim()) {
        setPlaces([]);
        setStatusSource("empty");
        setStatusMessage(null);
        return;
      }

      setLoading(true);
      setPlaces([]);
      setNextPageToken(null);
      setStatusSource(null);
      setStatusMessage(null);

      try {
        const res = await searchPlaces(destination);
        if (!mounted) return;
        const placeList = res.places || [];
        setPlaces(placeList);
        setNextPageToken(res.next_page_token || null);
        setStatusSource(res.source || null);
        setStatusMessage(res.message || null);
        
        if (placeList.length > 0) {
          onChangeRef.current(placeList.map(toSelectedAttraction));
        } else {
          onChangeRef.current([]);
        }
      } catch (err) {
        if (!mounted) return;
        setStatusSource("error");
        setStatusMessage(err.message || "Unable to fetch popular places.");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    const timer = setTimeout(() => {
      load();
    }, 300);

    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, [destination]);

  async function loadMore() {
    if (!nextPageToken) return;
    setLoading(true);
    try {
      const res = await searchPlaces(destination, nextPageToken);
      setPlaces((p) => [...p, ...(res.places || [])]);
      setNextPageToken(res.next_page_token || null);
    } catch {
      // Ignore pagination error
    } finally {
      setLoading(false);
    }
  }

  function isSelected(place) {
    return selected.some((s) => s.id === place.id);
  }

  function toggleSelect(place) {
    if (isSelected(place)) {
      onChange(selected.filter((s) => s.id !== place.id));
    } else {
      onChange([...selected, toSelectedAttraction(place)]);
    }
  }

  function selectAllVisible() {
    const visible = filteredPlaces;
    const merged = [...selected];
    for (const p of visible) {
      if (!merged.some((m) => m.id === p.id)) {
        merged.push(toSelectedAttraction(p));
      }
    }
    onChange(merged);
  }

  function clearAllVisible() {
    const visible = filteredPlaces.map((p) => p.id);
    onChange(selected.filter((s) => !visible.includes(s.id)));
  }

  const filteredPlaces = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = places.slice();
    if (q) list = list.filter((p) => p.name.toLowerCase().includes(q) || (p.category || "").toLowerCase().includes(q));
    if (sortByRating) {
      list.sort((a, b) => (b.rating || 0) - (a.rating || 0) || (b.user_reviews_count || 0) - (a.user_reviews_count || 0));
    }
    return list;
  }, [places, query, sortByRating]);

  const showFallbackNotice = ["maps_not_configured", "unavailable", "error", "google_places_unavailable"].includes(statusSource);

  return (
    <div className="popular-places">
      <div className="panel-heading">
        <h3>
          <MapPin size={18} style={{ marginRight: 6, verticalAlign: "middle" }} />
          Popular Places to Visit
        </h3>
        {places.length > 0 && (
          <span className="places-count-badge">
            {selected.length} of {places.length} selected
          </span>
        )}
      </div>

      {places.length > 0 && (
        <div className="places-controls">
          <input
            placeholder="Search discovered places..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="controls">
            <button type="button" onClick={selectAllVisible}>Select all</button>
            <button type="button" onClick={clearAllVisible}>Unselect visible</button>
            <button type="button" onClick={() => setSortByRating((s) => !s)}>{sortByRating ? "Unsort" : "Sort by rating"}</button>
          </div>
        </div>
      )}

      {loading && places.length === 0 ? (
        <div className="places-grid">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : showFallbackNotice ? (
        <div className="places-assistant-card" style={{ padding: "16px", borderRadius: "12px", background: "rgba(99, 102, 241, 0.08)", border: "1px dashed rgba(99, 102, 241, 0.3)", marginTop: "10px" }}>
          <div style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
            <Sparkles size={20} style={{ color: "#6366f1", flexShrink: 0, marginTop: 2 }} />
            <div>
              <strong style={{ display: "block", marginBottom: 4, color: "var(--text-primary, #1e293b)" }}>
                AI Destination Discovery Active
              </strong>
              <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--text-muted, #64748b)", lineHeight: 1.5 }}>
                {destination
                  ? `Our AI Assistant will dynamically discover, prioritize, and include signature attractions and authentic spots in ${destination} for you.`
                  : "Enter any destination to see popular highlights, or let the AI Assistant plan them automatically."}
              </p>
            </div>
          </div>
        </div>
      ) : filteredPlaces.length === 0 && places.length > 0 ? (
        <p className="muted" style={{ padding: "12px 0" }}>No places matched your search filter.</p>
      ) : filteredPlaces.length === 0 ? (
        <div className="places-assistant-card" style={{ padding: "16px", borderRadius: "12px", background: "rgba(99, 102, 241, 0.08)", border: "1px dashed rgba(99, 102, 241, 0.3)", marginTop: "10px" }}>
          <div style={{ display: "flex", gap: "10px", alignItems: "flex-start" }}>
            <Sparkles size={20} style={{ color: "#6366f1", flexShrink: 0, marginTop: 2 }} />
            <div>
              <strong style={{ display: "block", marginBottom: 4 }}>AI Assistant Ready</strong>
              <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--text-muted, #64748b)" }}>
                No specific places selected. The AI Assistant will curate the best activities, landmarks, and restaurants for your travel style.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="places-grid">
          {filteredPlaces.map((place) => (
            <label key={place.id} className={"place-card" + (isSelected(place) ? " selected" : "") }>
              <input
                type="checkbox"
                checked={isSelected(place)}
                onChange={() => toggleSelect(place)}
              />
              <div className="place-image">
                {place.image_url ? (
                  <img src={place.image_url} alt={place.name} />
                ) : (
                  <div className="no-image" />
                )}
              </div>
              <div className="place-info">
                <div className="place-row">
                  <strong>{place.name}</strong>
                  <span className="rating">
                    {place.rating ? `⭐${place.rating}${place.user_reviews_count ? ` (${place.user_reviews_count})` : ""}` : ""}
                  </span>
                </div>
                <div className="place-row small muted">{place.category}</div>
                <div className="place-row small">{place.description}</div>
                {place.distance && <div className="place-row tiny muted">{place.distance}</div>}
              </div>
            </label>
          ))}
        </div>
      )}

      <div className="places-footer">
        {nextPageToken && (
          <button className="primary-button" type="button" onClick={loadMore} disabled={loading}>
            {loading ? <Loader2 className="spin" size={16} /> : "Load more"}
          </button>
        )}
      </div>
    </div>
  );
}
