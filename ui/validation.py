"""Validation built on the upstream ``configure.py`` - the single source of truth.

``configure.get_config()`` reads a fixed file and has a side effect (it
creates the counters file). To validate a candidate config in memory we point
``configure.CONFIG_FILE`` at an in-memory object and swap its ``counters``
module for a no-op for the duration of the call.
"""
from __future__ import annotations

import dataclasses
import io
import json
import threading
import types

from . import bridge
from .config_store import ConfigInvalid

_lock = threading.Lock()


class _MemoryFile:
    """Quacks like the ``Path`` that configure.get_config() opens."""

    def __init__(self, text: str):
        self._text = text

    def open(self, *args, **kwargs):
        return io.StringIO(self._text)


_NO_COUNTER_IO = types.SimpleNamespace(
    get_counters=lambda: {}, update_counters=lambda counters: None)


def describe(exc: Exception) -> str:
    if isinstance(exc, KeyError):
        return f"Missing required key {exc}"
    return str(exc) or type(exc).__name__


def validate_config(data) -> None:
    """Raise ConfigInvalid with the upstream message if ``data`` is rejected."""
    if not isinstance(data, dict):
        raise ConfigInvalid("The config must be a JSON object.")
    try:
        text = json.dumps(data)
    except (TypeError, ValueError) as exc:
        raise ConfigInvalid(f"Config is not serialisable: {exc}") from exc
    configure = bridge.configure
    with _lock:
        original = (configure.CONFIG_FILE, configure.counters)
        configure.CONFIG_FILE = _MemoryFile(text)
        configure.counters = _NO_COUNTER_IO
        try:
            configure.get_config()
        except Exception as exc:  # upstream raises ValueError/TypeError/KeyError and more
            raise ConfigInvalid(describe(exc)) from exc
        finally:
            configure.CONFIG_FILE, configure.counters = original


def validate_marker_value(metric: str, value) -> None:
    """Validate marker data without validating templates that may reference it."""
    if value is None or value == {} or value == []:
        return
    configure = bridge.configure
    validators = {
        "distance": configure.validate_distance_markers,
        "moving_time": configure.validate_moving_time_markers,
        "elapsed_time": configure.validate_elapsed_time_markers,
        "pace": configure.validate_pace_markers,
        "start_time": configure.validate_start_time_markers,
        "date": configure.validate_date_markers,
        "elevation": configure.validate_elevation_markers,
        "elevation_per_km": configure.validate_elevation_per_km_markers,
        "cadence": configure.validate_cadence_markers,
        "counters": configure.validate_counters,
    }
    with _lock:
        original = configure.counters
        configure.counters = _NO_COUNTER_IO
        try:
            validators[metric](value)
        except Exception as exc:
            raise ConfigInvalid(describe(exc)) from exc
        finally:
            configure.counters = original


def markers_from_dict(data: dict):
    """Build the upstream Markers object the way get_config() does (no checks)."""
    markers = data.get("markers")
    if not isinstance(markers, dict):
        return None
    names = [f.name for f in dataclasses.fields(bridge.configure.Markers)]
    return bridge.configure.Markers(**{name: markers.get(name, {}) for name in names})


def item_error(data: dict, item, is_route: bool) -> str | None:
    """Validate one template / route template against the current markers."""
    configure = bridge.configure
    has_hr_zones = data.get("hr_zones") is not None
    markers = markers_from_dict(data)
    try:
        if is_route:
            configure.validate_route_template(item, markers, has_hr_zones)
        else:
            configure.validate_template(item, markers, has_hr_zones)
    except Exception as exc:
        return describe(exc)
    return None


def normalize_item(item, is_route: bool):
    """Shape a template the way the upstream parser needs it.

    Upstream ``get_config`` only assigns a route template's restriction when a
    ``restrict`` key exists, otherwise it raises UnboundLocalError (first item)
    or silently reuses the previous template's restriction. Always writing an
    ``restrict`` object avoids both.
    """
    if not isinstance(item, dict):
        raise ConfigInvalid("A template must be a JSON object.")
    if is_route:
        if item.get("restrict") is None:
            item["restrict"] = {}
        if item.get("points") is None:
            item["points"] = []
    return item


def available_placeholders(data: dict) -> list[dict]:
    configure = bridge.configure
    markers = data.get("markers") if isinstance(data.get("markers"), dict) else {}
    found: list[dict] = []
    for field in dataclasses.fields(configure.Markers):
        section = markers.get(field.name) or {}
        keys = list(section) if isinstance(section, (dict, list)) else []
        for key in keys:
            if isinstance(key, str):
                found.append({"placeholder": f"{field.name}.{key}", "group": field.name})
    found.append({"placeholder": configure.WEATHER_PLACEHOLDER, "group": "special"})
    if data.get("hr_zones") is not None:
        found.append({"placeholder": configure.HR_ZONES_PLACEHOLDER, "group": "special"})
    return found


def config_warnings(data: dict) -> list[str]:
    warnings = []
    for number, route in enumerate(data.get("route_templates") or [], start=1):
        if not isinstance(route, dict):
            continue
        if route.get("restrict") is None:
            warnings.append(
                f"Route template #{number} has no 'restrict' key. The upstream "
                "parser can crash or reuse another template's restrictions; "
                "saving it from this UI fixes that.")
        if not route.get("points"):
            warnings.append(
                f"Route template #{number} has no route points, so it matches "
                "every activity that passes its restrictions.")
    return warnings


def meta() -> dict:
    configure, const = bridge.configure, bridge.const
    return {
        "refresh_minutes": {
            "min": configure.MIN_REFRESH_MINUTES,
            "max": configure.MAX_REFRESH_MINUTES,
            "default": configure.DEFAULT_REFRESH_MINUTES,
        },
        "heart_rate": {"min": configure.MIN_HEART_RATE, "max": configure.MAX_HEART_RATE},
        "default_point_radius": configure.DEFAULT_POINT_RADIUS,
        "max_abs_latitude": configure.MAX_ABS_LATITUDE,
        "max_abs_longitude": configure.MAX_ABS_LONGITUDE,
        "special_placeholders": [configure.WEATHER_PLACEHOLDER, configure.HR_ZONES_PLACEHOLDER],
        "metrics": [f.name for f in dataclasses.fields(configure.Markers)],
        "paths": {"config": str(const.CONFIG_FILE), "data": str(const.DATA_FOLDER)},
    }
