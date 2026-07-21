import React, { useEffect, useMemo, useRef, useState } from "react";
import { searchPlaces } from "./placesService";
import { Loader2 } from "lucide-react";
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
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [sortByRating, setSortByRating] = useState(false);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      setError(null);
      setPlaces([]);
      setNextPageToken(null);
      try {
        const res = await searchPlaces(destination || "");
        if (!mounted) return;
        const places = res.places || [];
        setPlaces(places);
        setNextPageToken(res.next_page_token || null);
        
        if (places.length > 0) {
          onChangeRef.current(places.map(toSelectedAttraction));
        }
      } catch (err) {
        setError(err.message || "Unable to fetch popular places.");
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => (mounted = false);
  }, [destination]);

  async function loadMore() {
    if (!nextPageToken) return;
    setLoading(true);
    try {
      const res = await searchPlaces(destination, nextPageToken);
      setPlaces((p) => [...p, ...(res.places || [])]);
      setNextPageToken(res.next_page_token || null);
    } catch (err) {
      setError(err.message || "Unable to load more places.");
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

  const emptyMessage = "No popular places found for this destination.";

  return (
    <div className="popular-places">
      <div className="panel-heading">
        <h3>Popular Places to Visit</h3>
      </div>

      <div className="places-controls">
        <input
          placeholder="Search places"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="controls">
          <button type="button" onClick={selectAllVisible}>Select all</button>
          <button type="button" onClick={clearAllVisible}>Unselect visible</button>
          <button type="button" onClick={() => setSortByRating((s) => !s)}>{sortByRating ? "Unsort" : "Sort by rating"}</button>
        </div>
      </div>

      {loading && places.length === 0 ? (
        <div className="places-grid">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : error ? (
        <p className="muted">{error}</p>
      ) : filteredPlaces.length === 0 ? (
        <p className="muted">{emptyMessage}</p>
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
