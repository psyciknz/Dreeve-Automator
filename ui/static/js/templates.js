"use strict";

/* List + editor for templates and route templates (one script, two pages). */
(async function () {
  const root = $("#collection");
  const kind = root.dataset.kind;            // "templates" | "route-templates"
  const isRoute = kind === "route-templates";
  const endpoint = "/api/" + kind;
  const noun = isRoute ? "route template" : "template";

  const listView = $("#list-view");
  const editorView = $("#editor-view");
  const formError = $("#form-error");

  let items = [];
  let errors = [];
  let editingIndex = null;                    // null = creating a new one
  let lastFocused = null;
  let fields = null;                          // editor widgets
  let routeMap = null;
  let meta = null;

  // ---- small editor widgets --------------------------------------------
  function stringList(container, values, multiline) {
    const rows = el("div", { class: "rows" });
    const add = (text) => {
      const input = multiline
        ? el("textarea", { rows: 3 }) : el("input", { type: "text" });
      input.value = text;
      input.addEventListener("focus", () => { lastFocused = input; });
      const row = el("div", { class: "row" }, input,
        el("button", { type: "button", class: "icon", title: "Remove", onclick: () => row.remove() }, "✕"));
      rows.append(row);
    };
    (values.length ? values : [""]).forEach(add);
    container.replaceChildren(rows,
      el("button", { type: "button", class: "link", onclick: () => add("") }, "+ add alternative"));
    return {
      get: () => [...rows.querySelectorAll("input,textarea")].map((i) => i.value).filter((v) => v.trim() !== ""),
    };
  }

  const toList = (value) => (value == null || value === "" ? [] : Array.isArray(value) ? value : [value]);
  const fromList = (list) => (list.length === 0 ? "" : list.length === 1 ? list[0] : list);
  const toRanges = (value) => (!value || !value.length ? [] : Array.isArray(value[0]) ? value : [value]);
  const toTimeInput = (hhmm) => (hhmm ? hhmm.slice(0, 2) + ":" + hhmm.slice(2) : "");
  const fromTimeInput = (value) => value.replace(":", "");

  function rangeList(container, ranges, type) {
    const rows = el("div", { class: "rows" });
    const add = (range) => {
      const [lo, hi] = range || ["", ""];
      let a, b;
      if (type === "time") {
        a = el("input", { type: "time" }); a.value = toTimeInput(lo);
        b = el("input", { type: "time" }); b.value = toTimeInput(hi);
      } else {
        a = el("input", { type: "number", step: "any", min: "0", placeholder: "min" }); a.value = lo ?? "";
        b = el("input", { type: "number", step: "any", min: "0", placeholder: "no max" }); b.value = hi ?? "";
      }
      const row = el("div", { class: "row range" }, a, el("span", { class: "sep" }, "to"), b,
        el("button", { type: "button", class: "icon", title: "Remove", onclick: () => row.remove() }, "✕"));
      row._inputs = [a, b];
      rows.append(row);
    };
    ranges.forEach(add);
    container.replaceChildren(rows,
      el("button", { type: "button", class: "link", onclick: () => add(null) }, "+ add range"));
    return {
      get: () => [...rows.children].flatMap((row) => {
        const [a, b] = row._inputs;
        if (type === "time") return a.value && b.value ? [[fromTimeInput(a.value), fromTimeInput(b.value)]] : [];
        if (a.value === "") return [];
        return [[Number(a.value), b.value === "" ? null : Number(b.value)]];
      }),
    };
  }

  function insertPlaceholder(text) {
    const fallback = $("#titles input, #titles textarea");
    const target = lastFocused && editorView.contains(lastFocused) ? lastFocused : fallback;
    const start = target.selectionStart ?? target.value.length;
    const end = target.selectionEnd ?? start;
    target.value = target.value.slice(0, start) + text + target.value.slice(end);
    target.focus();
    target.setSelectionRange(start + text.length, start + text.length);
  }

  async function renderChips() {
    const { placeholders } = await api("GET", "/api/placeholders");
    $("#chips").replaceChildren(...placeholders.map((p) =>
      el("button", {
        type: "button", class: "chip" + (p.group === "special" ? " special" : ""),
        title: p.group, onclick: () => insertPlaceholder("{" + p.placeholder + "}"),
      }, p.placeholder)));
  }

  // ---- editor ----------------------------------------------------------
  async function openEditor(index) {
    if (isRoute && !routeMap) {
      // Never open the editor without the map: saving would drop the points.
      toast("The map could not be loaded, so route templates can't be edited right now.", "error");
      return;
    }
    editingIndex = index;
    const item = index === null
      ? { title: "", description: "", priority: null, restrict: {}, points: [] }
      : items[index];
    $("#editor-title").textContent = (index === null ? "New " : "Edit ") + noun;
    showError(formError, "");

    const restrict = item.restrict || {};
    fields = {
      titles: stringList($("#titles"), toList(item.title), false),
      descriptions: stringList($("#descriptions"), toList(item.description), true),
      distance: rangeList($("#r-distance"), toRanges(restrict.distance), "number"),
      pace: rangeList($("#r-pace"), toRanges(restrict.pace), "number"),
      start_time: rangeList($("#r-start_time"), toRanges(restrict.start_time), "time"),
    };
    $("#f-priority").value = item.priority ?? "";

    listView.hidden = true;
    editorView.hidden = false;
    window.scrollTo({ top: 0 });
    try { await renderChips(); } catch (err) { toast(err.message, "error"); }

    if (isRoute) {
      routeMap.invalidateSize();
      routeMap.setPoints(item.points || [], restrict.blacklist || []);
    }
  }

  function closeEditor() {
    editorView.hidden = true;
    listView.hidden = false;
    editingIndex = null;
  }

  function collect() {
    const item = {
      title: fromList(fields.titles.get()),
      description: fromList(fields.descriptions.get()),
    };
    const priorityText = $("#f-priority").value.trim();
    item.priority = priorityText === "" ? null : Number(priorityText);
    if (Number.isNaN(item.priority)) throw new Error("Priority must be a whole number.");

    const restrict = {};
    for (const key of ["distance", "pace", "start_time"]) {
      const ranges = fields[key].get();
      if (ranges.length) restrict[key] = ranges;
    }
    if (isRoute) {
      const blacklist = routeMap.getPoints("blacklist").map((p) => [p.lat, p.lon, p.radius]);
      if (blacklist.length) restrict.blacklist = blacklist;
      item.restrict = restrict;
      item.points = routeMap.getPoints("route").map((p) => [p.lat, p.lon, p.radius]);
    } else if (Object.keys(restrict).length) {
      item.restrict = restrict;
    }
    return item;
  }

  async function save() {
    showError(formError, "");
    let item;
    try { item = collect(); } catch (err) { showError(formError, err.message); return; }
    try {
      if (editingIndex === null) await api("POST", endpoint, item);
      else await api("PUT", `${endpoint}/${editingIndex}`, item);
      toast("Saved");
      closeEditor();
      await load();
    } catch (err) {
      showError(formError, err.message);
    }
  }

  // ---- list ------------------------------------------------------------
  function describeRanges(ranges, unit, format = (v) => v) {
    return toRanges(ranges).map(([a, b]) => `${format(a)}–${b == null ? "∞" : format(b)}${unit}`).join(", ");
  }

  function badges(item) {
    const restrict = item.restrict || {};
    const out = [];
    out.push(el("span", { class: "badge" }, item.priority == null ? "priority: none" : "priority " + item.priority));
    if (isRoute) out.push(el("span", { class: "badge" }, `${(item.points || []).length} point(s)`));
    if (restrict.distance?.length) out.push(el("span", { class: "badge" }, "distance " + describeRanges(restrict.distance, " km")));
    if (restrict.pace?.length) out.push(el("span", { class: "badge" }, "pace " + describeRanges(restrict.pace, " s/km")));
    if (restrict.start_time?.length) out.push(el("span", { class: "badge" },
      "time " + toRanges(restrict.start_time).map(([a, b]) => `${toTimeInput(a)}–${toTimeInput(b)}`).join(", ")));
    if (restrict.blacklist?.length) out.push(el("span", { class: "badge" }, `${restrict.blacklist.length} blacklisted`));
    return out;
  }

  function titleOf(item) {
    const first = toList(item.title)[0];
    return first ? first : "(empty title)";
  }

  function renderList() {
    const box = $("#list");
    if (!items.length) {
      box.replaceChildren(el("div", { class: "card empty" }, `No ${noun}s yet.`));
      return;
    }
    box.replaceChildren(...items.map((item, index) => {
      const info = el("div", { class: "info" },
        el("div", { class: "name" }, titleOf(item)),
        el("div", { class: "meta" }, badges(item)),
        errors[index] ? el("div", { class: "err" }, "⚠ " + errors[index]) : null);
      const buttons = el("div", { class: "buttons" },
        el("button", { type: "button", onclick: () => openEditor(index) }, "Edit"),
        el("button", { type: "button", onclick: () => duplicate(index) }, "Duplicate"),
        el("button", { type: "button", class: "danger", onclick: () => remove(index) }, "Delete"));
      return el("div", { class: "card item" + (errors[index] ? " has-error" : "") }, info, buttons);
    }));
  }

  async function duplicate(index) {
    const copy = structuredClone(items[index]);
    if (Array.isArray(copy.title)) copy.title[0] += " (copy)";
    else copy.title = (copy.title || "") + " (copy)";
    try {
      await api("POST", endpoint, copy);
      toast("Duplicated");
      await load();
    } catch (err) { toast(err.message, "error"); }
  }

  async function remove(index) {
    if (!confirm(`Delete "${titleOf(items[index])}"?`)) return;
    try {
      await api("DELETE", `${endpoint}/${index}`);
      toast("Deleted");
      await load();
    } catch (err) { toast(err.message, "error"); }
  }

  async function load() {
    const res = await api("GET", endpoint);
    items = res.items;
    errors = res.errors;
    renderList();
  }

  // ---- route map wiring ------------------------------------------------
  function setupMap() {
    const radiusInput = $("#default-radius");
    const stored = Number(localStorage.getItem("dreeve-ui.defaultRadius"));
    radiusInput.value = stored > 0 ? stored : meta.default_point_radius;
    const currentRadius = () => {
      const value = Number(radiusInput.value);
      return value > 0 ? value : meta.default_point_radius;
    };

    routeMap = new RouteMap($("#map"), {
      center: [Number(root.dataset.mapLat), Number(root.dataset.mapLon)],
      zoom: Number(root.dataset.mapZoom),
      defaultRadius: currentRadius(),
      fallbackRadius: meta.default_point_radius,
      tables: { route: $("#tbl-route"), blacklist: $("#tbl-blacklist") },
    });

    radiusInput.addEventListener("input", () => {
      routeMap.setDefaultRadius(currentRadius());
      try { localStorage.setItem("dreeve-ui.defaultRadius", String(currentRadius())); } catch (err) { /* ignore */ }
    });
    $("#apply-radius").addEventListener("click", () => routeMap.applyRadiusToAll("route", currentRadius()));
    document.querySelectorAll("input[name=map-mode]").forEach((radio) =>
      radio.addEventListener("change", () => routeMap.setMode(radio.value)));
    $("#clear-route").addEventListener("click", () => routeMap.clear("route"));
    $("#clear-blacklist").addEventListener("click", () => routeMap.clear("blacklist"));

    const search = async () => {
      const query = $("#map-search").value.trim();
      if (!query) return;
      try {
        if (!(await routeMap.search(query))) toast("Nothing found for that search", "error");
      } catch (err) { toast("Search failed: " + err.message, "error"); }
    };
    $("#map-search-btn").addEventListener("click", search);
    $("#map-search").addEventListener("keydown", (event) => {
      if (event.key === "Enter") { event.preventDefault(); search(); }
    });
    $("#map-locate-btn").addEventListener("click", () => routeMap.locate());
  }

  // ---- start -----------------------------------------------------------
  $("#new-btn").addEventListener("click", () => openEditor(null));
  $("#save-btn").addEventListener("click", save);
  $("#cancel-btn").addEventListener("click", closeEditor);

  try {
    meta = await getMeta();
    if (isRoute) {
      if (typeof L === "undefined") {
        toast("The map library (Leaflet) could not be loaded - check your internet connection.", "error");
      } else {
        setupMap();
      }
    }
    await load();
  } catch (err) {
    $("#list").replaceChildren(el("div", { class: "form-error" }, err.message));
  }
})();
