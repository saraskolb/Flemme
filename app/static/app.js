const form = document.querySelector("#route-form");
const routeButton = document.querySelector("#route-button");
const messageEl = document.querySelector("#message");
const tabsEl = document.querySelector("#route-tabs");
const summaryEl = document.querySelector("#summary");
const directionsEl = document.querySelector("#directions");
const mapEl = document.querySelector("#map");
const healthPill = document.querySelector("#health-pill");
const locateButton = document.querySelector("#locate-button");
const gpsStatusEl = document.querySelector("#gps-status");
const feedbackNoteEl = document.querySelector("#feedback-note");
const feedbackButtons = document.querySelectorAll("[data-feedback-type]");

let routeResponse = null;
let selectedRouteIndex = 0;
let lastRouteQuery = null;
let currentPosition = null;
let gpsWatchId = null;
let leafletMap = null;
let leafletLayers = [];

function numberFromInput(id) {
  const value = Number.parseFloat(document.querySelector(`#${id}`).value);
  if (!Number.isFinite(value)) {
    throw new Error("Coordinates must be numbers.");
  }
  return value;
}

function meters(value) {
  if (value >= 1000) {
    return `${(value / 1609.344).toFixed(2)} mi`;
  }
  return `${Math.round(value)} m`;
}

function minutes(value) {
  return `${Math.round(value / 60)} min`;
}

function grade(value) {
  return `${Math.round(value * 100)}%`;
}

function setMessage(text, isError = false) {
  messageEl.textContent = text;
  messageEl.classList.toggle("error", isError);
}

function setGpsStatus(text, isError = false) {
  gpsStatusEl.textContent = text;
  gpsStatusEl.classList.toggle("error", isError);
}

async function geocodeInput(addressId, latId, lonId) {
  const address = document.querySelector(`#${addressId}`).value.trim();
  if (!address) {
    return {
      lat: numberFromInput(latId),
      lon: numberFromInput(lonId),
      displayName: "coordinates",
    };
  }

  const response = await fetch("/geocode", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address }),
  });

  if (!response.ok) {
    const errorPayload = await response.json().catch(() => ({}));
    throw new Error(errorPayload.detail || `Could not find ${address}`);
  }

  const result = await response.json();
  document.querySelector(`#${latId}`).value = result.lat;
  document.querySelector(`#${lonId}`).value = result.lon;
  return {
    lat: result.lat,
    lon: result.lon,
    displayName: result.display_name,
  };
}

async function loadHealth() {
  try {
    const response = await fetch("/health");
    const health = await response.json();
    healthPill.textContent = health.production_graph_loaded
      ? health.graph_version
      : "No graph";
  } catch {
    healthPill.textContent = "Offline";
  }
}

async function runRouteQuery() {
  routeButton.disabled = true;
  setMessage("Routing...");
  tabsEl.replaceChildren();
  summaryEl.replaceChildren();
  directionsEl.replaceChildren();
  drawEmptyMap("Routing");

  try {
    setMessage("Finding addresses...");
    const [origin, destination] = await Promise.all([
      geocodeInput("origin-address", "origin-lat", "origin-lon"),
      geocodeInput("destination-address", "destination-lat", "destination-lon"),
    ]);
    setMessage("Routing...");
    const payload = {
      origin: {
        lat: origin.lat,
        lon: origin.lon,
      },
      destination: {
        lat: destination.lat,
        lon: destination.lon,
      },
      preferences: {
        mode: document.querySelector("#mode").value,
      },
    };
    lastRouteQuery = {
      originAddress: document.querySelector("#origin-address").value.trim(),
      destinationAddress: document.querySelector("#destination-address").value.trim(),
      origin,
      destination,
      mode: payload.preferences.mode,
    };

    const response = await fetch("/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.detail || `Route failed with ${response.status}`);
    }

    routeResponse = await response.json();
    selectedRouteIndex = 0;
    setMessage(
      `${routeResponse.routes.length} route${routeResponse.routes.length === 1 ? "" : "s"}`
    );
    renderRoutes();
  } catch (error) {
    routeResponse = null;
    lastRouteQuery = null;
    setMessage(error.message, true);
    drawEmptyMap("No route");
  } finally {
    routeButton.disabled = false;
    updateFeedbackState();
  }
}

