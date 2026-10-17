import {
  findRoutes,
  geocodeAddress,
  getHealth,
  getSuggestions,
  saveFeedback,
} from "/static/api.js";
import { FlemmeMap } from "/static/map.js";

const app = document.querySelector("#app");
const mapElement = document.querySelector("#map");
const planView = document.querySelector("#plan-view");
const compareView = document.querySelector("#compare-view");
const walkView = document.querySelector("#walk-view");
const brandBar = document.querySelector("#brand-bar");
const routeForm = document.querySelector("#route-form");
const routeButton = document.querySelector("#route-button");
const originInput = document.querySelector("#origin-address");
const destinationInput = document.querySelector("#destination-address");
const useLocationButton = document.querySelector("#use-location-button");
const mapLocateButton = document.querySelector("#map-locate-button");
const routeTabs = document.querySelector("#route-tabs");
const resultsSheet = document.querySelector("#query-panel");
const sheetHandle = document.querySelector("#sheet-handle");
const routeDetails = document.querySelector("#route-details");
const detailsButton = document.querySelector("#details-button");
const startWalkButton = document.querySelector("#start-walk-button");
const routeTitle = document.querySelector("#route-title");
const routeMeta = document.querySelector("#route-meta");
const routeBadge = document.querySelector("#route-badge");
const routeReason = document.querySelector("#route-reason");
const routeWarnings = document.querySelector("#route-warnings");
const slopeProfile = document.querySelector("#slope-profile");
const slopeCaption = document.querySelector("#slope-caption");
const directionsList = document.querySelector("#directions");
const directionCount = document.querySelector("#direction-count");
const planMessage = document.querySelector("#plan-message");
const compareMessage = document.querySelector("#compare-message");
const queryDestination = document.querySelector("#query-destination");
const queryPreference = document.querySelector("#query-preference");
const nextStepElement = document.querySelector("#next-step");
const maneuverDistance = document.querySelector("#maneuver-distance");
const maneuverIcon = document.querySelector("#maneuver-icon");
const walkTime = document.querySelector("#walk-time");
const walkMeta = document.querySelector("#walk-meta");
const gpsStatus = document.querySelector("#gps-status");
const diagnosticGps = document.querySelector("#diagnostic-gps");
const locateButton = document.querySelector("#locate-button");
const rerouteButton = document.querySelector("#reroute-button");
const feedbackDialog = document.querySelector("#feedback-dialog");
const feedbackMessage = document.querySelector("#feedback-message");
const feedbackNote = document.querySelector("#feedback-note");
const feedbackButtons = [...document.querySelectorAll("[data-feedback-type]")];
const diagnosticsDialog = document.querySelector("#diagnostics-dialog");
const healthStatus = document.querySelector("#health-status");
const healthPill = document.querySelector("#health-pill");
const statusDot = document.querySelector(".status-dot");
const toast = document.querySelector("#toast");

const map = new FlemmeMap(mapElement);
const state = {
  view: "plan",
  routeResponse: null,
  selectedRouteIndex: 0,
  origin: null,
  destination: null,
  originDisplay: "",
  destinationDisplay: "",
  currentPosition: null,
  gpsWatchId: null,
  activeStepIndex: 0,
  offRouteObservations: 0,
  lastRerouteAt: 0,
  routing: false,
  rerouting: false,
  muted: false,
};

const MANEUVER_ICONS = {
  depart: "↑",
  continue: "↑",
  turn_left: "↰",
  turn_right: "↱",
  u_turn: "↶",
};

function selectedRoute() {
  return state.routeResponse?.routes?.[state.selectedRouteIndex] || null;
}

function selectedMode() {
  return routeForm.elements.mode.value;
}

function modeLabel(mode = selectedMode()) {
  return {
    balanced: "Gentle hills",
    fastest: "Fastest",
    accessibility: "Avoid stairs",
    avoid_hills: "Avoid hills",
  }[mode] || "Custom walk";
}

function modePreferences(mode = selectedMode()) {
  if (mode === "accessibility") {
    return { mode, forbid_stairs: true };
  }
  return { mode };
}

