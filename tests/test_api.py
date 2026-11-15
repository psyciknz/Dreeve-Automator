import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ui import create_app
from ui.config_store import SECRET_SENTINEL
from ui.settings import Settings

# The upstream const module is re-rooted once per process, so all tests share
# one data directory and reset it between tests.
DATA_DIR = Path(tempfile.mkdtemp(prefix="dreeve-ui-test-"))


def tearDownModule():
    shutil.rmtree(DATA_DIR, ignore_errors=True)


def make_settings(**overrides):
    base = dict(data_dir=DATA_DIR, username="", password="", map_lat=0.0,
                map_lon=0.0, map_zoom=2, max_backups=3)
    base.update(overrides)
    return Settings(**base)


MARKERS = {
    "distance": {"category": [[0, 5, "Short"], [5, None, "Long"]]},
    "start_time": {"time_of_day": [["0500", "1200", "Morning"], [None, None, "Day"]]},
    "counters": ["total"],
}


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        for child in DATA_DIR.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        self.app = create_app(make_settings())
        self.client = self.app.test_client()
        self.store = self.app.extensions["dreeve_ui"].store

    # helpers
    def rev(self):
        return self.client.get("/api/status").get_json()["revision"]

    def put(self, url, body, **kw):
        return self.client.put(url, json=body, headers={"X-Config-Revision": self.rev()}, **kw)

    def post(self, url, body):
        return self.client.post(url, json=body, headers={"X-Config-Revision": self.rev()})

    def seed(self, validate=True, **extra):
        data = {"dreeve_url": "http://x", "dreeve_api_key": "secret-key", "refresh_minutes": 5,
                "markers": MARKERS, "templates": [], "route_templates": []}
        data.update(extra)
        self.store.write_text(json.dumps(data), validate=validate)


class StatusAndGeneral(ApiTestCase):
    def test_missing_file_gives_valid_default(self):
        body = self.client.get("/api/status").get_json()
        self.assertFalse(body["exists"])
        self.assertTrue(body["valid"])
        self.assertEqual(body["revision"], "none")

    def test_meta_comes_from_upstream_constants(self):
        body = self.client.get("/api/meta").get_json()
        self.assertEqual(body["default_point_radius"], 25)
        self.assertEqual(body["refresh_minutes"]["max"], 60)
        self.assertIn("counters", body["metrics"])
        self.assertTrue(body["paths"]["config"].startswith(str(DATA_DIR.resolve())))

    def test_general_update_creates_file_and_keeps_key_hidden(self):
        r = self.put("/api/general", {"dreeve_url": "http://dreeve", "dreeve_api_key": "abc",
                                      "refresh_minutes": 10})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["dreeve_api_key_set"])
        self.assertNotIn("abc", r.get_data(as_text=True))
        self.assertEqual(json.loads(self.store.read_text())["dreeve_api_key"], "abc")
        # blank key keeps the existing one
        self.put("/api/general", {"dreeve_api_key": "", "refresh_minutes": 11})
        self.assertEqual(json.loads(self.store.read_text())["dreeve_api_key"], "abc")

    def test_refresh_minutes_out_of_range_rejected_with_upstream_message(self):
        r = self.put("/api/general", {"refresh_minutes": 1})
        self.assertEqual(r.status_code, 422)
        self.assertIn("Refresh minutes", r.get_json()["error"])
        self.assertFalse(self.store.exists())

    def test_hr_zones_round_trip_and_removal(self):
        zones = {"1": 100, "2": 120, "3": 140, "4": 160, "5": 180}
        self.assertEqual(self.put("/api/general", {"hr_zones": zones}).status_code, 200)
        self.assertEqual(json.loads(self.store.read_text())["hr_zones"], zones)
        self.put("/api/general", {"hr_zones": None})
        self.assertNotIn("hr_zones", json.loads(self.store.read_text()))
        bad = self.put("/api/general", {"hr_zones": {"1": 100, "2": 90, "3": 140, "4": 160, "5": 180}})
        self.assertEqual(bad.status_code, 422)


