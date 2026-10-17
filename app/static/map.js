const ROUTE_COLORS = {
  recommended: "#ff5da2",
  fastest: "#b9adb4",
  flattest: "#4fd2a1",
  accessible: "#ae82ff",
};

export class FlemmeMap {
  constructor(element) {
    this.element = element;
    this.map = null;
    this.layers = [];
    this.positionLayers = [];
    this.routes = [];
    this.selectedIndex = 0;
    this.currentPosition = null;
    this.ensureMap();
  }

  ensureMap() {
    if (!window.L || this.map) {
      return this.map;
    }
    this.element.replaceChildren();
    this.map = window.L.map(this.element, {
      zoomControl: false,
      attributionControl: true,
    }).setView([37.7749, -122.4194], 13);
    this.map.attributionControl.setPrefix(false);
    window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      detectRetina: true,
      className: "clean-map-tiles",
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(this.map);
    if (window.matchMedia("(min-width: 900px)").matches) {
      window.L.control.zoom({ position: "bottomright" }).addTo(this.map);
    }
    return this.map;
  }

  showHome() {
    const map = this.ensureMap();
    if (!map) {
      this.drawFallback("San Francisco");
      return;
    }
    this.clearRoutes();
    map.setView([37.7749, -122.4194], 13);
  }

  setRoutes(routes, selectedIndex = 0, { fit = true } = {}) {
    this.routes = routes;
    this.selectedIndex = selectedIndex;
    const map = this.ensureMap();
    if (!map) {
      this.drawFallback("Route ready");
      return;
    }
    this.clearRoutes();
    const bounds = window.L.latLngBounds([]);

    routes.forEach((route, index) => {
      if (index === selectedIndex) {
        return;
      }
      this.addRoute(route, false, bounds);
    });
    const selected = routes[selectedIndex];
    if (!selected) {
      return;
    }
    this.addRoute(selected, true, bounds);
    this.addEndpoints(selected, bounds);
    this.drawPosition();

    if (fit && bounds.isValid()) {
      map.fitBounds(bounds.pad(0.14), this.fitOptions());
    }
  }

  selectRoute(index) {
    this.setRoutes(this.routes, index);
  }

  addRoute(route, selected, bounds) {
    const latLngs = route.geometry.map(([lon, lat]) => [lat, lon]);
    if (latLngs.length < 2) {
      return;
    }
    latLngs.forEach((point) => bounds.extend(point));
    const outline = window.L.polyline(latLngs, {
      color: "#241f22",
      opacity: selected ? 0.96 : 0.76,
      weight: selected ? 11 : 8,
      lineCap: "round",
      lineJoin: "round",
      interactive: false,
    }).addTo(this.map);
    const line = window.L.polyline(latLngs, {
      color: selected ? (ROUTE_COLORS[route.label] || ROUTE_COLORS.recommended) : "#9d9298",
      opacity: selected ? 0.98 : 0.55,
      weight: selected ? 6 : 4,
      dashArray: selected ? null : "2 9",
      lineCap: "round",
      lineJoin: "round",
    }).addTo(this.map);
    if (!selected) {
      line.on("click", () => {
        const index = this.routes.indexOf(route);
        this.element.dispatchEvent(new CustomEvent("route-select", { detail: { index } }));
      });
    }
    this.layers.push(outline, line);
  }

  addEndpoints(route, bounds) {
    if (!route.geometry.length) {
      return;
    }
    const [startLon, startLat] = route.geometry[0];
    const [endLon, endLat] = route.geometry[route.geometry.length - 1];
    const start = [startLat, startLon];
    const end = [endLat, endLon];
    bounds.extend(start);
    bounds.extend(end);
    const startIcon = window.L.divIcon({
      className: "route-endpoint-icon",
      html: '<span class="location-marker origin-marker" aria-hidden="true"></span>',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
    const endIcon = window.L.divIcon({
      className: "route-endpoint-icon",
      html: '<span class="location-marker destination-marker" aria-hidden="true"></span>',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
    this.layers.push(
      window.L.marker(start, { icon: startIcon, keyboard: false }).addTo(this.map),
      window.L.marker(end, { icon: endIcon, keyboard: false }).addTo(this.map)
    );
  }

  setCurrentPosition(position, { follow = false } = {}) {
    this.currentPosition = position;
    this.drawPosition();
    if (follow && this.map && position) {
      this.map.panTo([position.lat, position.lon], { animate: true });
    }
  }

  drawPosition() {
    this.positionLayers.forEach((layer) => layer.remove());
    this.positionLayers = [];
    if (!this.map || !this.currentPosition) {
      return;
    }
    const point = [this.currentPosition.lat, this.currentPosition.lon];
    if (this.currentPosition.accuracy_m) {
      this.positionLayers.push(
        window.L.circle(point, {
          color: "#72a3ff",
          fillColor: "#72a3ff",
          fillOpacity: 0.14,
          radius: this.currentPosition.accuracy_m,
          weight: 1,
        }).addTo(this.map)
      );
    }
    this.positionLayers.push(
      window.L.circleMarker(point, {
        color: "#241f22",
        fillColor: "#72a3ff",
        fillOpacity: 1,
        radius: 8,
        weight: 4,
      }).addTo(this.map)
    );
  }

  clearRoutes() {
    this.layers.forEach((layer) => layer.remove());
    this.layers = [];
    this.positionLayers.forEach((layer) => layer.remove());
    this.positionLayers = [];
  }

  invalidate() {
    window.setTimeout(() => this.map?.invalidateSize({ pan: false }), 80);
  }

  fitOptions() {
    if (window.matchMedia("(min-width: 900px)").matches) {
      return { paddingTopLeft: [450, 70], paddingBottomRight: [42, 42], maxZoom: 16 };
    }
    return { paddingTopLeft: [28, 110], paddingBottomRight: [28, 320], maxZoom: 15 };
  }

  drawFallback(label) {
    this.element.innerHTML = `<div class="fallback-map" aria-label="${label}"><span>${label}</span></div>`;
  }
}