function setView(view) {
  state.view = view;
  app.dataset.view = view;
  planView.hidden = view !== "plan";
  compareView.hidden = view !== "compare";
  walkView.hidden = view !== "walk";
  brandBar.hidden = view !== "plan";
  mapLocateButton.hidden = view === "walk";
  if (view !== "compare") {
    document.documentElement.style.setProperty("--sheet-offset", "0px");
  }
  map.invalidate();
}

function setInlineMessage(element, message = "", isError = false) {
  element.textContent = message;
  element.classList.toggle("is-error", isError);
}

let toastTimer = null;
function showToast(message) {
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

function meters(value) {
  if (value >= 1609.344) {
    return `${(value / 1609.344).toFixed(1)} mi`;
  }
  if (value >= 160.934) {
    return `${(value / 1609.344).toFixed(2)} mi`;
  }
  return `${Math.max(0, Math.round(value))} m`;
}

function minutes(value) {
  return `${Math.max(1, Math.round(value / 60))} min`;
}

function feet(value) {
  return `${Math.round(value * 3.28084)} ft`;
}

function grade(value) {
  return `${Math.round(Math.max(0, value) * 100)}%`;
}

function shortPlaceName(value) {
  if (!value) {
    return "Destination";
  }
  return value.split(",").slice(0, 2).join(",");
}

function installSuggestions(input, container, locationKey) {
  let timer = null;
  let requestSequence = 0;

  input.addEventListener("input", () => {
    state[locationKey] = null;
    requestSequence += 1;
    const sequence = requestSequence;
    window.clearTimeout(timer);
    const query = input.value.trim();
    if (query.length < 2 || query === "Current location") {
      container.replaceChildren();
      container.classList.remove("has-results");
      return;
    }
    timer = window.setTimeout(async () => {
      try {
        const response = await getSuggestions(query);
        if (sequence !== requestSequence) {
          return;
        }
        renderSuggestions(input, container, locationKey, response.suggestions || []);
      } catch {
        container.replaceChildren();
        container.classList.remove("has-results");
      }
    }, 220);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      container.replaceChildren();
      container.classList.remove("has-results");
    }
  });
}

function renderSuggestions(input, container, locationKey, suggestions) {
  container.replaceChildren();
  suggestions.slice(0, 5).forEach((suggestion) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "suggestion-button";
    button.setAttribute("role", "option");
    const title = document.createElement("strong");
    title.textContent = suggestion.display_name.split(",")[0];
    const detail = document.createElement("span");
    detail.textContent = suggestion.display_name.split(",").slice(1, 3).join(",").trim();
    button.append(title, detail);
    button.addEventListener("click", () => {
      state[locationKey] = {
        lat: suggestion.lat,
        lon: suggestion.lon,
        display_name: suggestion.display_name,
        input_value: suggestion.display_name,
      };
      input.value = suggestion.display_name;
      container.replaceChildren();
      container.classList.remove("has-results");
      if (locationKey === "destination") {
        routeButton.focus();
      }
    });
    container.append(button);
  });
  container.classList.toggle("has-results", container.childElementCount > 0);
}

async function resolveLocation(input, locationKey) {
  const value = input.value.trim();
  const existing = state[locationKey];
  if (existing && (existing.input_value === value || value === "Current location")) {
    return existing;
  }
  if (!value) {
    throw new Error(locationKey === "origin" ? "Choose a starting point." : "Choose a destination.");
  }
  const result = await geocodeAddress(value);
  const location = { ...result, input_value: value };
  state[locationKey] = location;
  input.value = result.display_name;
  return location;
}

