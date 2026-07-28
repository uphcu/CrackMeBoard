import json

from flask import render_template, request, abort
from flask_login import current_user

from app.core import core_bp


# ── Honeypot routes (catch-all for known attack paths) ──

HONEYPOT_PATHS = [
    "admin.php",
    "wp-admin",
    "wp-login.php",
    "phpmyadmin",
    ".env",
    ".git/config",
    "api/v1/admin",
    "actuator/health",
    "swagger-ui.html",
]


@core_bp.route("/")
def index():
    return render_template("core/index.html")


@core_bp.route("/<path:path>")
def catch_all(path: str):
    """Catch-all route: serve honeypot + 404 for unknown paths"""
    if any(hp in path.lower() for hp in HONEYPOT_PATHS):
        # Honeypot: log the attempt
        import logging
        logging.getLogger(__name__).warning(
            f"HONEYPOT TRIGGERED: /{path} from {request.remote_addr}"
        )
        return abort(404)  # Don't reveal it's a honeypot

    return abort(404)