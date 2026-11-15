"""JSON API used by the browser UI (everything under /api)."""
from __future__ import annotations

import copy
import json

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from . import bridge
from .config_store import (
    SECRET_SENTINEL, ConfigInvalid, ConfigValidationError, ItemNotFound, RevisionConflict,
    default_config, redact_text,
)
from .validation import (
    available_placeholders, config_warnings, item_error, meta,
    normalize_item, validate_config, validate_marker_value,
)
from .runner import DreeveApiError, run_template

api = Blueprint("api", __name__, url_prefix="/api")


# ---- helpers -----------------------------------------------------------
def _store():
    return current_app.extensions["dreeve_ui"].store


def _expected_revision() -> str | None:
    return request.headers.get("X-Config-Revision") or None


def _respond(payload: dict | None = None, status: int = 200):
    body = dict(payload or {})
    body["revision"] = _store().revision()
    return jsonify(body), status


def _body() -> dict:
    data = request.get_json()  # 415/400 handled below for non-JSON requests
    if not isinstance(data, dict):
        raise ConfigInvalid("Request body must be a JSON object.")
    return data


def _load() -> dict:
    return _store().load()


def _section(data: dict, key: str, kind: type):
    """Return data[key] creating an empty ``kind`` when absent."""
    if data.get(key) is None:
        data[key] = kind()
    if not isinstance(data[key], kind):
        raise ConfigInvalid(
            f"'{key}' in config.json is not a {kind.__name__}; fix it in the Raw JSON editor.")
    return data[key]


# ---- error handling ----------------------------------------------------
@api.errorhandler(ConfigInvalid)
def _invalid(exc):
    return jsonify(error=exc.message), 422


@api.errorhandler(RevisionConflict)
def _conflict(exc):
    return jsonify(error=str(exc)), 409


@api.errorhandler(DreeveApiError)
def _dreeve_error(exc):
    return jsonify(error=str(exc)), 502


@api.errorhandler(ItemNotFound)
def _missing(exc):
    return jsonify(error=str(exc)), 404


@api.errorhandler(HTTPException)
def _http(exc):
    return jsonify(error=exc.description), exc.code


# ---- status / reference ------------------------------------------------
@api.get("/status")
def status():
    store = _store()
    info = {
        "config_path": str(store.path),
        "exists": store.exists(),
        "modified": store.mtime(),
        "valid": True,
        "error": None,
        "counts": {},
        "warnings": [],
        "auth_enabled": current_app.extensions["dreeve_ui"].settings.auth_enabled,
        "backups": len(store.list_backups()),
    }
    try:
        data = store.load()
        validate_config(data)
        info["counts"] = {
            "templates": len(data.get("templates") or []),
            "route_templates": len(data.get("route_templates") or []),
            "markers": sum(1 for v in (data.get("markers") or {}).values() if v),
        }
        info["warnings"] = config_warnings(data)
    except ConfigInvalid as exc:
        info["valid"] = False
        info["error"] = exc.message
    return _respond(info)


@api.get("/meta")
def get_meta():
    return _respond(meta())


@api.get("/placeholders")
def placeholders():
    return _respond({"placeholders": available_placeholders(_load())})


@api.post("/validate")
def validate():
    body = _body()
    try:
        data = json.loads(body.get("text", ""))
    except json.JSONDecodeError as exc:
        return _respond({"valid": False, "error": f"Not valid JSON: {exc}"})
    try:
        validate_config(data)
    except ConfigInvalid as exc:
        return _respond({"valid": False, "error": exc.message})
    return _respond({"valid": True, "error": None})


# ---- general settings --------------------------------------------------
@api.get("/general")
def get_general():
    data = _load()
    return _respond({
        "dreeve_url": data.get("dreeve_url", ""),
        "dreeve_api_key_set": bool(data.get("dreeve_api_key")),
        "refresh_minutes": data.get("refresh_minutes", bridge.configure.DEFAULT_REFRESH_MINUTES),
        "hr_zones": data.get("hr_zones"),
    })


@api.put("/general")
def put_general():
    body = _body()

    def apply(data: dict):
        if "dreeve_url" in body:
            if not isinstance(body["dreeve_url"], str):
                raise ConfigInvalid("Dreeve URL must be text.")
            data["dreeve_url"] = body["dreeve_url"].strip()
        data.setdefault("dreeve_url", "")
        key = body.get("dreeve_api_key")
        if isinstance(key, str) and key.strip() and key != SECRET_SENTINEL:
            data["dreeve_api_key"] = key.strip()
        data.setdefault("dreeve_api_key", "")
        if "refresh_minutes" in body:
            data["refresh_minutes"] = body["refresh_minutes"]
        if "hr_zones" in body:
            if body["hr_zones"] is None:
                data.pop("hr_zones", None)
            else:
                data["hr_zones"] = body["hr_zones"]

    _store().update(apply, _expected_revision())
    return get_general()


