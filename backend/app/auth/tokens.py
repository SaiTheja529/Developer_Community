"""Access-token JWTs with kid-based key rotation (spec §6.2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.common.errors import ApiError
from app.extensions import settings as get_settings


def issue_access_token(user, session_id) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    ttl = s.ACCESS_TOKEN_TTL_SECONDS
    claims = {
        "iss": s.JWT_ISSUER,
        "aud": s.JWT_AUDIENCE,
        "sub": str(user.id),
        "sid": str(session_id),
        "role": user.role,
        "email_verified": user.email_verified_at is not None,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=ttl),
        "jti": str(uuid.uuid4()),
    }
    kid = s.JWT_ACTIVE_KID
    token = jwt.encode(claims, s.signing_key(kid), algorithm="HS256", headers={"kid": kid})
    return token, ttl


def decode_access_token(token: str, verify_exp: bool = True) -> dict:
    s = get_settings()
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.PyJWTError as e:
        raise ApiError("unauthenticated", "Invalid access token.", 401) from e
    key = s.signing_key(kid) if kid else None
    if key is None:
        raise ApiError("unauthenticated", "Invalid access token.", 401)
    try:
        return jwt.decode(
            token,
            key,
            algorithms=["HS256"],  # explicit allow-list; never trust the header's alg
            audience=s.JWT_AUDIENCE,
            issuer=s.JWT_ISSUER,
            options={"require": ["exp", "iat", "nbf", "sub", "sid", "iss", "aud"], "verify_exp": verify_exp},
            leeway=30,
        )
    except jwt.ExpiredSignatureError as e:
        raise ApiError("token_expired", "Access token expired. Refresh and retry.", 401) from e
    except jwt.PyJWTError as e:
        raise ApiError("unauthenticated", "Invalid access token.", 401) from e
