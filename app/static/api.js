async function requestJSON(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

export function getHealth() {
  return requestJSON("/health");
}

export function getSuggestions(query) {
  const params = new URLSearchParams({ q: query });
  return requestJSON(`/geocode/suggest?${params.toString()}`);
}

export function geocodeAddress(address) {
  return requestJSON("/geocode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });
}

export function findRoutes(origin, destination, preferences) {
  return requestJSON("/route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ origin, destination, preferences }),
  });
}

export function saveFeedback(payload) {
  return requestJSON("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
