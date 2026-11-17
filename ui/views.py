"""HTML pages. All data is loaded by the browser from the JSON API."""
from __future__ import annotations

from flask import Blueprint, current_app, render_template

views = Blueprint("views", __name__)


@views.get("/")
def overview():
    return render_template("overview.html", active="overview")


@views.get("/markers")
def markers():
    return render_template("markers.html", active="markers")


@views.get("/templates")
def templates():
    return render_template("templates.html", active="templates")


@views.get("/route-templates")
def route_templates():
    settings = current_app.extensions["dreeve_ui"].settings
    return render_template(
        "route_templates.html", active="route-templates",
        map_lat=settings.map_lat, map_lon=settings.map_lon, map_zoom=settings.map_zoom)


@views.get("/raw")
def raw():
    return render_template("raw.html", active="raw")


@views.get("/run")
def run():
    return render_template("run.html", active="run")


@views.get("/healthz")
def healthz():
    return {"status": "ok"}
