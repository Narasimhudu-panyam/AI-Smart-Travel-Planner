const configuredApiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const API_BASE_URL = configuredApiBase.startsWith("/") ? "http://localhost:8000" : configuredApiBase.replace(/\/+$/, "");

export async function generateTrip(payload) {
  const response = await fetch(`${API_BASE_URL}/api/trips/generate?stream=true`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Unable to generate trip.");
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("text/event-stream") || !response.body) {
    return response.json();
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
      const name = event.match(/^event: (.+)$/m)?.[1];
      const data = event.match(/^data: (.+)$/m)?.[1];
      if (!data) continue;
      if (name === "delta") window.dispatchEvent(new CustomEvent("travel-ai-delta", { detail: JSON.parse(data) }));
      if (name === "final") plan = JSON.parse(data);
    }
    if (done) break;
  }
  if (!plan) throw new Error("The itinerary stream ended before a final plan was returned.");
  return plan;
}

export async function fetchTrips(userId) {
  const url = new URL(`${API_BASE_URL}/api/trips`);
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