function renderRoutes() {
  if (!routeResponse || routeResponse.routes.length === 0) {
    drawEmptyMap("No route");
    return;
  }

  tabsEl.replaceChildren();
  routeResponse.routes.forEach((route, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = route.label;
    button.setAttribute("aria-selected", String(index === selectedRouteIndex));
    button.addEventListener("click", () => {
      selectedRouteIndex = index;
      renderRoutes();
    });
    tabsEl.append(button);
  });

  const route = routeResponse.routes[selectedRouteIndex];
  renderSummary(route);
  renderDirections(route);
  drawMap(routeResponse.routes, selectedRouteIndex);
  updateFeedbackState();
}

function renderSummary(route) {
  const metrics = route.metrics;
  summaryEl.replaceChildren();

  const heading = document.createElement("h2");
  heading.textContent = route.label;

  const line = document.createElement("div");
  line.className = "summary-line";
  line.append(
    metricSpan(minutes(metrics.time_s)),
    metricSpan(meters(metrics.distance_m)),
    metricSpan(`${Math.round(metrics.gain_m)} m gain`),
    metricSpan(`${grade(metrics.max_uphill_grade)} max uphill`)
  );

  const explanation = document.createElement("p");
  explanation.textContent = route.explanation;

  summaryEl.append(heading, line, explanation);
}

function metricSpan(text) {
  const span = document.createElement("span");
  span.textContent = text;
  return span;
}

function renderDirections(route) {
  directionsEl.replaceChildren();
  route.directions.forEach((step) => {
    const item = document.createElement("li");
    const instruction = document.createElement("strong");
    instruction.textContent = step.instruction;

    const meta = document.createElement("div");
    meta.className = "step-meta";
    meta.append(
      metricSpan(meters(step.distance_m)),
      metricSpan(minutes(step.time_s)),
      metricSpan(`${Math.round(step.gain_m)} m up`),
      metricSpan(`${Math.round(step.loss_m)} m down`)
    );

    item.append(instruction, meta);
    directionsEl.append(item);
  });
}

function drawEmptyMap(label) {
  const map = ensureLeafletMap();
  if (map) {
    clearLeafletLayers();
    map.setView([37.7749, -122.4194], 13);
    return;
  }

  mapEl.replaceChildren();
  const svg = fallbackSvg();
  drawGrid(svg);
  const text = svgNode("text", {
    x: 500,
    y: 360,
    "text-anchor": "middle",
    class: "map-label",
  });
  text.textContent = label;
  svg.append(text);
  mapEl.append(svg);
}

function drawMap(routes, selectedIndex) {
  const map = ensureLeafletMap();
  if (map) {
    drawLeafletMap(map, routes, selectedIndex);
    return;
  }

  mapEl.replaceChildren();
  const svg = fallbackSvg();
  drawGrid(svg);

  const allPoints = routes.flatMap((route) => route.geometry);
  if (currentPosition) {
    allPoints.push([currentPosition.lon, currentPosition.lat]);
  }
  if (allPoints.length < 2) {
    drawEmptyMap("No geometry");
    return;
  }

  const project = projector(allPoints);
  routes.forEach((route, index) => {
    if (index === selectedIndex) {
      return;
    }
    svg.append(svgNode("path", {
      d: pathFor(route.geometry, project),
      class: "route-line-muted",
    }));
  });

  const selected = routes[selectedIndex];
  svg.append(svgNode("path", {
    d: pathFor(selected.geometry, project),
    class: "route-line",
  }));

  const start = project(selected.geometry[0]);
  const end = project(selected.geometry[selected.geometry.length - 1]);
  svg.append(svgNode("circle", { cx: start.x, cy: start.y, r: 11, class: "marker start" }));
  svg.append(svgNode("circle", { cx: end.x, cy: end.y, r: 11, class: "marker end" }));

  if (currentPosition) {
    const current = project([currentPosition.lon, currentPosition.lat]);
    svg.append(svgNode("circle", {
      cx: current.x,
      cy: current.y,
      r: 9,
      class: "marker current",
    }));
  }

  mapEl.append(svg);
}