async function runRouteQuery({ originOverride = null, stayWalking = false } = {}) {
  if (state.routing) {
    return;
  }
  const rerouting = Boolean(originOverride && stayWalking);
  state.routing = true;
  state.rerouting = rerouting;
  app.classList.add("is-routing");
  routeButton.disabled = true;
  startWalkButton.disabled = true;
  setInlineMessage(planMessage, rerouting ? "Re-routing…" : "Finding the best walks…");
  setInlineMessage(compareMessage, rerouting ? "Re-routing from your location…" : "");

  try {
    const origin = originOverride || await resolveLocation(originInput, "origin");
    const destination = state.destination || await resolveLocation(destinationInput, "destination");
    const response = await findRoutes(
      { lat: origin.lat, lon: origin.lon },
      { lat: destination.lat, lon: destination.lon },
      modePreferences()
    );
    state.routeResponse = response;
    state.origin = origin;
    state.destination = destination;
    state.originDisplay = originOverride ? "Current location" : originInput.value.trim();
    state.destinationDisplay = destinationInput.value.trim();
    state.selectedRouteIndex = Math.max(
      0,
      response.routes.findIndex((route) => route.route_id === response.recommended_route_id)
    );
    state.activeStepIndex = 0;
    state.offRouteObservations = 0;
    renderRouteOptions();
    map.setRoutes(response.routes, state.selectedRouteIndex, { fit: !stayWalking });
    if (stayWalking) {
      setView("walk");
      updateWalkProgress();
      showToast("Route updated");
    } else {
      setView("compare");
      expandSheet();
    }
    await loadHealth();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not find a route.";
    if (stayWalking) {
      setInlineMessage(gpsStatus, message, true);
      rerouteButton.hidden = false;
    } else {
      setInlineMessage(planMessage, message, true);
      setView("plan");
    }
  } finally {
    app.classList.remove("is-routing");
    routeButton.disabled = false;
    startWalkButton.disabled = false;
    state.routing = false;
    state.rerouting = false;
  }
}

function renderRouteOptions() {
  const routes = state.routeResponse?.routes || [];
  routeTabs.replaceChildren();
  routes.forEach((route, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "route-tab";
    button.setAttribute("role", "tab");
    button.setAttribute("aria-selected", String(index === state.selectedRouteIndex));
    const time = document.createElement("span");
    time.className = "route-tab-time";
    time.textContent = minutes(route.metrics.time_s);
    const label = document.createElement("span");
    label.className = "route-tab-label";
    label.textContent = `${route.badge} · ${meters(route.metrics.distance_m)}`;
    button.append(time, label);
    button.addEventListener("click", () => selectRoute(index));
    routeTabs.append(button);
  });
  queryDestination.textContent = `${shortPlaceName(state.originDisplay)} → ${shortPlaceName(state.destinationDisplay)}`;
  queryPreference.textContent = modeLabel();
  renderSelectedRoute();
}

function selectRoute(index) {
  if (!state.routeResponse?.routes?.[index]) {
    return;
  }
  state.selectedRouteIndex = index;
  [...routeTabs.children].forEach((button, buttonIndex) => {
    button.setAttribute("aria-selected", String(buttonIndex === index));
  });
  renderSelectedRoute();
  map.selectRoute(index);
}

function renderSelectedRoute() {
  const route = selectedRoute();
  if (!route) {
    return;
  }
  routeTitle.textContent = route.title;
  routeBadge.textContent = route.badge;
  routeMeta.textContent = `${minutes(route.metrics.time_s)} · ${meters(route.metrics.distance_m)} · ${feet(route.metrics.gain_m)} climb`;
  renderReason(route);
  renderWarnings(route.warnings || []);
  renderSlope(route);
  renderDirections(route);
}

function renderReason(route) {
  routeReason.replaceChildren();
  const heading = document.createElement("strong");
  const body = document.createElement("span");
  const comparison = route.comparison;
  if (comparison.avoided_10pct_uphill_m > 5) {
    const timeText = comparison.extra_time_s > 20
      ? `${minutes(comparison.extra_time_s)} slower, much gentler`
      : "A gentler walk with almost no time penalty";
    heading.textContent = timeText;
    body.textContent = `Avoids ${meters(comparison.avoided_10pct_uphill_m)} of 10%+ climbing. Steepest sustained grade is ${grade(route.metrics.max_uphill_grade)}.`;
  } else if (route.label === "fastest") {
    heading.textContent = "The quickest practical walk";
    body.textContent = `About ${minutes(route.metrics.time_s)} with a steepest sustained grade of ${grade(route.metrics.max_uphill_grade)}.`;
  } else {
    heading.textContent = route.recommendation.title;
    body.textContent = route.recommendation.summary;
  }
  routeReason.append(heading, body);
}

