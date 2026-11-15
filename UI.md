# Dreeve Config UI

A small web UI (Flask, no build step) for creating and editing the `config.json` used by
[Dreeve-Automator](https://github.com/psyciknz/Dreeve-Automator), deployable with Docker. It imports the
upstream `configure.py` / `const.py` directly, so **validation is the automator's own validation**, not a copy.

## What works today

| Page | |
|---|---|
| Overview | Dreeve URL, API key (never sent back to the browser), refresh interval, heart-rate zones; file status; backup list + restore |
| Markers | Per-metric JSON editors with format hints and examples (a structured editor is a planned improvement) |
| Templates | Create / edit / duplicate / delete; title and description alternatives; priority; distance / pace / start-time restrictions; click-to-insert placeholders taken from your markers |
| Route templates | As above plus a **Leaflet map**: click to add route points, drag to move, per-point radius, a default radius for new points, "apply radius to all", blacklist points, place search |
| Raw JSON | Edit the file directly (API key masked), validate, optional "save even if validation fails" |
| Run & test | Placeholder - next phase (see below) |

Every save is validated by upstream `configure.get_config()` before it touches disk, written atomically, and the
previous version is kept in `backups/`. Saves carry the file's revision, so a change made elsewhere (hand edit,
another tab) is refused instead of overwritten.

## Run it

```bash
docker compose up --build        # http://localhost:8000
```

Set `DREEVE_UI_USERNAME` and `DREEVE_UI_PASSWORD` (e.g. in a `.env` file next to `docker-compose.yml`) to require
a login. **Without them anyone who can reach the port can read and change your config.**

Without Docker (Python 3.10+):

```bash
pip install -r requirements.txt
DREEVE_UI_DATA_DIR=./data python wsgi.py     # http://127.0.0.1:8000
```

| Variable | Default | |
|---|---|---|
| `DREEVE_UI_DATA_DIR` | `./data` (`/data` in Docker) | Holds `config.json`, `backups/`; re-roots every path in upstream `const.py` |
| `DREEVE_UI_USERNAME` / `_PASSWORD` | unset | Enables HTTP Basic auth when both are set (`/healthz` stays open) |
| `DREEVE_UI_MAP_LAT` / `_LON` / `_ZOOM` | `20` / `0` / `2` | Where the route map opens when a template has no points yet |
| `DREEVE_UI_MAX_BACKUPS` | `20` | |

The route map loads Leaflet from unpkg and tiles from OpenStreetMap, so the browser needs internet access for that
page. Place search uses the public Nominatim service.

## Layout

```
dreeve_ui/            Flask app (app factory in __init__.py)
  bridge.py           puts vendor/.../src on sys.path, re-roots const.py paths, exposes configure/const
  validation.py       in-memory wrapper around configure.get_config() + per-item checks, placeholders
  config_store.py     atomic writes, backups, revisions, API-key masking
  api.py              JSON API (/api/...)   views.py  pages   auth.py  optional Basic auth
  templates/ static/  Jinja pages and vanilla JS (route_map.js = Leaflet wrapper)
vendor/dreeve_automator/   unmodified upstream source (see VENDORED.md for commit + how to update)
tests/                test_api.py (unittest, no browser) and e2e_smoke.py (optional Playwright)
```

Run the tests: `python -m unittest discover tests`.

## Things in the upstream code that this UI works around

* `get_config()` only builds a route template's restriction when a `restrict` key exists; without one it raises
  `UnboundLocalError` (first template) or silently reuses the *previous* template's restriction. The UI always writes
  `"restrict": {}` for route templates. Overview warns about existing ones that lack it.
* `generate.matching_route_template` is `restriction is None or (restrictions pass and all points touched)`, so a
  route template with no restriction object would match every run regardless of its points - another reason for the above.
* A route template with zero points matches everything its restrictions allow; the UI warns rather than blocks.
* Route points only need to be *passed*, in any order (`all_points_touched`); the map therefore draws no connecting line.
* `activity.update_activity` currently PATCHes only `name`; the description line is commented out upstream.

## Next phase: Run & test

Planned on top of the vendored `generate.py` / `activity.py`:

1. **Test mode** - fetch an activity, run the rules, show the title/description that *would* be written. Needs care:
   upstream `get_counter_text` increments and persists counters while rendering, and `get_activities` records
   activities as seen, so test mode must stub those.
2. **Run as configured** - process unseen activities exactly like `main.py`.
3. **Single activity** - by activity id, test or apply.