# ---- markers -----------------------------------------------------------
@api.get("/markers")
def get_markers():
    data = _load()
    return _respond({"markers": data.get("markers") or {}, "metrics": meta()["metrics"]})


@api.put("/markers/<metric>")
def put_marker(metric: str):
    if metric not in meta()["metrics"]:
        raise ItemNotFound(f"Unknown marker metric {metric!r}.")
    body = _body()
    value = body.get("value")
    force = body.get("force", False)
    if not isinstance(force, bool):
        raise ConfigInvalid("'force' must be a boolean.")
    validate_marker_value(metric, value)

    def apply(data: dict):
        markers = _section(data, "markers", dict)
        if value in (None, {}, []):
            markers.pop(metric, None)
        else:
            markers[metric] = value

    try:
        _store().update(apply, _expected_revision(), validate=not force)
    except ConfigValidationError as exc:
        return jsonify(error=exc.message, can_force=True), 422
    return get_markers()


# ---- templates and route templates -------------------------------------
def _register_collection(path: str, key: str, is_route: bool) -> None:
    label = "route template" if is_route else "template"

    def list_items():
        data = _load()
        items = data.get(key) or []
        errors = [item_error(data, item, is_route) for item in items]
        return _respond({"items": items, "errors": errors})

    def create():
        item = normalize_item(_body(), is_route)

        def apply(data: dict):
            items = _section(data, key, list)
            items.append(item)
            return len(items) - 1

        index = _store().update(apply, _expected_revision())
        return _respond({"index": index, "item": item}, 201)

    def replace(index: int):
        item = normalize_item(_body(), is_route)

        def apply(data: dict):
            items = _section(data, key, list)
            if not 0 <= index < len(items):
                raise ItemNotFound(f"No {label} at position {index}.")
            items[index] = item

        _store().update(apply, _expected_revision())
        return _respond({"index": index, "item": item})

    def delete(index: int):
        def apply(data: dict):
            items = _section(data, key, list)
            if not 0 <= index < len(items):
                raise ItemNotFound(f"No {label} at position {index}.")
            return items.pop(index)

        removed = _store().update(apply, _expected_revision())
        return _respond({"deleted": removed})

    api.add_url_rule(path, f"list_{key}", list_items, methods=["GET"])
    api.add_url_rule(path, f"create_{key}", create, methods=["POST"])
    api.add_url_rule(f"{path}/<int:index>", f"replace_{key}", replace, methods=["PUT"])
    api.add_url_rule(f"{path}/<int:index>", f"delete_{key}", delete, methods=["DELETE"])


_register_collection("/templates", "templates", is_route=False)
_register_collection("/route-templates", "route_templates", is_route=True)


# ---- single-template run / test ---------------------------------------
@api.post("/run")
def run_selected_template():
    body = _body()
    activity_url = body.get("activity_url")
    collection = body.get("template_type")
    index = body.get("template_index")
    action = body.get("action")
    if not isinstance(activity_url, str):
        raise ConfigInvalid("'activity_url' must be a URL.")
    if collection not in ("templates", "route_templates"):
        raise ConfigInvalid("'template_type' must be templates or route_templates.")
    if type(index) is not int or index < 0:
        raise ConfigInvalid("'template_index' must be a non-negative integer.")
    if action not in ("test", "run"):
        raise ConfigInvalid("'action' must be test or run.")

    expected = _expected_revision()
    if expected is not None and expected != _store().revision():
        raise RevisionConflict(
            "config.json changed on disk since this page was loaded. "
            "Reload the page to see the latest version.")
    result = run_template(_load(), activity_url, collection, index, action)
    return _respond(result)


# ---- raw JSON ----------------------------------------------------------
@api.get("/raw")
def get_raw():
    store = _store()
    text = store.read_text()
    if not text.strip():
        text = json.dumps(default_config(), indent=4) + "\n"
    return _respond({"text": redact_text(text), "exists": store.exists()})


@api.put("/raw")
def put_raw():
    body = _body()
    text = body.get("text")
    if not isinstance(text, str):
        raise ConfigInvalid("'text' must be a string.")
    _store().write_text(text, _expected_revision(), validate=not body.get("force"))
    return get_raw()


# ---- backups -----------------------------------------------------------
@api.get("/backups")
def list_backups():
    return _respond({"backups": _store().list_backups()})


@api.post("/backups/<name>/restore")
def restore_backup(name: str):
    _store().restore_backup(name, _expected_revision())
    return _respond({"restored": name})