function renderWarnings(warnings) {
  routeWarnings.replaceChildren();
  warnings.forEach((warning) => {
    const paragraph = document.createElement("p");
    paragraph.className = "route-warning";
    paragraph.textContent = warning;
    routeWarnings.append(paragraph);
  });
}

function svgElement(tag, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function renderSlope(route) {
  slopeProfile.replaceChildren();
  const points = route.elevation_profile || [];
  slopeCaption.textContent = `${feet(route.metrics.gain_m)} total climb`;
  if (points.length < 2) {
    const label = svgElement("text", { x: 160, y: 48, "text-anchor": "middle", class: "slope-label" });
    label.textContent = "Detailed elevation is unavailable";
    slopeProfile.append(label);
    return;
  }
  const width = 320;
  const height = 92;
  const padX = 7;
  const padTop = 8;
  const padBottom = 18;
  const maxDistance = Math.max(...points.map((point) => point.distance_m), 1);
  const elevations = points.map((point) => point.elevation_m);
  const minElevation = Math.min(...elevations);
  const maxElevation = Math.max(...elevations);
  const elevationSpan = Math.max(2, maxElevation - minElevation);
  const project = (point) => ({
    x: padX + (point.distance_m / maxDistance) * (width - padX * 2),
    y: padTop + ((maxElevation - point.elevation_m) / elevationSpan) * (height - padTop - padBottom),
  });
  const projected = points.map(project);
  const linePath = projected.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${projected.at(-1).x.toFixed(1)},${height - padBottom} L${projected[0].x.toFixed(1)},${height - padBottom} Z`;
  slopeProfile.append(
    svgElement("line", { x1: padX, y1: height - padBottom, x2: width - padX, y2: height - padBottom, class: "slope-baseline" }),
    svgElement("path", { d: areaPath, class: "slope-area" }),
    svgElement("path", { d: linePath, class: "slope-line" })
  );
  const startLabel = svgElement("text", { x: padX, y: height - 4, class: "slope-label" });
  startLabel.textContent = "Start";
  const endLabel = svgElement("text", { x: width - padX, y: height - 4, "text-anchor": "end", class: "slope-label" });
  endLabel.textContent = meters(maxDistance);
  slopeProfile.append(startLabel, endLabel);
}

function renderDirections(route) {
  directionsList.replaceChildren();
  directionCount.textContent = `${route.directions.length} steps`;
  route.directions.forEach((step) => {
    const item = document.createElement("li");
    item.className = "direction-step";
    const icon = document.createElement("span");
    icon.className = "direction-icon";
    icon.textContent = MANEUVER_ICONS[step.maneuver] || "↑";
    const content = document.createElement("div");
    const instruction = document.createElement("strong");
    instruction.textContent = step.instruction;
    const metadata = document.createElement("span");
    metadata.textContent = `${meters(step.distance_m)} · ${minutes(step.time_s)}`;
    content.append(instruction, metadata);
    item.append(icon, content);
    directionsList.append(item);
  });
}

function toggleDetails() {
  const willOpen = routeDetails.hidden;
  routeDetails.hidden = !willOpen;
  detailsButton.textContent = willOpen ? "Less" : "Details";
  detailsButton.setAttribute("aria-expanded", String(willOpen));
  if (willOpen) {
    expandSheet();
    window.setTimeout(() => routeDetails.scrollIntoView({ behavior: "smooth", block: "nearest" }), 80);
  }
}

function startWalking() {
  const route = selectedRoute();
  if (!route) {
    return;
  }
  state.activeStepIndex = 0;
  state.offRouteObservations = 0;
  rerouteButton.hidden = true;
  setView("walk");
  map.setRoutes(state.routeResponse.routes, state.selectedRouteIndex, { fit: false });
  updateWalkProgress();
  startGpsWatch();
}

function endWalking() {
  stopGpsWatch();
  setView("compare");
  map.setRoutes(state.routeResponse.routes, state.selectedRouteIndex);
}

function positionPayload(position) {
  const { coords } = position;
  return {
    lat: coords.latitude,
    lon: coords.longitude,
    accuracy_m: Number.isFinite(coords.accuracy) ? coords.accuracy : null,
    heading: Number.isFinite(coords.heading) ? coords.heading : null,
    speed_mps: Number.isFinite(coords.speed) ? coords.speed : null,
    observed_at: new Date(position.timestamp).toISOString(),
  };
}

function updatePosition(position, { follow = state.view === "walk" } = {}) {
  state.currentPosition = position;
  state.origin = {
    lat: position.lat,
    lon: position.lon,
    display_name: "Current location",
    input_value: "Current location",
  };
  map.setCurrentPosition(position, { follow });
  const accuracyText = position.accuracy_m ? `GPS ±${Math.round(position.accuracy_m)} m` : "GPS active";
  setInlineMessage(gpsStatus, accuracyText);
  diagnosticGps.textContent = accuracyText;
  if (state.view === "walk") {
    updateWalkProgress();
  }
}

function requestCurrentLocation({ setAsOrigin = false } = {}) {
  if (!navigator.geolocation) {
    showToast("GPS is unavailable on this device");
    return Promise.reject(new Error("GPS is unavailable."));
  }
  useLocationButton.disabled = true;
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const payload = positionPayload(position);
        updatePosition(payload, { follow: true });
        if (setAsOrigin) {
          originInput.value = "Current location";
          state.origin = { ...payload, display_name: "Current location", input_value: "Current location" };
          setInlineMessage(planMessage, "Start set to your current location.");
        }
        useLocationButton.disabled = false;
        resolve(payload);
      },
      (error) => {
        useLocationButton.disabled = false;
        showToast(error.message || "Could not get your location");
        reject(error);
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
  });
}

function startGpsWatch() {
  if (!navigator.geolocation) {
    setInlineMessage(gpsStatus, "GPS is unavailable.", true);
    return;
  }
  if (state.gpsWatchId !== null) {
    return;
  }
  setInlineMessage(gpsStatus, "Locating…");
  locateButton.textContent = "Stop GPS";
  state.gpsWatchId = navigator.geolocation.watchPosition(
    (position) => updatePosition(positionPayload(position)),
    (error) => {
      setInlineMessage(gpsStatus, error.message || "GPS failed.", true);
      stopGpsWatch();
    },
    { enableHighAccuracy: true, maximumAge: 3000, timeout: 15000 }
  );
}

function stopGpsWatch() {
  if (state.gpsWatchId !== null && navigator.geolocation) {
    navigator.geolocation.clearWatch(state.gpsWatchId);
  }
  state.gpsWatchId = null;
  locateButton.textContent = "Start GPS";
  setInlineMessage(gpsStatus, "GPS idle");
  diagnosticGps.textContent = "Idle";
}

function toggleGpsWatch() {
  if (state.gpsWatchId === null) {
    startGpsWatch();
  } else {
    stopGpsWatch();
  }
}

function distanceMeters(left, right) {
  const radiusM = 6371008.8;
  const lat1 = left.lat * Math.PI / 180;
  const lat2 = right.lat * Math.PI / 180;
  const deltaLat = lat2 - lat1;
  const deltaLon = (right.lon - left.lon) * Math.PI / 180;
  const a = Math.sin(deltaLat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;
  return radiusM * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function projectToRoute(position, geometry) {
  if (!position || geometry.length < 2) {
    return null;
  }
  const referenceLat = position.lat * Math.PI / 180;
  const lonScale = 111320 * Math.cos(referenceLat);
  const latScale = 110540;
  const point = { x: position.lon * lonScale, y: position.lat * latScale };
  let best = { distanceToRouteM: Infinity, distanceAlongGeometryM: 0 };
  let cumulativeM = 0;

  for (let index = 1; index < geometry.length; index += 1) {
    const [lonA, latA] = geometry[index - 1];
    const [lonB, latB] = geometry[index];
    const a = { x: lonA * lonScale, y: latA * latScale };
    const b = { x: lonB * lonScale, y: latB * latScale };
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const squaredLength = dx * dx + dy * dy;
    const t = squaredLength > 0
      ? Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / squaredLength))
      : 0;
    const nearest = { x: a.x + t * dx, y: a.y + t * dy };
    const distanceToRouteM = Math.hypot(point.x - nearest.x, point.y - nearest.y);
    const segmentM = distanceMeters({ lat: latA, lon: lonA }, { lat: latB, lon: lonB });
    if (distanceToRouteM < best.distanceToRouteM) {
      best = {
        distanceToRouteM,
        distanceAlongGeometryM: cumulativeM + segmentM * t,
      };
    }
    cumulativeM += segmentM;
  }
  return { ...best, geometryLengthM: cumulativeM };
}

function updateWalkProgress() {
  const route = selectedRoute();
  if (!route) {
    return;
  }
  let progressM = 0;
  let offRouteM = 0;
  if (state.currentPosition) {
    const projection = projectToRoute(state.currentPosition, route.geometry);
    if (projection) {
      const scale = projection.geometryLengthM > 0
        ? route.metrics.distance_m / projection.geometryLengthM
        : 1;
      progressM = projection.distanceAlongGeometryM * scale;
      offRouteM = projection.distanceToRouteM;
    }
  }
  progressM = Math.max(0, Math.min(route.metrics.distance_m, progressM));
  const steps = route.directions || [];
  const foundStepIndex = steps.findIndex((step) => step.end_distance_m >= progressM);
  state.activeStepIndex = foundStepIndex === -1
    ? Math.max(0, steps.length - 1)
    : foundStepIndex;
  const step = steps[state.activeStepIndex];
  if (step) {
    const remainingStepM = Math.max(0, step.end_distance_m - progressM);
    maneuverDistance.textContent = remainingStepM < 20 ? "Now" : `In ${meters(remainingStepM)}`;
    nextStepElement.textContent = step.instruction;
    maneuverIcon.textContent = MANEUVER_ICONS[step.maneuver] || "↑";
  }

  const remainingM = Math.max(0, route.metrics.distance_m - progressM);
  const remainingRatio = route.metrics.distance_m > 0 ? remainingM / route.metrics.distance_m : 0;
  const remainingTimeS = route.metrics.time_s * remainingRatio;
  const arrival = new Date(Date.now() + remainingTimeS * 1000);
  walkTime.textContent = remainingM < 12 ? "Arriving" : minutes(remainingTimeS);
  walkMeta.textContent = `${arrival.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} arrival · ${meters(remainingM)} left`;

  const accuracy = state.currentPosition?.accuracy_m ?? Infinity;
  const threshold = Math.max(40, Math.min(70, accuracy * 1.6));
  if (state.currentPosition && accuracy <= 80 && offRouteM > threshold) {
    state.offRouteObservations += 1;
  } else {
    state.offRouteObservations = 0;
  }
  rerouteButton.hidden = state.offRouteObservations < 2;
  if (
    state.offRouteObservations >= 3
    && Date.now() - state.lastRerouteAt > 45000
    && !state.routing
  ) {
    rerouteFromCurrent();
  }
}

async function rerouteFromCurrent() {
  if (!state.currentPosition || !state.destination || state.routing) {
    return;
  }
  state.lastRerouteAt = Date.now();
  rerouteButton.hidden = true;
  await runRouteQuery({ originOverride: state.currentPosition, stayWalking: true });
}

function openFeedback() {
  feedbackMessage.textContent = "";
  if (typeof feedbackDialog.showModal === "function") {
    feedbackDialog.showModal();
  } else {
    feedbackDialog.setAttribute("open", "");
  }
}

function uniqueKey() {
  return window.crypto?.randomUUID?.() || `feedback-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function submitFeedback(type) {
  const route = selectedRoute();
  if (!route || !state.origin || !state.destination) {
    return;
  }
  feedbackButtons.forEach((button) => { button.disabled = true; });
  setInlineMessage(feedbackMessage, "Saving…");
  const step = route.directions[state.activeStepIndex] || null;
  try {
    const result = await saveFeedback({
      feedback_type: type,
      graph_version: state.routeResponse.graph_version,
      route_id: route.route_id,
      step_id: step?.step_id || null,
      idempotency_key: uniqueKey(),
      route_label: route.label,
      route_edge_ids: route.edge_ids,
      direction_street_names: route.directions.map((direction) => direction.street_name),
      origin_address: state.originDisplay || null,
      destination_address: state.destinationDisplay || null,
      origin: { lat: state.origin.lat, lon: state.origin.lon },
      destination: { lat: state.destination.lat, lon: state.destination.lon },
      current_position: state.currentPosition,
      active_step_index: state.activeStepIndex,
      note: feedbackNote.value.trim() || null,
    });
    feedbackNote.value = "";
    feedbackDialog.close?.();
    showToast(result.duplicate ? "Feedback already saved" : "Thanks — feedback saved");
  } catch (error) {
    setInlineMessage(feedbackMessage, error instanceof Error ? error.message : "Could not save feedback.", true);
  } finally {
    feedbackButtons.forEach((button) => { button.disabled = false; });
  }
}

async function loadHealth() {
  try {
    const health = await getHealth();
    healthStatus.textContent = "Connected";
    healthPill.textContent = `${health.graph_version} · ${health.graph_status}`;
    statusDot.classList.toggle("is-ready", health.graph_status === "ready" || health.graph_status === "available");
    statusDot.classList.remove("is-error");
  } catch {
    healthStatus.textContent = "Offline";
    healthPill.textContent = "Unavailable";
    statusDot.classList.remove("is-ready");
    statusDot.classList.add("is-error");
  }
}

let sheetDrag = null;
function collapsedSheetOffset() {
  return Math.max(0, resultsSheet.getBoundingClientRect().height - 164);
}

function setSheetOffset(value) {
  const offset = Math.max(0, Math.min(value, collapsedSheetOffset()));
  document.documentElement.style.setProperty("--sheet-offset", `${Math.round(offset)}px`);
}

function collapseSheet() {
  if (!window.matchMedia("(max-width: 899px)").matches) {
    return;
  }
  resultsSheet.classList.add("is-collapsed");
  sheetHandle.setAttribute("aria-expanded", "false");
  sheetHandle.setAttribute("aria-label", "Expand route details");
  setSheetOffset(collapsedSheetOffset());
  map.invalidate();
}

function expandSheet() {
  resultsSheet.classList.remove("is-collapsed");
  sheetHandle.setAttribute("aria-expanded", "true");
  sheetHandle.setAttribute("aria-label", "Collapse route details");
  setSheetOffset(0);
  map.invalidate();
}

function toggleSheet() {
  if (resultsSheet.classList.contains("is-collapsed")) {
    expandSheet();
  } else {
    collapseSheet();
  }
}

function startSheetDrag(event) {
  if (!window.matchMedia("(max-width: 899px)").matches) {
    return;
  }
  event.preventDefault();
  const currentOffset = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--sheet-offset")) || 0;
  sheetDrag = { pointerId: event.pointerId, startY: event.clientY, lastY: event.clientY, startOffset: currentOffset, moved: false };
  resultsSheet.classList.add("is-dragging");
  sheetHandle.setPointerCapture?.(event.pointerId);
  window.addEventListener("pointermove", dragSheet);
  window.addEventListener("pointerup", finishSheetDrag);
  window.addEventListener("pointercancel", finishSheetDrag);
}

function dragSheet(event) {
  if (!sheetDrag || event.pointerId !== sheetDrag.pointerId) {
    return;
  }
  const delta = event.clientY - sheetDrag.startY;
  sheetDrag.lastY = event.clientY;
  sheetDrag.moved ||= Math.abs(delta) > 5;
  setSheetOffset(sheetDrag.startOffset + delta);
}

function finishSheetDrag(event) {
  if (!sheetDrag || event.pointerId !== sheetDrag.pointerId) {
    return;
  }
  const delta = sheetDrag.lastY - sheetDrag.startY;
  const moved = sheetDrag.moved;
  sheetDrag = null;
  resultsSheet.classList.remove("is-dragging");
  window.removeEventListener("pointermove", dragSheet);
  window.removeEventListener("pointerup", finishSheetDrag);
  window.removeEventListener("pointercancel", finishSheetDrag);
  if (!moved) {
    toggleSheet();
  } else if (delta > 35) {
    collapseSheet();
  } else {
    expandSheet();
  }
}

function updateViewport() {
  const visibleHeight = window.visualViewport?.height || window.innerHeight;
  document.documentElement.style.setProperty("--app-height", `${window.innerHeight}px`);
  document.documentElement.style.setProperty("--visible-height", `${visibleHeight}px`);
  const editing = window.matchMedia("(max-width: 520px)").matches
    && document.activeElement?.matches?.("input, textarea");
  document.body.classList.toggle("is-editing", Boolean(editing));
  if (state.view === "compare" && resultsSheet.classList.contains("is-collapsed")) {
    setSheetOffset(collapsedSheetOffset());
  }
  map.invalidate();
}

function loadRouteFromQuery() {
  const params = new URLSearchParams(window.location.search);
  const originLat = Number.parseFloat(params.get("originLat"));
  const originLon = Number.parseFloat(params.get("originLon"));
  const destinationLat = Number.parseFloat(params.get("destinationLat"));
  const destinationLon = Number.parseFloat(params.get("destinationLon"));
  if (![originLat, originLon, destinationLat, destinationLon].every(Number.isFinite)) {
    return false;
  }
  const originName = params.get("origin") || "Shared start";
  const destinationName = params.get("destination") || "Shared destination";
  const requestedMode = params.get("mode") || "balanced";
  const modeInput = routeForm.querySelector(`[name="mode"][value="${CSS.escape(requestedMode)}"]`);
  if (modeInput) {
    modeInput.checked = true;
  }
  originInput.value = originName;
  destinationInput.value = destinationName;
  state.origin = { lat: originLat, lon: originLon, display_name: originName, input_value: originName };
  state.destination = {
    lat: destinationLat,
    lon: destinationLon,
    display_name: destinationName,
    input_value: destinationName,
  };
  return params.get("route") === "1";
}

routeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runRouteQuery();
});

