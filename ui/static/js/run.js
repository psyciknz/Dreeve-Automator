"use strict";

(async function () {
  const activityUrl = $("#activity-url");
  const errorBox = $("#run-error");

  function display(value) {
    if (value == null || value === "") return "(empty)";
    return Array.isArray(value) ? value.join(" / ") : String(value);
  }

  function resultView(result) {
    return el("div", { class: "run-result" },
      el("strong", {}, result.applied ? "Activity updated" : "Test preview"),
      el("dl", {},
        el("dt", {}, "Current title"), el("dd", {}, display(result.current.title)),
        el("dt", {}, "Current description"), el("dd", {}, display(result.current.description)),
        el("dt", {}, "New title"), el("dd", {}, result.proposed.title),
        el("dt", {}, "New description"), el("dd", {}, result.proposed.description)));
  }

  async function processTemplate(collection, index, title, action, resultBox) {
    showError(errorBox, "");
    const url = activityUrl.value.trim();
    if (!url) {
      showError(errorBox, "Enter a Dreeve activity URL first.");
      activityUrl.focus();
      return;
    }
    if (action === "run" &&
        !confirm(`Update this activity with "${display(title)}" and the generated description?`)) {
      return;
    }
    resultBox.replaceChildren(el("p", { class: "muted" }, action === "test" ? "Testing…" : "Updating…"));
    resultBox.hidden = false;
    try {
      const result = await api("POST", "/api/run", {
        activity_url: url,
        template_type: collection,
        template_index: index,
        action,
      });
      resultBox.replaceChildren(resultView(result));
      toast(result.applied ? "Activity updated" : "Test completed");
    } catch (err) {
      resultBox.replaceChildren(el("div", { class: "form-error" }, err.message));
    }
  }

  function itemCard(collection, item, index, validationError) {
    const resultBox = el("div", { class: "run-result", hidden: true });
    const disabled = Boolean(validationError);
    const title = display(item.title);
    const buttons = el("div", { class: "actions" },
      el("button", {
        type: "button", disabled,
        onclick: () => processTemplate(collection, index, item.title, "test", resultBox),
      }, "Test"),
      el("button", {
        type: "button", class: "primary", disabled,
        onclick: () => processTemplate(collection, index, item.title, "run", resultBox),
      }, "Run"));
    return el("article", { class: "card run-item" },
      el("div", { class: "run-item-head" },
        el("h3", {}, title),
        el("span", { class: "badge" }, item.priority == null ? "priority: none" : `priority ${item.priority}`)),
      item.description ? el("p", { class: "muted" }, display(item.description)) : null,
      validationError ? el("p", { class: "err" }, "⚠ " + validationError) : null,
      buttons,
      resultBox);
  }

  async function loadCollection(collection, root) {
    const data = await api("GET", `/api/${collection}`);
    const items = data.items.map((item, index) =>
      itemCard(collection, item, index, data.errors[index]));
    root.replaceChildren(...(items.length ? items : [
      el("p", { class: "muted" }, "No templates configured."),
    ]));
  }

  try {
    await Promise.all([
      loadCollection("route-templates", $("#route-templates")),
      loadCollection("templates", $("#templates")),
    ]);
  } catch (err) {
    showError(errorBox, err.message);
  }
})();
