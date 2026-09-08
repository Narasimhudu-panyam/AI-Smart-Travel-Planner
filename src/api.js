const configuredApiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_BASE_URL = import.meta.env.PROD ? "" : (configuredApiBase.startsWith("/") ? "http://localhost:8000" : configuredApiBase.replace(/\/+$/, ""));

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
  const fallbackResponse = await fetch(`${API_BASE_URL}/api/trips/generate?stream=false`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!fallbackResponse.ok) {
    const error = await fallbackResponse.json().catch(() => ({}));
    throw new Error(error.detail || "Unable to generate itinerary. Please try again.");
  }

  return await fallbackResponse.json();
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
