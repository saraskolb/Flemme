const presets = {
  duboce: {
    originAddress: "1227 Page Street",
    destinationAddress: "599 Duboce Avenue",
    origin: [37.7714654, -122.4412496],
    destination: [37.7690287, -122.4333261],
  },
  haight: {
    originAddress: "1227 Page Street",
    destinationAddress: "1840 Haight Street",
    origin: [37.7714654, -122.4412496],
    destination: [37.7695111, -122.4526159],
  },
  post: {
    originAddress: "1227 Page Street",
    destinationAddress: "Post Street and Webster Street",
    origin: [37.7714654, -122.4412496],
    destination: [37.785372647, -122.431366397],
  },
  ocean: {
    originAddress: "Ferry Building",
    destinationAddress: "Ocean Beach",
    origin: [37.7955, -122.3937],
    destination: [37.7697, -122.5108],
  },
};

const form = document.querySelector("#route-form");
const routeButton = document.querySelector("#route-button");
const messageEl = document.querySelector("#message");
const tabsEl = document.querySelector("#route-tabs");
const summaryEl = document.querySelector("#summary");
const directionsEl = document.querySelector("#directions");
const mapEl = document.querySelector("#map");
const healthPill = document.querySelector("#health-pill");

let routeResponse = null;
let selectedRouteIndex = 0;

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

function setPreset(name) {
  const preset = presets[name];
  document.querySelector("#origin-address").value = preset.originAddress;
  document.querySelector("#destination-address").value = preset.destinationAddress;
  document.querySelector("#origin-lat").value = preset.origin[0];
  document.querySelector("#origin-lon").value = preset.origin[1];
  document.querySelector("#destination-lat").value = preset.destination[0];
  document.querySelector("#destination-lon").value = preset.destination[1];
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
    setMessage(error.message, true);
    drawEmptyMap("No route");
  } finally {
    routeButton.disabled = false;
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
  mapEl.replaceChildren();
  drawGrid();
  const text = svgNode("text", {
    x: 500,
    y: 360,
    "text-anchor": "middle",
    class: "map-label",
  });
  text.textContent = label;
  mapEl.append(text);
}

function drawMap(routes, selectedIndex) {
  mapEl.replaceChildren();
  drawGrid();

  const allPoints = routes.flatMap((route) => route.geometry);
  if (allPoints.length < 2) {
    drawEmptyMap("No geometry");
    return;
  }

  const project = projector(allPoints);
  routes.forEach((route, index) => {
    if (index === selectedIndex) {
      return;
    }
    mapEl.append(svgNode("path", {
      d: pathFor(route.geometry, project),
      class: "route-line-muted",
    }));
  });

  const selected = routes[selectedIndex];
  mapEl.append(svgNode("path", {
    d: pathFor(selected.geometry, project),
    class: "route-line",
  }));

  const start = project(selected.geometry[0]);
  const end = project(selected.geometry[selected.geometry.length - 1]);
  mapEl.append(svgNode("circle", { cx: start.x, cy: start.y, r: 11, class: "marker start" }));
  mapEl.append(svgNode("circle", { cx: end.x, cy: end.y, r: 11, class: "marker end" }));
}

function drawGrid() {
  for (let x = 100; x < 1000; x += 100) {
    mapEl.append(svgNode("line", { x1: x, y1: 0, x2: x, y2: 720, class: "grid-line" }));
  }
  for (let y = 80; y < 720; y += 80) {
    mapEl.append(svgNode("line", { x1: 0, y1: y, x2: 1000, y2: y, class: "grid-line" }));
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

document.querySelectorAll("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => {
    setPreset(button.dataset.preset);
    runRouteQuery();
  });
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  runRouteQuery();
});

loadHealth();
drawEmptyMap("Flemme");
