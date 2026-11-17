"""Web UI for creating and editing the Dreeve-Automator config.json."""
from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from . import bridge
from .api import api
from .auth import init_auth
from .config_store import ConfigStore
from .settings import Settings
from .validation import validate_config
from .views import views


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    bridge.load(settings.data_dir)

    store = ConfigStore(
        bridge.const.CONFIG_FILE, validate_config, max_backups=settings.max_backups)

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
    app.json.sort_keys = False  # keep config key order as written
    app.extensions["dreeve_ui"] = SimpleNamespace(store=store, settings=settings)

    init_auth(app, settings)
    app.register_blueprint(views)
    app.register_blueprint(api)
    return app
