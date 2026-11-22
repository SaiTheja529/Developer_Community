"""Flask extension singletons."""

from __future__ import annotations

from flask import current_app, has_app_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
cors = CORS()


def _ip_key() -> str:
    from app.common.ratelimit import client_ip

    return client_ip()


limiter = Limiter(key_func=_ip_key, default_limits=["300 per minute"], headers_enabled=True)


def settings():
    """Return the typed Settings object for the current app."""
    if has_app_context():
        return current_app.extensions["settings"]
    from app.config import load_settings

    return load_settings()
