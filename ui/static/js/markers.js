"use strict";

(async function () {
  const HINTS = {
    distance: ["Kilometres. Rows: [min, max, \"title\", \"description\"]; max may be null; description optional. Range is min <= value < max.",
      { category: [[0, 5, "Short", "Under 5k"], [5, null, "Long", "5k+"]] }],
    moving_time: ["Whole seconds (integers). Same row format as distance.",
      { length: [[0, 1800, "Quick"], [1800, null, "Long"]] }],
    elapsed_time: ["Whole seconds (integers). Same row format as distance.",
      { length: [[0, 3600, "Under an hour"], [3600, null, "Over an hour"]] }],
    pace: ["Seconds per km. Same row format as distance. A row with null min and max is the fallback.",
      { intensity: [[360, 600, "Easy"], [300, 360, "Steady"], [null, null, "Run"]] }],
    start_time: ["24-hour HHMM strings: [from, to, \"title\", \"description\"]. A range may wrap past midnight (2300 -> 0500). [null, null, ...] is the fallback.",
      { time_of_day: [["0500", "1200", "Morning"], ["1200", "1700", "Afternoon"], ["1700", "2300", "Evening"], [null, null, "Night"]] }],
    date: ["Rows: [\"YYYY-MM-DD\", \"title\", \"description\"]; * is a wildcard (*-12-25). [null, \"title\"] is the fallback.",
      { dates: [["*-12-25", "Christmas", "Merry Christmas!"], [null, ""]] }],
    elevation: ["Metres climbed. Same row format as distance.", { climb: [[0, 100, "Flat"], [100, null, "Hilly"]] }],
    elevation_per_km: ["Metres climbed per km. Same row format as distance.", { hilliness: [[0, 10, "Flat"], [10, null, "Hilly"]] }],
    cadence: ["Steps per minute. Same row format as distance.", { rhythm: [[0, 160, "Relaxed"], [160, null, "Quick feet"]] }],
    counters: ["A list of counter names. {counters.name} becomes the next number each time it is used; the automator keeps the running totals in counters.json.",
      ["total"]],
  };

  const root = $("#markers");
  let markers = {};

  function pretty(value) { return JSON.stringify(value, null, 2); }

  function card(metric) {
    const [hint, example] = HINTS[metric] || ["", {}];
    const empty = metric === "counters" ? [] : {};
    const current = markers[metric] ?? empty;
    const area = el("textarea", { class: "code", rows: 7, spellcheck: "false" });
    area.value = Object.keys(current).length || current.length ? pretty(current) : "";
    const err = el("div", { class: "form-error", hidden: true });

    const save = async () => {
      showError(err, "");
      let value = null;
      if (area.value.trim()) {
        try { value = JSON.parse(area.value); } catch (e) { showError(err, "Not valid JSON: " + e.message); return; }
      }
      try {
        let res;
        try {
          res = await api("PUT", `/api/markers/${metric}`, { value });
        } catch (e) {
          if (e.status !== 422 || !e.data || e.data.can_force !== true) throw e;
          if (!confirm(`This marker change will leave part of the config invalid:\n\n${e.message}\n\nSave the marker anyway? You can fix affected templates afterward.`)) {
            showError(err, e.message);
            return;
          }
          res = await api("PUT", `/api/markers/${metric}`, { value, force: true });
        }
        markers = res.markers;
        area.value = markers[metric] ? pretty(markers[metric]) : "";
        toast(`Saved ${metric}`);
      } catch (e) { showError(err, e.message); }
    };

    return el("section", { class: "card" },
      el("h2", {}, el("code", {}, metric)),
      el("p", { class: "muted" }, hint),
      area, err,
      el("div", { class: "actions" },
        el("button", { class: "primary", type: "button", onclick: save }, "Save"),
        el("button", { type: "button", onclick: () => { area.value = pretty(example); } }, "Insert example"),
        el("button", { type: "button", onclick: () => { area.value = markers[metric] ? pretty(markers[metric]) : ""; showError(err, ""); } }, "Revert")));
  }

  try {
    const res = await api("GET", "/api/markers");
    markers = res.markers;
    root.replaceChildren(...res.metrics.map(card));
  } catch (e) {
    root.replaceChildren(el("div", { class: "form-error" }, e.message));
  }
})();
