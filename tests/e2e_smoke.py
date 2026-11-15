"""Browser smoke test (optional): drives the real UI in headless Chrome.

Needs ``pip install playwright`` and a Chrome/Chromium binary (set CHROME_PATH
or it uses /usr/bin/google-chrome). Leaflet and map tiles come from the
internet, so Leaflet is replaced by a tiny stand-in; this checks *our*
JavaScript and API wiring, not Leaflet itself.

    python tests/e2e_smoke.py [screenshot_dir]
"""
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from ui import create_app  # noqa: E402
from ui.settings import Settings  # noqa: E402

FAKE_LEAFLET = """
window.L = {
  map() { const h = {}; const m = { setView() { return m; }, on(e, f) { h[e] = f; return m; },
    fitBounds() {}, invalidateSize() {}, getZoom() { return 5; }, locate() {}, _h: h };
    window.__map = m; return m; },
  tileLayer() { return { addTo() { return this; } }; },
  divIcon(o) { return o; },
  marker(ll) { const m = { _ll: { lat: ll[0], lng: ll[1] }, addTo() { return m; }, on() { return m; },
    remove() {}, setIcon() {}, setLatLng(p) { m._ll = { lat: p[0], lng: p[1] }; }, getLatLng() { return m._ll; } };
    return m; },
  circle() { const c = { addTo() { return c; }, remove() {}, setRadius() {}, setLatLng() {},
    getBounds() { return { pad() { return {}; } }; } }; return c; },
  featureGroup() { return { getBounds() { return { pad() { return {}; } }; } }; },
};
"""


def main():
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    data_dir = Path(tempfile.mkdtemp(prefix="dreeve-ui-e2e-"))
    app = create_app(Settings(data_dir=data_dir, username="", password="", map_lat=-41.29,
                              map_lon=174.78, map_zoom=11, max_backups=5))
    server = make_server("127.0.0.1", 0, app, threaded=True)
    base = f"http://127.0.0.1:{server.server_port}"
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config_file = Path(app.extensions["dreeve_ui"].store.path)

    problems = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=os.environ.get("CHROME_PATH", "/usr/bin/google-chrome"),
            args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        # The test deliberately triggers one 422 (invalid placeholder); the browser logs it.
        page.on("console", lambda m: m.type == "error" and "status of 422" not in m.text
                and problems.append(f"console error: {m.text}"))
        page.route("**/unpkg.com/**/leaflet.js", lambda r: r.fulfill(body=FAKE_LEAFLET, content_type="text/javascript"))
        page.route("**/unpkg.com/**/leaflet.css", lambda r: r.fulfill(body="", content_type="text/css"))
        page.dialog_handler = None
        page.on("dialog", lambda d: d.accept())

        def shot(name):
            if shots:
                page.screenshot(path=str(shots / f"{name}.png"), full_page=True)

        def config():
            return json.loads(config_file.read_text())

        # ---- overview / general
        page.goto(base + "/")
        page.wait_for_selector("#general-form")
        page.fill("#g-url", "http://dreeve.local:8080")
        page.fill("#g-key", "my-secret")
        page.fill("#g-refresh", "10")
        page.check("#g-hr-on")
        for i, v in enumerate([100, 120, 140, 160, 180]):
            page.locator(".hr-grid input").nth(i).fill(str(v))
        page.click("#general-form button[type=submit]")
        page.wait_for_selector(".toast:text-is('Saved')")
        page.wait_for_function("document.querySelector('#g-key').value === ''")   # form reloaded
        assert config()["dreeve_api_key"] == "my-secret"
        assert config()["hr_zones"]["5"] == 180
        assert page.input_value("#g-key") == ""        # never echoed back
        shot("overview")

        # ---- markers
        page.goto(base + "/markers")
        page.wait_for_selector("section.card textarea")
        for metric in ("distance", "start_time"):
            card = page.locator("section.card", has=page.locator(f"h2 code:text-is('{metric}')"))
            card.get_by_text("Insert example").click()
            card.get_by_text("Save", exact=True).click()
            page.wait_for_selector(f".toast:text-is('Saved {metric}')")
        assert set(config()["markers"]) == {"distance", "start_time"}
        shot("markers")

        # ---- templates
        page.goto(base + "/templates")
        page.click("#new-btn")
        page.wait_for_selector("#chips .chip")
        page.focus("#titles input")
        page.click("#chips .chip:text-is('start_time.time_of_day')")
        page.keyboard.type(" Run")
        page.locator("#descriptions textarea").fill("Weather:\n{weather}")
        page.fill("#f-priority", "2")
        page.click("#r-distance button.link")
        page.locator("#r-distance input").nth(0).fill("1")
        page.locator("#r-distance input").nth(1).fill("30")
        shot("template_editor")
        page.click("#save-btn")
        page.wait_for_selector("#list .item")
        saved = config()["templates"][0]
        assert saved["title"] == "{start_time.time_of_day} Run", saved
        assert saved["restrict"] == {"distance": [[1.0, 30.0]]}, saved
        assert saved["priority"] == 2
        # server-side validation error surfaces inline
        page.click("text=Edit")
        page.fill("#titles input", "{distance.nope}")
        page.click("#save-btn")
        page.wait_for_selector("#form-error:not([hidden])")
        assert "Invalid placeholder" in page.inner_text("#form-error")
        page.click("#cancel-btn")
        page.click("text=Duplicate")
        page.wait_for_function("document.querySelectorAll('#list .item').length === 2")
        page.locator("#list .item").nth(1).get_by_text("Delete").click()
        page.wait_for_function("document.querySelectorAll('#list .item').length === 1")
        assert len(config()["templates"]) == 1
        shot("templates")

        # ---- route templates
        page.goto(base + "/route-templates")
        page.wait_for_selector("#new-btn")
        page.click("#new-btn")
        page.wait_for_selector("#map")
        page.fill("#titles input", "Waterfront loop")
        page.fill("#default-radius", "40")
        for lat, lon in [(-41.2865, 174.7762), (-41.2900, 174.7800)]:
            page.evaluate("([a, b]) => window.__map._h.click({ latlng: { lat: a, lng: b } })", [lat, lon])
        page.check("input[name=map-mode][value=blacklist]")
        page.evaluate("() => window.__map._h.click({ latlng: { lat: -41.3, lng: 174.8 } })")
        page.locator("#tbl-route tr").nth(1).locator("input").nth(2).fill("60")
        page.fill("#f-priority", "1")
        shot("route_editor")
        page.click("#save-btn")
        page.wait_for_selector("#list .item")
        route = config()["route_templates"][0]
        assert route["points"] == [[-41.2865, 174.7762, 40.0], [-41.29, 174.78, 60.0]], route
        assert route["restrict"]["blacklist"] == [[-41.3, 174.8, 40.0]], route
        page.click("text=Edit")
        page.wait_for_function("document.querySelectorAll('#tbl-route tr').length === 2")
        assert page.locator("#tbl-blacklist tr").count() == 1
        page.click("#cancel-btn")
        shot("route_templates")

        # ---- raw
        page.goto(base + "/raw")
        page.wait_for_function("document.querySelector('#raw-text').value.includes('********')")
        assert "my-secret" not in page.input_value("#raw-text")
        page.click("#raw-validate")
        page.wait_for_selector("#raw-result.ok")
        shot("raw")

        browser.close()
    server.shutdown()

    if problems:
        print("FAILED:\n  " + "\n  ".join(dict.fromkeys(problems)))
        sys.exit(1)
    print("e2e smoke test passed")


if __name__ == "__main__":
    main()
