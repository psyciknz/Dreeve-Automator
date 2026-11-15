"""Optional HTTP Basic authentication (enabled when both env vars are set)."""
from __future__ import annotations

import hmac

from flask import Flask, Response, request

from .settings import Settings


def init_auth(app: Flask, settings: Settings) -> None:
    if not settings.auth_enabled:
        return
    expected_user = settings.username.encode()
    expected_pass = settings.password.encode()

    @app.before_request
    def require_login():
        if request.endpoint == "views.healthz":
            return None
        auth = request.authorization
        if (
            auth is not None
            and auth.type == "basic"
            and hmac.compare_digest((auth.username or "").encode(), expected_user)
            and hmac.compare_digest((auth.password or "").encode(), expected_pass)
        ):
            return None
        return Response(
            "Authentication required", 401,
            {"WWW-Authenticate": 'Basic realm="Dreeve Config UI"'})