useLocationButton.addEventListener("click", () => {
  requestCurrentLocation({ setAsOrigin: true }).catch(() => {});
});

mapLocateButton.addEventListener("click", () => {
  requestCurrentLocation({ setAsOrigin: false }).catch(() => {});
});

document.querySelector("#edit-route-button").addEventListener("click", () => setView("plan"));
document.querySelector("#route-query-summary").addEventListener("click", () => setView("plan"));
document.querySelector("#compare-menu-button").addEventListener("click", openFeedback);
document.querySelector("#diagnostics-button").addEventListener("click", () => diagnosticsDialog.showModal());
document.querySelector("#report-button").addEventListener("click", openFeedback);
document.querySelector("#end-walk-button").addEventListener("click", endWalking);
document.querySelector("#mute-button").addEventListener("click", (event) => {
  state.muted = !state.muted;
  event.currentTarget.textContent = state.muted ? "◗" : "◖";
  showToast(state.muted ? "Guidance muted" : "Guidance unmuted");
});

detailsButton.addEventListener("click", toggleDetails);
startWalkButton.addEventListener("click", startWalking);
locateButton.addEventListener("click", toggleGpsWatch);
rerouteButton.addEventListener("click", rerouteFromCurrent);
sheetHandle.addEventListener("pointerdown", startSheetDrag);
mapElement.addEventListener("route-select", (event) => selectRoute(event.detail.index));

feedbackButtons.forEach((button) => {
  button.addEventListener("click", () => submitFeedback(button.dataset.feedbackType));
});

document.querySelectorAll("[data-view-target]").forEach((button) => {
  button.addEventListener("click", () => setView(button.dataset.viewTarget));
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".location-field")) {
    document.querySelectorAll(".suggestions").forEach((container) => {
      container.replaceChildren();
      container.classList.remove("has-results");
    });
  }
});

document.addEventListener("focusin", updateViewport);
document.addEventListener("focusout", () => window.setTimeout(updateViewport, 160));
window.addEventListener("resize", updateViewport);
window.visualViewport?.addEventListener("resize", updateViewport);
window.visualViewport?.addEventListener("scroll", updateViewport);

installSuggestions(originInput, document.querySelector("#origin-suggestions"), "origin");
installSuggestions(destinationInput, document.querySelector("#destination-suggestions"), "destination");

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/static/service-worker.js").catch(() => {});
  });
}

updateViewport();
setView("plan");
map.showHome();
loadHealth();
if (loadRouteFromQuery()) {
  window.setTimeout(() => runRouteQuery(), 0);
}
