"""Single-use, hashed, short-lived email tokens (spec §6.7)."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.auth.models import EmailToken
from app.auth.sessions import hash_token
from app.common.errors import ApiError
from app.extensions import db

LIFETIMES = {
    "verify_email": timedelta(hours=24),
    "reset_password": timedelta(hours=1),
    "change_email": timedelta(hours=24),
}


def issue(user, purpose: str, new_email: str | None = None) -> str:
    """Create a token; older unused tokens of the same purpose are invalidated."""
    db.session.execute(
        delete(EmailToken).where(
            EmailToken.user_id == user.id, EmailToken.purpose == purpose, EmailToken.used_at.is_(None)
        )
    )
    raw = secrets.token_urlsafe(32)
    db.session.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(raw),
            new_email=new_email,
            expires_at=datetime.now(UTC) + LIFETIMES[purpose],
        )
    )
    db.session.flush()
    return raw


def consume(raw: str, purposes: tuple[str, ...]) -> EmailToken:
    invalid = ApiError("invalid_token", "This link is invalid or has expired.", 400)
    if not raw or len(raw) > 200:
        raise invalid
    tok = db.session.execute(
        select(EmailToken).where(EmailToken.token_hash == hash_token(raw)).with_for_update()
    ).scalar_one_or_none()
    if tok is None or tok.purpose not in purposes or tok.used_at is not None or tok.expires_at <= datetime.now(UTC):
        raise invalid
    tok.used_at = datetime.now(UTC)
    return tok