class Markers(ApiTestCase):
    def test_marker_save_validate_and_clear(self):
        self.seed(markers={})
        r = self.put("/api/markers/distance", {"value": MARKERS["distance"]})
        self.assertEqual(r.status_code, 200)
        bad = self.put("/api/markers/distance", {"value": {"k": [[5, 1, "x"]]}})
        self.assertEqual(bad.status_code, 422)
        self.put("/api/markers/distance", {"value": None})
        self.assertNotIn("distance", json.loads(self.store.read_text())["markers"])

    def test_marker_rename_can_be_confirmed_when_template_reference_breaks(self):
        self.seed(
            markers={"counters": ["old"]},
            templates=[{"title": "{counters.old}", "description": ""}],
        )
        rejected = self.put("/api/markers/counters", {"value": ["new"]})
        self.assertEqual(rejected.status_code, 422)
        self.assertIn("Invalid placeholder", rejected.get_json()["error"])
        self.assertTrue(rejected.get_json()["can_force"])

        saved = self.put("/api/markers/counters", {"value": ["new"], "force": True})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(json.loads(self.store.read_text())["markers"]["counters"], ["new"])
        names = [p["placeholder"] for p in self.client.get("/api/placeholders").get_json()["placeholders"]]
        self.assertIn("counters.new", names)
        self.assertNotIn("counters.old", names)

    def test_confirmed_marker_save_still_rejects_invalid_marker_data(self):
        self.seed(markers={})
        response = self.put(
            "/api/markers/distance",
            {"value": {"bad": [[5, 1, "invalid"]]}, "force": True},
        )
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.get_json().get("can_force", False))

    def test_unknown_metric_404(self):
        self.assertEqual(self.put("/api/markers/nope", {"value": {}}).status_code, 404)


class Templates(ApiTestCase):
    def test_crud(self):
        self.seed()
        item = {"title": "{distance.category} Run", "description": "", "priority": 1,
                "restrict": {"distance": [[1, 30]]}}
        r = self.post("/api/templates", item)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["index"], 0)
        item["title"] = ["{start_time.time_of_day} Run", "Run"]
        self.assertEqual(self.put("/api/templates/0", item).status_code, 200)
        listing = self.client.get("/api/templates").get_json()
        self.assertEqual(listing["items"][0]["title"], ["{start_time.time_of_day} Run", "Run"])
        self.assertEqual(listing["errors"], [None])
        self.assertEqual(self.put("/api/templates/5", item).status_code, 404)
        r = self.client.delete("/api/templates/0", headers={"X-Config-Revision": self.rev()})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/api/templates").get_json()["items"], [])

    def test_unknown_placeholder_rejected(self):
        self.seed()
        r = self.post("/api/templates", {"title": "{distance.nope}", "description": ""})
        self.assertEqual(r.status_code, 422)
        self.assertIn("Invalid placeholder", r.get_json()["error"])

    def test_list_reports_per_item_errors(self):
        self.seed(validate=False, templates=[{"title": "{distance.nope}", "description": ""}])
        errors = self.client.get("/api/templates").get_json()["errors"]
        self.assertIn("Invalid placeholder", errors[0])

    def test_placeholders_follow_markers(self):
        self.seed()
        names = [p["placeholder"] for p in self.client.get("/api/placeholders").get_json()["placeholders"]]
        self.assertIn("distance.category", names)
        self.assertIn("counters.total", names)
        self.assertIn("weather", names)
        self.assertNotIn("hr_zones", names)


class RouteTemplates(ApiTestCase):
    def test_restrict_is_always_written(self):
        self.seed()
        r = self.post("/api/route-templates", {"title": "Loop", "description": "",
                                               "points": [[-41.2, 174.8, 40]]})
        self.assertEqual(r.status_code, 201)
        saved = json.loads(self.store.read_text())["route_templates"][0]
        self.assertEqual(saved["restrict"], {})
        self.assertEqual(saved["points"], [[-41.2, 174.8, 40]])

    def test_two_templates_without_restrict_do_not_crash_the_parser(self):
        self.seed()
        for name in ("A", "B"):
            self.assertEqual(self.post("/api/route-templates", {
                "title": name, "description": "", "points": [[1, 2]]}).status_code, 201)

    def test_blacklist_and_validation(self):
        self.seed()
        ok = self.post("/api/route-templates", {
            "title": "Loop", "description": "", "points": [[1, 2, 30]],
            "restrict": {"blacklist": [[3, 4, 10]]}})
        self.assertEqual(ok.status_code, 201)
        bad = self.post("/api/route-templates", {
            "title": "Bad", "description": "", "points": [[95, 2, 30]]})
        self.assertEqual(bad.status_code, 422)
        self.assertIn("latitude out of range", bad.get_json()["error"])

    def test_empty_points_is_a_warning_not_an_error(self):
        self.seed()
        self.assertEqual(self.post("/api/route-templates", {
            "title": "Any", "description": ""}).status_code, 201)
        warnings = self.client.get("/api/status").get_json()["warnings"]
        self.assertTrue(any("no route points" in w for w in warnings))