function ensureLeafletMap() {
  if (!window.L) {
    return null;
  }

  if (!leafletMap) {
    mapEl.replaceChildren();
    leafletMap = L.map(mapEl, {
      zoomControl: true,
      attributionControl: true,
    }).setView([37.7749, -122.4194], 13);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(leafletMap);
  }

  return leafletMap;
}

function clearLeafletLayers() {
  leafletLayers.forEach((layer) => layer.remove());
  leafletLayers = [];
}

function drawLeafletMap(map, routes, selectedIndex) {
  clearLeafletLayers();
  const bounds = L.latLngBounds([]);

  routes.forEach((route, index) => {
    const latLngs = route.geometry.map(([lon, lat]) => [lat, lon]);
    if (latLngs.length < 2) {
      return;
    }
    latLngs.forEach((latLng) => bounds.extend(latLng));
    if (index !== selectedIndex) {
      leafletLayers.push(L.polyline(latLngs, {
        color: "#8694a0",
        opacity: 0.45,
        weight: 6,
      }).addTo(map));
    }
  });

  const selected = routes[selectedIndex];
  const selectedLatLngs = selected.geometry.map(([lon, lat]) => [lat, lon]);
  leafletLayers.push(L.polyline(selectedLatLngs, {
    color: "#e85d24",
    opacity: 0.95,
    weight: 7,
  }).addTo(map));

  const start = selectedLatLngs[0];
  const end = selectedLatLngs[selectedLatLngs.length - 1];
  leafletLayers.push(L.circleMarker(start, {
    className: "leaflet-start-marker",
    color: "#ffffff",
    fillColor: "#f97316",
    fillOpacity: 1,
    radius: 8,
    weight: 3,
  }).addTo(map));
  leafletLayers.push(L.circleMarker(end, {
    className: "leaflet-end-marker",
    color: "#ffffff",
    fillColor: "#8d3f7a",
    fillOpacity: 1,
    radius: 8,
    weight: 3,
  }).addTo(map));

  if (currentPosition) {
    const currentLatLng = [currentPosition.lat, currentPosition.lon];
    bounds.extend(currentLatLng);
    leafletLayers.push(L.circleMarker(currentLatLng, {
      color: "#ffffff",
      fillColor: "#2f6fbd",
      fillOpacity: 1,
      radius: 7,
      weight: 3,
    }).addTo(map));
    if (currentPosition.accuracy_m) {
      leafletLayers.push(L.circle(currentLatLng, {
        color: "#2f6fbd",
        fillColor: "#2f6fbd",
        fillOpacity: 0.08,
        radius: currentPosition.accuracy_m,
        weight: 1,
      }).addTo(map));
    }
  }

  if (bounds.isValid()) {
    map.fitBounds(bounds.pad(0.18));
  }
}

function fallbackSvg() {
  return svgNode("svg", {
    viewBox: "0 0 1000 720",
    class: "fallback-map",
    role: "img",
    "aria-label": "Route map",
  });
}

function drawGrid(svg) {
  for (let x = 100; x < 1000; x += 100) {
    svg.append(svgNode("line", { x1: x, y1: 0, x2: x, y2: 720, class: "grid-line" }));
  }
  for (let y = 80; y < 720; y += 80) {
    svg.append(svgNode("line", { x1: 0, y1: y, x2: 1000, y2: y, class: "grid-line" }));
  }
}

