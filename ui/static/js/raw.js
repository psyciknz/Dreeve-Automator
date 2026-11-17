"use strict";

(function () {
  const area = $("#raw-text");
  const result = $("#raw-result");

  function say(message, ok = false) {
    result.classList.toggle("ok", ok);
    showError(result, message);
  }

  async function load() {
    try {
      const res = await api("GET", "/api/raw");
      area.value = res.text;
      say("");
    } catch (e) { say(e.message); }
  }

  $("#raw-reload").addEventListener("click", load);

  $("#raw-format").addEventListener("click", () => {
    try {
      area.value = JSON.stringify(JSON.parse(area.value), null, 4) + "\n";
      say("");
    } catch (e) { say("Not valid JSON: " + e.message); }
  });

  $("#raw-validate").addEventListener("click", async () => {
    try {
      const res = await api("POST", "/api/validate", { text: area.value });
      say(res.valid ? "Valid." : res.error, res.valid);
    } catch (e) { say(e.message); }
  });

  $("#raw-save").addEventListener("click", async () => {
    try {
      const res = await api("PUT", "/api/raw", { text: area.value, force: $("#raw-force").checked });
      area.value = res.text;
      say("Saved.", true);
      toast("Saved");
    } catch (e) { say(e.message); }
  });

  load();
})();
