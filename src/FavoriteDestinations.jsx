import { useEffect, useState } from "react";
import { Check, Loader2, Pencil, Plus, X } from "lucide-react";

import { fetchUserProfile, updateFavoriteDestinations } from "./api";

const MAX_FAVORITES = 10;

function normalizeDestination(value) {
  return value.trim().replace(/\s+/g, " ");
}

function uniqueDestinations(destinations) {
  const seen = new Set();
  return destinations.reduce((result, destination) => {
    const normalized = normalizeDestination(destination);
    const key = normalized.toLocaleLowerCase();
    if (normalized && !seen.has(key)) {
      seen.add(key);
      result.push(normalized);
    }
    return result;
  }, []);
}

export default function FavoriteDestinations({ firebaseUid }) {
  const [favorites, setFavorites] = useState([]);
  const [draft, setDraft] = useState([]);
  const [newDestination, setNewDestination] = useState("");
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchUserProfile(firebaseUid)
      .then((profile) => {
        if (!active) return;
        const destinations = uniqueDestinations(profile.favorite_destinations || []);
        setFavorites(destinations);
        setDraft(destinations);
      })
      .catch((loadError) => active && setError(loadError.message))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [firebaseUid]);

  function startEditing() {
    setDraft(favorites);
    setNewDestination("");
    setError("");
    setMessage("");
    setEditing(true);
  }

  function cancelEditing() {
    setDraft(favorites);
    setNewDestination("");
    setError("");
    setEditing(false);
  }

  function addDestination(event) {
    event?.preventDefault();
    const destination = normalizeDestination(newDestination);
    if (!destination) return;
    if (draft.some((item) => item.toLocaleLowerCase() === destination.toLocaleLowerCase())) {
      setError("That destination is already in your favorites.");
      return;
    }
    if (draft.length >= MAX_FAVORITES) {
      setError("You can save up to 10 favorite destinations.");
      return;
    }
    setDraft([...draft, destination]);
    setNewDestination("");
    setError("");
  }

  function updateDestination(index, value) {
    setDraft(draft.map((destination, currentIndex) => currentIndex === index ? value : destination));
  }

  function removeDestination(index) {
    setDraft(draft.filter((_, currentIndex) => currentIndex !== index));
    setError("");
  }

  async function saveFavorites() {
    const destinations = uniqueDestinations(draft);
    if (destinations.length > MAX_FAVORITES) {
      setError("You can save up to 10 favorite destinations.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await updateFavoriteDestinations(firebaseUid, destinations);
      const refreshedProfile = await fetchUserProfile(firebaseUid);
      const refreshedDestinations = uniqueDestinations(refreshedProfile.favorite_destinations || []);
      setFavorites(refreshedDestinations);
      setDraft(refreshedDestinations);
      setEditing(false);
      setMessage("Favorite destinations updated successfully.");
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="favorite-destinations">
      <div className="favorites-heading">
        <div>
          <h3>Favorite destinations</h3>
          <p>Keep your most-loved places close.</p>
        </div>
        {!editing && <button className="outline favorites-edit" type="button" onClick={startEditing} disabled={loading}><Pencil size={15}/> Edit</button>}
      </div>

      {loading ? <p className="favorites-loading"><Loader2 className="spin" size={16}/> Loading favorites…</p> : editing ? <>
        <div className="favorite-chip-list editable">
          {draft.map((destination, index) => <label className="favorite-chip edit-chip" key={`${destination}-${index}`}>
            <input aria-label={`Favorite destination ${index + 1}`} value={destination} onChange={(event) => updateDestination(index, event.target.value)} />
            <button type="button" aria-label={`Remove ${destination}`} onClick={() => removeDestination(index)}><X size={14}/></button>
          </label>)}
        </div>
        <form className="favorite-add" onSubmit={addDestination}>
          <input value={newDestination} maxLength="120" placeholder="Add a destination" onChange={(event) => setNewDestination(event.target.value)} />
          <button className="outline" type="submit" disabled={draft.length >= MAX_FAVORITES}><Plus size={16}/> Add</button>
        </form>
        <p className="favorites-limit">{draft.length}/{MAX_FAVORITES} destinations</p>
        <div className="favorite-actions">
          <button className="outline" type="button" onClick={cancelEditing} disabled={saving}>Cancel</button>
          <button className="button small" type="button" onClick={saveFavorites} disabled={saving}>{saving ? <><Loader2 className="spin" size={15}/> Saving…</> : <><Check size={15}/> Save</>}</button>
        </div>
      </> : <div className="favorite-chip-list">
        {favorites.length ? favorites.map((destination) => <span className="favorite-chip" key={destination}>{destination}</span>) : <p className="favorites-empty">No favorite destinations yet.</p>}
      </div>}
      {error && <p className="error favorites-message">{error}</p>}
      {message && <p className="favorites-toast" role="status">{message}</p>}
    </div>
  );
}