function projector(points) {
  const lons = points.map((point) => point[0]);
  const lats = points.map((point) => point[1]);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const padding = 58;
  const width = 1000 - padding * 2;
  const height = 720 - padding * 2;
  const lonSpan = Math.max(0.00001, maxLon - minLon);
  const latSpan = Math.max(0.00001, maxLat - minLat);
  const scale = Math.min(width / lonSpan, height / latSpan);
  const usedWidth = lonSpan * scale;
  const usedHeight = latSpan * scale;
  const offsetX = padding + (width - usedWidth) / 2;
  const offsetY = padding + (height - usedHeight) / 2;

  return ([lon, lat]) => ({
    x: offsetX + (lon - minLon) * scale,
    y: offsetY + (maxLat - lat) * scale,
  });
}

function pathFor(points, project) {
  return points
    .map((point, index) => {
      const projected = project(point);
      return `${index === 0 ? "M" : "L"} ${projected.x.toFixed(1)} ${projected.y.toFixed(1)}`;
    })
    .join(" ");
}

function svgNode(tag, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  return node;
}

function updateFeedbackState() {
  feedbackButtons.forEach((button) => {
    button.disabled = !routeResponse;
  });
}

function toggleLocationWatch() {
  if (!navigator.geolocation) {
    setGpsStatus("GPS unavailable", true);
    return;
  }

  if (gpsWatchId !== null) {
    navigator.geolocation.clearWatch(gpsWatchId);
    gpsWatchId = null;
    locateButton.textContent = "Start GPS";
    setGpsStatus("GPS idle");
    return;
  }

  locateButton.textContent = "Stop GPS";
  setGpsStatus("Locating...");
  gpsWatchId = navigator.geolocation.watchPosition(
    (position) => {
      currentPosition = positionPayload(position);
      setGpsStatus(`GPS ±${Math.round(currentPosition.accuracy_m || 0)} m`);
      if (routeResponse) {
        drawMap(routeResponse.routes, selectedRouteIndex);
      }
    },
    (error) => {
      setGpsStatus(error.message || "GPS failed", true);
      locateButton.textContent = "Start GPS";
      gpsWatchId = null;
    },
    {
      enableHighAccuracy: true,
      maximumAge: 5000,
      timeout: 15000,
    }
  );
}

function positionPayload(position) {
  const { coords } = position;
  return {
    lat: coords.latitude,
    lon: coords.longitude,
    accuracy_m: numberOrNull(coords.accuracy),
    heading: numberOrNull(coords.heading),
    speed_mps: numberOrNull(coords.speed),
    observed_at: new Date(position.timestamp).toISOString(),
  };
}

function numberOrNull(value) {
  return Number.isFinite(value) ? value : null;
}

async function submitFeedback(feedbackType) {
  if (!routeResponse) {
    setMessage("Route first", true);
    return;
  }

  const route = routeResponse.routes[selectedRouteIndex];
  const payload = {
    feedback_type: feedbackType,
    graph_version: routeResponse.graph_version,
    route_label: route.label,
    route_edge_ids: route.edge_ids,
    direction_street_names: route.directions.map((step) => step.street_name),
    origin_address: lastRouteQuery?.originAddress || null,
    destination_address: lastRouteQuery?.destinationAddress || null,
    origin: lastRouteQuery
      ? { lat: lastRouteQuery.origin.lat, lon: lastRouteQuery.origin.lon }
      : null,
    destination: lastRouteQuery
      ? { lat: lastRouteQuery.destination.lat, lon: lastRouteQuery.destination.lon }
      : null,
    current_position: currentPosition,
    active_step_index: null,
    note: feedbackNoteEl.value.trim() || null,
  };

  feedbackButtons.forEach((button) => {
    button.disabled = true;
  });
  try {
    const response = await fetch("/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.detail || `Feedback failed with ${response.status}`);
    }
    const result = await response.json();
    feedbackNoteEl.value = "";
    setMessage(`Saved feedback ${result.feedback_id.slice(0, 8)}`);
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    updateFeedbackState();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  runRouteQuery();
});

locateButton.addEventListener("click", toggleLocationWatch);

feedbackButtons.forEach((button) => {
  button.addEventListener("click", () => {
    submitFeedback(button.dataset.feedbackType);
  });
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
  });
}

loadHealth();
updateFeedbackState();
drawEmptyMap("Flemme");
