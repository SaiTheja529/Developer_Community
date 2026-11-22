"""DevCommons API application factory."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from flask import Flask
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Settings, load_settings
from app.extensions import cors, db, limiter, migrate


class ApiJSONProvider(DefaultJSONProvider):
    """ISO 8601 UTC timestamps ('2026-11-21T10:15:00Z'), UUIDs and Decimals as JSON-friendly values."""

    sort_keys = False

    @staticmethod
    def default(o):
        if isinstance(o, datetime):
            if o.tzinfo is None:
                o = o.replace(tzinfo=UTC)
            return o.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if isinstance(o, date):
            return o.isoformat()
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, Decimal):
            return float(o)
        return DefaultJSONProvider.default(o)


def create_app(settings: Settings | None = None) -> Flask:
    settings = settings or load_settings()

    from app.common.request_context import configure_logging

    configure_logging(settings.LOG_LEVEL, json_logs=settings.APP_ENV != "test")

    if settings.SENTRY_DSN:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.APP_ENV, send_default_pii=False)

    app = Flask(__name__)
    app.json = ApiJSONProvider(app)
    app.extensions["settings"] = settings
    app.config.update(
        SECRET_KEY=settings.SECRET_KEY,
        SQLALCHEMY_DATABASE_URI=settings.DATABASE_URL,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_size": settings.DB_POOL_SIZE, "pool_pre_ping": True, "max_overflow": 10},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=256 * 1024,
        RATELIMIT_STORAGE_URI=settings.RATELIMIT_STORAGE_URI,
        RATELIMIT_ENABLED=settings.RATELIMIT_ENABLED,
        RATELIMIT_HEADERS_ENABLED=True,
        JSON_SORT_KEYS=False,
    )
    app.url_map.strict_slashes = False

    if settings.TRUST_PROXY_HOPS > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=settings.TRUST_PROXY_HOPS, x_proto=1, x_host=1)  # type: ignore[method-assign]

    from app import models as _models  # noqa: F401  (register all models)

    db.init_app(app)
    migrate.init_app(app, db, directory="migrations", compare_type=True)
    limiter.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": settings.CORS_ORIGINS}},
        supports_credentials=True,
        allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After", "X-RateLimit-Remaining"],
        max_age=600,
    )

    from app.auth.email_sender import build_sender

    app.extensions["email_sender"] = build_sender(settings)

    from app.common.errors import register_error_handlers
    from app.common.request_context import register_request_hooks

    register_request_hooks(app)
    register_error_handlers(app)
    _register_blueprints(app)

    from app.cli import register_cli

    register_cli(app)
    return app


def _register_blueprints(app: Flask) -> None:
    from app.auth.routes import bp as auth_bp
    from app.modules.admin.routes import bp as admin_bp
    from app.modules.ai.routes import bp as ai_bp
    from app.modules.collaborations.routes import bp as collab_bp
    from app.modules.collections.routes import bp as collections_bp
    from app.modules.comments.routes import bp as comments_bp
    from app.modules.comments.routes import make_comment_routes
    from app.modules.harnesses.routes import bp as harnesses_bp
    from app.modules.harnesses.routes import github_bp, reviews_bp
    from app.modules.ideas.routes import bp as ideas_bp
    from app.modules.jobs.routes import bp as jobs_bp
    from app.modules.meta.routes import bp as meta_bp
    from app.modules.notifications.routes import bp as notifications_bp
    from app.modules.reports.routes import bp as reports_bp
    from app.modules.resources.routes import bp as resources_bp
    from app.modules.suggestions.routes import bp as suggestions_bp
    from app.modules.suggestions.routes import make_suggestion_routes
    from app.modules.users.routes import bp as users_bp
    from app.modules.votes.routes import bp as votes_bp

    for bp in (
        meta_bp,
        auth_bp,
        users_bp,
        harnesses_bp,
        reviews_bp,
        github_bp,
        ideas_bp,
        resources_bp,
        collections_bp,
        comments_bp,
        suggestions_bp,
        votes_bp,
        collab_bp,
        notifications_bp,
        reports_bp,
        admin_bp,
        jobs_bp,
        ai_bp,
    ):
        app.register_blueprint(bp)
    for target in ("harness", "idea", "resource", "collection"):
        app.register_blueprint(make_comment_routes(target))
    for target in ("harness", "idea", "resource"):
        app.register_blueprint(make_suggestion_routes(target))

    _apply_write_limit(app)


def _apply_write_limit(app: Flask) -> None:
    """Writes (POST/PATCH/PUT/DELETE): 60/min per user (spec §13). Keyed from the token's subject."""
    from flask import request

    from app.common.ratelimit import client_ip, enforce

    @app.before_request
    def _write_limit():
        if request.method not in ("POST", "PATCH", "PUT", "DELETE"):
            return
        if request.path.startswith("/api/internal/") or request.path.startswith("/api/auth/"):
            return
        key = f"ip:{client_ip()}"
        header = request.headers.get("Authorization", "")
        if header.lower().startswith("bearer "):
            try:
                from app.auth.tokens import decode_access_token

                key = f"user:{decode_access_token(header[7:].strip())['sub']}"
            except Exception:
                pass
        enforce("60 per minute", "writes", key=key)
