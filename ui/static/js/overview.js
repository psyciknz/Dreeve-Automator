"use strict";

(async function () {
  const statusCard = $("#status-card");
  const form = $("#general-form");
  const errorBox = $("#general-error");
  const hrOn = $("#g-hr-on");
  const hrGrid = $("#g-hr");
  const hrInputs = [1, 2, 3, 4, 5].map((zone) => {
    const input = el("input", { type: "number", step: "1" });
    hrGrid.append(el("label", {}, "Zone " + zone, input));
    return input;
  });

  function syncHr() { hrInputs.forEach((i) => (i.disabled = !hrOn.checked)); }
  hrOn.addEventListener("change", syncHr);

  async function renderStatus() {
    const s = await api("GET", "/api/status");
    const rows = [
      el("p", {}, el("code", {}, s.config_path), " ",
        s.exists ? el("span", { class: "badge" }, "modified " + formatTime(s.modified))
                 : el("span", { class: "badge" }, "not created yet - saving anything creates it")),
      el("p", {}, s.valid ? el("span", { class: "badge good" }, "✓ valid")
                          : el("span", { class: "badge bad" }, "invalid"),
        " ", s.counts.templates !== undefined
          ? `${s.counts.templates} templates, ${s.counts.route_templates} route templates, ${s.counts.markers} marker groups`
          : ""),
    ];
    if (s.error) rows.push(el("div", { class: "form-error" }, s.error));
    s.warnings.forEach((w) => rows.push(el("p", { class: "muted" }, "⚠ " + w)));
    if (!s.auth_enabled) {
      rows.push(el("p", { class: "muted" },
        "⚠ No login is set (DREEVE_UI_USERNAME / DREEVE_UI_PASSWORD). Do not expose this UI to untrusted networks."));
    }
    statusCard.replaceChildren(el("h2", {}, "Config file"), ...rows);
  }

  async function loadGeneral() {
    const [meta, g] = await Promise.all([getMeta(), api("GET", "/api/general")]);
    $("#g-url").value = g.dreeve_url || "";
    $("#g-key").value = "";
    $("#g-key").placeholder = g.dreeve_api_key_set ? "(set - leave blank to keep)" : "not set";
    $("#g-refresh").value = g.refresh_minutes;
    $("#g-refresh").min = meta.refresh_minutes.min;
    $("#g-refresh").max = meta.refresh_minutes.max;
    $("#g-refresh-hint").textContent =
      `${meta.refresh_minutes.min}-${meta.refresh_minutes.max} minutes (default ${meta.refresh_minutes.default})`;
    const zones = g.hr_zones;
    hrOn.checked = !!zones;
    hrInputs.forEach((input, i) => {
      input.min = meta.heart_rate.min;
      input.max = meta.heart_rate.max;
      input.value = zones ? zones[String(i + 1)] ?? "" : "";
    });
    syncHr();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError(errorBox, "");
    const body = {
      dreeve_url: $("#g-url").value,
      dreeve_api_key: $("#g-key").value,
      refresh_minutes: Number($("#g-refresh").value),
      hr_zones: null,
    };
    if (hrOn.checked) {
      body.hr_zones = {};
      hrInputs.forEach((input, i) => (body.hr_zones[String(i + 1)] = Number(input.value)));
    }
    try {
      await api("PUT", "/api/general", body);
      toast("Saved");
      await Promise.all([loadGeneral(), renderStatus(), renderBackups()]);
    } catch (err) {
      showError(errorBox, err.message);
    }
  });

  async function renderBackups() {
    const { backups } = await api("GET", "/api/backups");
    const box = $("#backups");
    if (!backups.length) {
      box.replaceChildren(el("p", { class: "muted" }, "No backups yet."));
      return;
    }
    box.replaceChildren(...backups.map((b) =>
      el("div", { class: "row" },
        el("code", {}, b.name), el("span", { class: "muted" }, formatTime(b.modified)),
        el("button", {
          type: "button",
          onclick: async () => {
            if (!confirm("Restore " + b.name + "? The current file is backed up first.")) return;
            try {
              await api("POST", `/api/backups/${encodeURIComponent(b.name)}/restore`, {});
              toast("Restored " + b.name);
              await Promise.all([loadGeneral(), renderStatus(), renderBackups()]);
            } catch (err) { toast(err.message, "error"); }
          },
        }, "Restore"))));
  }

  try {
    await Promise.all([renderStatus(), loadGeneral(), renderBackups()]);
  } catch (err) {
    showError(errorBox, err.message);
  }
})();
