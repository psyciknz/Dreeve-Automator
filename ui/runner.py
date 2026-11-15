"""Run or preview one selected template against one Dreeve activity."""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

import requests

from . import bridge
from .config_store import ConfigInvalid
from .validation import config_from_data

_ACTIVITY_SLUG = re.compile(r"activity-[A-Za-z0-9-]+$")


class DreeveApiError(Exception):
    """A request to the configured Dreeve API failed."""


def activity_id_from_url(activity_url: str) -> str:
    """Extract the full activity slug from a Dreeve activity URL."""
    parsed = urlsplit(activity_url.strip())
    segments = [unquote(segment) for segment in parsed.path.rstrip("/").split("/")]
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or len(segments) < 2
        or segments[-2] != "activities"
        or not _ACTIVITY_SLUG.fullmatch(segments[-1])
    ):
        raise ConfigInvalid(
            "Enter a Dreeve URL ending in /activities/activity-<id>.")
    return segments[-1]


def run_template(
    data: dict,
    activity_url: str,
    collection: str,
    index: int,
    action: str,
) -> dict:
    """Generate an update for one template and optionally patch the activity."""
    activity_id = activity_id_from_url(activity_url)
    raw_templates = data.get(collection)
    if not isinstance(raw_templates, list) or not 0 <= index < len(raw_templates):
        raise ConfigInvalid("The selected template no longer exists.")
    config_data = dict(data)
    config_data["templates"] = (
        [raw_templates[index]] if collection == "templates" else [])
    config_data["route_templates"] = (
        [raw_templates[index]] if collection == "route_templates" else [])
    config = config_from_data(config_data)
    template = getattr(config, collection)[0]

    import activity
    import dreeve_api
    import generate

    session = dreeve_api.create_session(config.dreeve_url, config.dreeve_api_key)
    try:
        activity_data = activity.get_activity(activity_id, session)
    except (requests.RequestException, RuntimeError) as exc:
        raise DreeveApiError(f"Could not fetch activity: {exc}") from exc
    counter_values = (
        bridge.configure.counters.get_counters() if action == "test" else None)
    try:
        title, description = generate.generate_for_template(
            activity_data, template, config, counter_values)
    except RuntimeError as exc:
        raise ConfigInvalid(
            str(exc) or "The selected template cannot generate an update for this activity."
        ) from exc

    if action == "run":
        try:
            activity.update_activity(activity_id, title, description, session)
        except (requests.RequestException, RuntimeError) as exc:
            raise DreeveApiError(f"Could not update activity: {exc}") from exc

    return {
        "activity_id": activity_id,
        "template_type": collection,
        "template_index": index,
        "action": action,
        "applied": action == "run",
        "current": {
            "title": activity_data.title,
            "description": activity_data.description,
        },
        "proposed": {"title": title, "description": description},
    }
