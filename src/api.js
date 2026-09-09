const envApiUrl = import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE_URL || "";
export const API_BASE_URL = envApiUrl ? envApiUrl.trim().replace(/\/+$/, "") : "";

export async function generateTrip(payload) {
  // First attempt streaming generation
  try {
    const response = await fetch(`${API_BASE_URL}/api/trips/generate?stream=true`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("text/event-stream") || !response.body) {
        return await response.json();
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let plan = null;

      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const event of events) {
          const name = event.match(/^event:\s*(.+)$/m)?.[1]?.trim();
          const dataMatch = event.match(/^data:\s*([\s\S]+)$/m)?.[1]?.trim();
          if (!dataMatch) continue;

          try {
            const parsedData = JSON.parse(dataMatch);
            if (name === "delta") {
              window.dispatchEvent(new CustomEvent("travel-ai-delta", { detail: parsedData }));
            }
            if (name === "final") {
              plan = parsedData;
            }
          } catch {
            // Ignore malformed partial chunks
          }
        }

        if (done) break;
      }

      if (plan) return plan;
    }
  } catch (streamErr) {
    console.warn("Streaming generation encountered an issue, falling back to direct generation:", streamErr);
  }

  // Resilient non-streaming fallback
  try {
    const fallbackResponse = await fetch(`${API_BASE_URL}/api/trips/generate?stream=false`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!fallbackResponse.ok) {
      const error = await fallbackResponse.json().catch(() => ({}));
      throw new Error(error.detail || `Server returned error (${fallbackResponse.status}). Please try again.`);
    }

    return await fallbackResponse.json();
  } catch (err) {
    if (err.name === "TypeError" && (err.message.includes("fetch") || err.message.includes("Failed"))) {
      throw new Error("Unable to connect to the backend server. Please verify the backend is running on port 8000.");
    }
    throw err;
  }
}

export async function fetchTrips(userId) {
  const url = new URL(`${API_BASE_URL}/api/trips`, window.location.origin);
  if (userId) {
    url.searchParams.set("user_id", userId);
  }
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Unable to load trip history.");
  }
  return response.json();
}

export async function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/api/uploads`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Unable to upload document.");
  }

  return response.json();
}

export async function fetchUserProfile(firebaseUid) {
  const url = new URL(`${API_BASE_URL}/api/users/profile`, window.location.origin);
  url.searchParams.set("firebase_uid", firebaseUid);
  const response = await fetch(url);
  if (!response.ok) throw new Error("Unable to load your profile.");
  return response.json();
}

export async function updateFavoriteDestinations(firebaseUid, favoriteDestinations) {
  const url = new URL(`${API_BASE_URL}/api/users/profile`, window.location.origin);
  url.searchParams.set("firebase_uid", firebaseUid);
  const response = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ favorite_destinations: favoriteDestinations }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Unable to update favorite destinations.");
  }
  return response.json();
}

export async function fetchTripById(id) {
  if (!id || id === "latest") return null;
  try {
    const url = new URL(`${API_BASE_URL}/api/itineraries`, window.location.origin);
    url.searchParams.set("trip_id", id);
    const response = await fetch(url);
    if (response.ok) {
      const list = await response.json();
      if (Array.isArray(list) && list.length && list[0].ai_response) {
        return list[0].ai_response;
      }
    }
  } catch {
    // Graceful fallback to cached or list
  }
  return null;
}