class RawAndBackups(ApiTestCase):
    def test_raw_view_hides_key_and_save_restores_it(self):
        self.seed()
        text = self.client.get("/api/raw").get_json()["text"]
        self.assertNotIn("secret-key", text)
        self.assertIn(SECRET_SENTINEL, text)
        self.assertEqual(self.put("/api/raw", {"text": text}).status_code, 200)
        self.assertEqual(json.loads(self.store.read_text())["dreeve_api_key"], "secret-key")

    def test_raw_validation_can_be_forced(self):
        self.seed()
        data = json.loads(self.store.read_text())
        data["refresh_minutes"] = 1
        text = json.dumps(data)
        self.assertEqual(self.put("/api/raw", {"text": text}).status_code, 422)
        self.assertEqual(self.put("/api/raw", {"text": text, "force": True}).status_code, 200)
        self.assertEqual(self.put("/api/raw", {"text": "{nope", "force": True}).status_code, 422)

    def test_validate_endpoint(self):
        ok = self.client.post("/api/validate", json={"text": json.dumps(
            {"dreeve_url": "u", "dreeve_api_key": "k"})}).get_json()
        self.assertTrue(ok["valid"])
        bad = self.client.post("/api/validate", json={"text": "{}"}).get_json()
        self.assertFalse(bad["valid"])
        self.assertIn("dreeve url", bad["error"])

    def test_backups_are_created_pruned_and_restorable(self):
        self.seed()
        for minutes in (6, 7, 8, 9, 10):
            self.put("/api/general", {"refresh_minutes": minutes})
        backups = self.client.get("/api/backups").get_json()["backups"]
        self.assertEqual(len(backups), 3)  # max_backups=3
        name = backups[0]["name"]
        self.assertEqual(self.post(f"/api/backups/{name}/restore", {}).status_code, 200)
        self.assertEqual(self.post("/api/backups/config-19990101-000000.json/restore", {}).status_code, 404)
        self.assertEqual(self.post("/api/backups/..%2Fconfig.json/restore", {}).status_code, 404)

    def test_stale_revision_is_rejected(self):
        self.seed()
        r = self.client.put("/api/general", json={"refresh_minutes": 9},
                            headers={"X-Config-Revision": "deadbeef"})
        self.assertEqual(r.status_code, 409)

    def test_counters_file_is_not_created_by_validation(self):
        self.seed()
        self.assertFalse((DATA_DIR / "counters.json").exists())

    def test_non_json_body_is_a_json_error(self):
        r = self.client.put("/api/general", data="x", content_type="text/plain")
        self.assertEqual(r.status_code, 415)
        self.assertIn("error", r.get_json())


class Auth(unittest.TestCase):
    def test_basic_auth_when_configured(self):
        app = create_app(make_settings(username="me", password="pw"))
        client = app.test_client()
        self.assertEqual(client.get("/").status_code, 401)
        self.assertEqual(client.get("/healthz").status_code, 200)
        import base64
        good = {"Authorization": "Basic " + base64.b64encode(b"me:pw").decode()}
        bad = {"Authorization": "Basic " + base64.b64encode(b"me:no").decode()}
        self.assertEqual(client.get("/api/status", headers=good).status_code, 200)
        self.assertEqual(client.get("/api/status", headers=bad).status_code, 401)


class Pages(ApiTestCase):
    def test_pages_render(self):
        for url in ("/", "/markers", "/templates", "/route-templates", "/raw", "/run"):
            self.assertEqual(self.client.get(url).status_code, 200, url)


if __name__ == "__main__":
    unittest.main()
