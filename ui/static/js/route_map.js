"use strict";

/* Leaflet map for route templates.
 *
 * Two lists of points share one map: "route" (the run must pass through every
 * one) and "blacklist" (the run must pass through none). Each point has a
 * latitude, longitude and radius in metres, matching configure.Point.
 */
class RouteMap {
  constructor(mapElement, options) {
    this.fallbackRadius = options.fallbackRadius;     // radius for [lat, lon] points (upstream default)
    this.defaultRadius = options.defaultRadius;       // radius given to newly clicked points
    this.mode = "route";
    this.tables = options.tables;                     // { route: <tbody>, blacklist: <tbody> }
    this.entries = { route: [], blacklist: [] };
    this.colors = { route: "#2563eb", blacklist: "#dc2626" };

    this.map = L.map(mapElement).setView(options.center, options.zoom);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(this.map);
    this.map.on("click", (event) =>
      this.add(this.mode, event.latlng.lat, event.latlng.lng, this.defaultRadius));
  }

  // ---- public API ------------------------------------------------------
  setPoints(route, blacklist) {
    this.clear("route", false);
    this.clear("blacklist", false);
    (route || []).forEach((p) => this.add("route", p[0], p[1], p[2] ?? this.fallbackRadius, false));
    (blacklist || []).forEach((p) => this.add("blacklist", p[0], p[1], p[2] ?? this.fallbackRadius, false));
    this.renderTables();
    this.fitAll();
  }

  getPoints(kind) {
    return this.entries[kind].map((e) => ({
      lat: Number(e.lat.toFixed(6)),
      lon: Number(e.lon.toFixed(6)),
      radius: e.radius,
    }));
  }

  setMode(mode) { this.mode = mode; }
  setDefaultRadius(radius) { this.defaultRadius = radius; }
  invalidateSize() { this.map.invalidateSize(); }

  applyRadiusToAll(kind, radius) {
    this.entries[kind].forEach((e) => this.setRadius(e, radius));
    this.renderTables();
  }

  clear(kind, render = true) {
    this.entries[kind].forEach((e) => this.removeLayers(e));
    this.entries[kind] = [];
    if (render) this.renderTables();
  }

  fitAll() {
    const all = [...this.entries.route, ...this.entries.blacklist];
    if (!all.length) return;
    const group = L.featureGroup(all.map((e) => e.circle));
    this.map.fitBounds(group.getBounds().pad(0.25), { maxZoom: 17 });
  }

  async search(query) {
    const url = "https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + encodeURIComponent(query);
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    const results = await response.json();
    if (!results.length) return false;
    this.map.setView([Number(results[0].lat), Number(results[0].lon)], 15);
    return true;
  }

  locate() { this.map.locate({ setView: true, maxZoom: 15 }); }

  // ---- internals -------------------------------------------------------
  add(kind, lat, lon, radius, render = true) {
    const entry = { kind, lat: Number(lat), lon: Number(lon), radius: Number(radius) };
    entry.marker = L.marker([entry.lat, entry.lon], { draggable: true, icon: this.icon(kind, 0) }).addTo(this.map);
    entry.circle = L.circle([entry.lat, entry.lon], {
      radius: entry.radius, color: this.colors[kind], weight: 2, fillOpacity: 0.12,
    }).addTo(this.map);

    entry.marker.on("drag", () => {
      const { lat: la, lng: lo } = entry.marker.getLatLng();
      entry.lat = la;
      entry.lon = lo;
      entry.circle.setLatLng([la, lo]);
      if (entry.inputs) {
        entry.inputs.lat.value = la.toFixed(6);
        entry.inputs.lon.value = lo.toFixed(6);
      }
    });
    this.entries[kind].push(entry);
    if (render) this.renderTables();
    return entry;
  }

  icon(kind, number) {
    return L.divIcon({
      className: "",
      html: `<div class="pin pin-${kind}">${kind === "route" ? number : "✕"}</div>`,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });
  }

  removeLayers(entry) {
    entry.marker.remove();
    entry.circle.remove();
  }

  remove(entry) {
    this.removeLayers(entry);
    this.entries[entry.kind] = this.entries[entry.kind].filter((e) => e !== entry);
    this.renderTables();
  }

  setRadius(entry, radius) {
    entry.radius = radius;
    entry.circle.setRadius(radius);
  }

  renderTables() {
    for (const kind of ["route", "blacklist"]) {
      const body = this.tables[kind];
      body.replaceChildren();
      this.entries[kind].forEach((entry, index) => {
        entry.marker.setIcon(this.icon(kind, index + 1));
        const latInput = el("input", { type: "number", step: "any", value: entry.lat.toFixed(6) });
        const lonInput = el("input", { type: "number", step: "any", value: entry.lon.toFixed(6) });
        const radiusInput = el("input", { type: "number", step: "any", min: "1", value: entry.radius });
        entry.inputs = { lat: latInput, lon: lonInput, radius: radiusInput };

        const moved = () => {
          const lat = Number(latInput.value), lon = Number(lonInput.value);
          if (Number.isFinite(lat) && Number.isFinite(lon)) {
            entry.lat = lat; entry.lon = lon;
            entry.marker.setLatLng([lat, lon]);
            entry.circle.setLatLng([lat, lon]);
          }
        };
        latInput.addEventListener("change", moved);
        lonInput.addEventListener("change", moved);
        radiusInput.addEventListener("input", () => {
          const radius = Number(radiusInput.value);
          if (radius > 0) this.setRadius(entry, radius);
        });

        body.append(el("tr", {},
          el("td", {}, kind === "route" ? index + 1 : "✕"),
          el("td", {}, latInput), el("td", {}, lonInput), el("td", {}, radiusInput),
          el("td", {},
            el("button", { type: "button", class: "icon", title: "Centre map here",
              onclick: () => this.map.setView([entry.lat, entry.lon], Math.max(this.map.getZoom(), 16)) }, "⌖"),
            el("button", { type: "button", class: "icon danger", title: "Remove point",
              onclick: () => this.remove(entry) }, "✕"))));
      });
      if (!this.entries[kind].length) {
        body.append(el("tr", {}, el("td", { colspan: 5, class: "muted" },
          kind === "route" ? "Click the map to add route points." : "No blacklist points.")));
      }
    }
  }
}
