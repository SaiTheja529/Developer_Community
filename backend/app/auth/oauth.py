"""Sign in with GitHub / Google (addition to the spec).

Flow (OAuth 2.0 authorization code + PKCE, state in a signed, short-lived cookie):

  GET /api/auth/oauth/<p>/start     -> sets dc_oauth cookie, redirects to the provider
  GET /api/auth/oauth/<p>/callback  -> checks state, swaps the code for the profile + verified email,
                                       finds / links / creates the user, sets the normal refresh cookie,
                                       redirects to <frontend>/auth/callback

The frontend then runs its usual silent refresh, so no token ever appears in a URL. Provider access
tokens are used once to read the profile and are never stored.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit

import httpx
from flask import g, redirect, request
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import sessions
from app.auth.models import OAuthAccount
from app.common import enums
from app.common.errors import ApiError
from app.extensions import db
from app.extensions import settings as get_settings
from app.modules.users.models import User
from app.modules.users.service import username_problem

log = logging.getLogger("devcommons.oauth")
security_log = logging.getLogger("devcommons.security")

STATE_COOKIE = "dc_oauth"
STATE_COOKIE_PATH = "/api/auth/oauth"
STATE_MAX_AGE = 600
LINK_TOKEN_MAX_AGE = 300
RECENT_SIGN_IN = timedelta(minutes=15)
HTTP_TIMEOUT = 10.0
LABELS = {"github": "GitHub", "google": "Google"}


class OAuthFailure(Exception):
    """Ends the flow with a redirect to the frontend carrying `oauth_error=<code>`."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class Identity:
    provider: str
    subject: str
    email: str | None
    email_verified: bool
    login: str | None
    name: str | None
    avatar_url: str | None


# Providers ----------------------------------------------------------------------------------


class GitHubProvider:
    name = "github"
    authorize_url = "https://github.com/login/oauth/authorize"
    token_url = "https://github.com/login/oauth/access_token"
    scope = "read:user user:email"

    def authorize_params(self) -> dict:
        return {"allow_signup": "true"}

    def token_request(self, code: str, verifier: str, redirect_uri: str, cid: str, secret: str) -> dict:
        return {
            "client_id": cid,
            "client_secret": secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }

    def identity(self, http: httpx.Client, access_token: str) -> Identity:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        r = http.get("https://api.github.com/user", headers=headers)
        r.raise_for_status()
        profile = r.json()
        r = http.get("https://api.github.com/user/emails", headers=headers)
        r.raise_for_status()
        emails = [e for e in r.json() if isinstance(e, dict) and e.get("verified") and e.get("email")]
        # Prefer the primary address; any other verified address is still proven to belong to the user.
        emails.sort(key=lambda e: not e.get("primary"))
        email = emails[0]["email"] if emails else None
        return Identity(
            provider="github",
            subject=str(profile["id"]),
            email=email,
            email_verified=email is not None,
            login=profile.get("login"),
            name=profile.get("name"),
            avatar_url=profile.get("avatar_url"),
        )


class GoogleProvider:
    name = "google"
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    scope = "openid email profile"

    def authorize_params(self) -> dict:
        return {"prompt": "select_account"}

    def token_request(self, code: str, verifier: str, redirect_uri: str, cid: str, secret: str) -> dict:
        return {
            "client_id": cid,
            "client_secret": secret,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

    def identity(self, http: httpx.Client, access_token: str) -> Identity:
        r = http.get(
            "https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"}
        )
        r.raise_for_status()
        info = r.json()
        verified = info.get("email_verified") in (True, "true")
        return Identity(
            provider="google",
            subject=str(info["sub"]),
            email=info.get("email"),
            email_verified=verified,
            login=None,
            name=info.get("name"),
            avatar_url=info.get("picture"),
        )


PROVIDERS = {"github": GitHubProvider(), "google": GoogleProvider()}


def _credentials(provider: str) -> tuple[str, str] | None:
    s = get_settings()
    cid = getattr(s, f"{provider.upper()}_OAUTH_CLIENT_ID")
    secret = getattr(s, f"{provider.upper()}_OAUTH_CLIENT_SECRET")
    if not cid or not secret or not secret.get_secret_value():
        return None
    return cid, secret.get_secret_value()


def enabled_providers() -> dict[str, bool]:
    return {p: _credentials(p) is not None for p in enums.OAUTH_PROVIDERS}


def get_provider(provider: str):
    if provider not in PROVIDERS:
        raise ApiError("not_found", "Unknown sign-in provider.", 404)
    return PROVIDERS[provider]


def redirect_uri(provider: str) -> str:
    return f"{get_settings().API_PUBLIC_URL.rstrip('/')}/api/auth/oauth/{provider}/callback"


# State, PKCE, safe redirects ------------------------------------------------------------------


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().SECRET_KEY, salt=salt)


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def safe_next(value: str | None) -> str:
    """Only same-site relative paths: blocks open redirects such as //evil.example or /\\evil.example."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    if re.search(r"[\x00-\x1f]", value):
        return "/"
    return value[:500]


def _is_loopback(origin: str) -> bool:
    parts = urlsplit(origin)
    return parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1") and not parts.path


def safe_return_to(value: str | None) -> str:
    """The frontend origin to send the browser back to. Must be a known frontend origin.

    In development any http://localhost:<port> is accepted, because Vite moves to the next free port
    when 5173 is busy.
    """
    s = get_settings()
    default = s.FRONTEND_URL.rstrip("/")
    if not value:
        return default
    value = value.rstrip("/")
    allowed = {o.rstrip("/") for o in s.CORS_ORIGINS} | {default}
    if value in allowed:
        return value
    if s.APP_ENV != "production" and _is_loopback(value):
        return value
    return default


def issue_link_token(user: User) -> str:
    return _serializer("oauth-link").dumps({"uid": str(user.id)})


def _read_link_token(token: str) -> str:
    try:
        return _serializer("oauth-link").loads(token, max_age=LINK_TOKEN_MAX_AGE)["uid"]
    except (BadSignature, KeyError, TypeError) as e:
        raise OAuthFailure("link_expired") from e


def _frontend_redirect(return_to: str, path: str, **params):
    query = urlencode({k: v for k, v in params.items() if v is not None})
    return redirect(f"{return_to}{path}{'?' + query if query else ''}", code=302)


def _set_state_cookie(resp, payload: dict) -> None:
    resp.set_cookie(
        STATE_COOKIE,
        _serializer("oauth-state").dumps(payload),
        max_age=STATE_MAX_AGE,
        path=STATE_COOKIE_PATH,
        secure=get_settings().COOKIE_SECURE,
        httponly=True,
        # Lax (not Strict): the cookie must come back on the top-level redirect from the provider.
        samesite="Lax",
    )


def _clear_state_cookie(resp) -> None:
    resp.delete_cookie(STATE_COOKIE, path=STATE_COOKIE_PATH, secure=get_settings().COOKIE_SECURE, httponly=True)


# Start ----------------------------------------------------------------------------------------


def start(provider_name: str):
    provider = get_provider(provider_name)
    return_to = safe_return_to(request.args.get("return_to"))
    next_path = safe_next(request.args.get("next"))
    link = request.args.get("link")
    error_path = "/settings/account" if link else "/sign-in"
    creds = _credentials(provider_name)
    if creds is None:
        return _frontend_redirect(return_to, error_path, oauth_error="provider_not_configured", provider=provider_name)
    link_uid = None
    if link:
        try:
            link_uid = _read_link_token(link)
        except OAuthFailure as f:
            return _frontend_redirect(return_to, error_path, oauth_error=f.code, provider=provider_name)

    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce_pair()
    params = {
        "client_id": creds[0],
        "redirect_uri": redirect_uri(provider_name),
        "response_type": "code",
        "scope": provider.scope,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        **provider.authorize_params(),
    }
    resp = redirect(f"{provider.authorize_url}?{urlencode(params)}", code=302)
    _set_state_cookie(
        resp, {"p": provider_name, "s": state, "v": verifier, "r": return_to, "n": next_path, "u": link_uid}
    )
    return resp


# Callback -------------------------------------------------------------------------------------


def _fetch_identity(provider_name: str, code: str, verifier: str) -> Identity:
    provider = get_provider(provider_name)
    cid, secret = _credentials(provider_name) or (None, None)
    if cid is None:
        raise OAuthFailure("provider_not_configured")
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT, follow_redirects=False) as http:
            r = http.post(
                provider.token_url,
                data=provider.token_request(code, verifier, redirect_uri(provider_name), cid, secret),
                headers={"Accept": "application/json"},
            )
            body = r.json() if r.content else {}
            token = body.get("access_token") if isinstance(body, dict) else None
            if r.status_code >= 400 or not token:
                log.warning(
                    "oauth_token_exchange_failed",
                    extra={"provider": provider_name, "status": r.status_code, "error": (body or {}).get("error")},
                )
                raise OAuthFailure("provider_error")
            return provider.identity(http, token)
    except OAuthFailure:
        raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
        log.warning("oauth_provider_request_failed", extra={"provider": provider_name, "error": type(e).__name__})
        raise OAuthFailure("provider_error") from e


def _now() -> datetime:
    return datetime.now(UTC)


def suggest_username(identity: Identity) -> str:
    """A valid, free username from the GitHub login, the name, or the email (user can change it later)."""
    raw = identity.login or (identity.email or "").split("@")[0] or identity.name or "dev"
    base = re.sub(r"[^a-z0-9_-]+", "-", raw.lower()).strip("-_")[:24]
    if len(base) < 3:
        base = f"{base}-dev" if base else "dev"
    if not base[0].isalnum():
        base = "u" + base[1:]
    candidates = [base] + [f"{base}-{i}" for i in range(2, 20)]
    for c in candidates:
        if username_problem(c) is None:
            return c
    while True:
        c = f"{base[:20]}-{secrets.token_hex(3)}"
        if username_problem(c) is None:
            return c


def _check_status(user: User) -> None:
    if user.status == "deleted":
        raise OAuthFailure("account_unavailable")
    if user.status == "suspended":
        raise OAuthFailure("account_suspended")


def _touch(acct: OAuthAccount, identity: Identity) -> None:
    acct.last_used_at = _now()
    acct.email = identity.email
    acct.login = identity.login


def _fill_profile(user: User, identity: Identity) -> None:
    if identity.provider == "github" and identity.login and not user.github_username:
        user.github_username = identity.login
    if identity.avatar_url and not user.avatar_url and identity.avatar_url.startswith("https://"):
        user.avatar_url = identity.avatar_url[:500]


def _link(user: User, identity: Identity) -> OAuthAccount:
    existing = db.session.execute(
        select(OAuthAccount).where(OAuthAccount.user_id == user.id, OAuthAccount.provider == identity.provider)
    ).scalar_one_or_none()
    if existing is not None and existing.provider_user_id != identity.subject:
        raise OAuthFailure("provider_already_linked")
    if existing is not None:
        _touch(existing, identity)
        return existing
    acct = OAuthAccount(
        user_id=user.id,
        provider=identity.provider,
        provider_user_id=identity.subject,
        email=identity.email,
        login=identity.login,
    )
    db.session.add(acct)
    return acct


def link_identity(user_id: str, identity: Identity) -> None:
    """Settings -> Connected accounts: attach a provider to the signed-in user."""
    user = db.session.get(User, user_id)
    if user is None:
        raise OAuthFailure("link_expired")
    _check_status(user)
    owner = db.session.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == identity.provider, OAuthAccount.provider_user_id == identity.subject
        )
    ).scalar_one_or_none()
    if owner is not None and owner.user_id != user.id:
        raise OAuthFailure("already_linked_elsewhere")
    _link(user, identity)
    _fill_profile(user, identity)


def sign_in_identity(identity: Identity) -> tuple[User, dict]:
    """Returns (user, notices). Notices are flags for the frontend: new account, password removed."""
    notices: dict = {}
    acct = db.session.execute(
        select(OAuthAccount)
        .where(OAuthAccount.provider == identity.provider, OAuthAccount.provider_user_id == identity.subject)
        .with_for_update()
    ).scalar_one_or_none()
    if acct is not None:
        user = db.session.get(User, acct.user_id)
        if user is None:
            raise OAuthFailure("account_unavailable")
        _check_status(user)
        _touch(acct, identity)
    else:
        if not identity.email or not identity.email_verified:
            raise OAuthFailure("email_not_verified")
        email = identity.email.strip().lower()
        user = db.session.execute(select(User).where(User.email == email).with_for_update()).scalar_one_or_none()
        if user is not None:
            _check_status(user)
            if user.email_verified_at is None:
                # Someone may have registered this address without owning it. The provider has just
                # proven who owns it, so the old password (possibly set by someone else) is removed and
                # every existing session is signed out.
                if user.password_hash is not None:
                    user.password_hash = None
                    user.password_changed_at = _now()
                    notices["password_removed"] = "1"
                sessions.revoke_user_sessions(user.id, "password_reset")
                user.email_verified_at = _now()
                security_log.info(
                    "oauth_claimed_unverified_account", extra={"user_id": str(user.id), "provider": identity.provider}
                )
            _link(user, identity)
        else:
            user = User(
                email=email,
                email_verified_at=_now(),
                username=suggest_username(identity),
                display_name=((identity.name or identity.login or email.split("@")[0]).strip() or "Developer")[:60],
            )
            db.session.add(user)
            db.session.flush()
            _link(user, identity)
            notices["new"] = "1"
    _fill_profile(user, identity)
    user.last_login_at = _now()
    user.failed_login_count = 0
    user.locked_until = None
    return user, notices


def callback(provider_name: str):
    get_provider(provider_name)
    raw = request.cookies.get(STATE_COOKIE)
    default_return = safe_return_to(None)
    try:
        state = _serializer("oauth-state").loads(raw, max_age=STATE_MAX_AGE) if raw else None
    except BadSignature:
        state = None
    if not state or state.get("p") != provider_name:
        resp = _frontend_redirect(default_return, "/sign-in", oauth_error="state_expired", provider=provider_name)
        _clear_state_cookie(resp)
        return resp

    return_to = safe_return_to(state.get("r"))
    next_path = safe_next(state.get("n"))
    link_uid = state.get("u")
    error_path = "/settings/account" if link_uid else "/sign-in"

    def fail(code: str):
        db.session.rollback()
        resp = _frontend_redirect(return_to, error_path, oauth_error=code, provider=provider_name)
        _clear_state_cookie(resp)
        return resp

    if not hmac.compare_digest(str(state.get("s", "")), request.args.get("state", "")):
        security_log.warning("oauth_state_mismatch", extra={"provider": provider_name})
        return fail("state_mismatch")
    if request.args.get("error"):
        return fail("cancelled" if request.args.get("error") == "access_denied" else "provider_error")
    code = request.args.get("code")
    if not code:
        return fail("provider_error")

    try:
        identity = _fetch_identity(provider_name, code, state["v"])
        if link_uid:
            link_identity(link_uid, identity)
            db.session.commit()
            resp = _frontend_redirect(return_to, "/settings/account", linked=provider_name)
            _clear_state_cookie(resp)
            return resp
        user, notices = sign_in_identity(identity)
        sess, raw_refresh = sessions.create_session(user)
        db.session.commit()
    except OAuthFailure as f:
        return fail(f.code)
    except IntegrityError:
        # Two sign-ins racing to create the same account or link; the retry finds the winner's row.
        return fail("try_again")

    resp = _frontend_redirect(return_to, "/auth/callback", next=next_path, provider=provider_name, **notices)
    sessions.set_refresh_cookie(resp, raw_refresh)
    _clear_state_cookie(resp)
    log.info("oauth_sign_in", extra={"provider": provider_name, "new_user": bool(notices.get("new"))})
    return resp


# Connected accounts ---------------------------------------------------------------------------


def connections(user: User) -> dict:
    rows = (
        db.session.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id).order_by(OAuthAccount.created_at))
        .scalars()
        .all()
    )
    return {
        "has_password": user.password_hash is not None,
        "providers": enabled_providers(),
        "accounts": [
            {
                "provider": a.provider,
                "label": LABELS[a.provider],
                "email": a.email,
                "login": a.login,
                "created_at": a.created_at,
                "last_used_at": a.last_used_at,
            }
            for a in rows
        ],
    }


def unlink(user: User, provider: str) -> None:
    get_provider(provider)
    accounts = db.session.execute(select(OAuthAccount).where(OAuthAccount.user_id == user.id)).scalars().all()
    target = next((a for a in accounts if a.provider == provider), None)
    if target is None:
        raise ApiError("not_found", f"No {LABELS[provider]} account is connected.", 404)
    if user.password_hash is None and len(accounts) == 1:
        raise ApiError(
            "last_sign_in_method",
            f"{LABELS[provider]} is your only way to sign in. Set a password or connect another account first.",
            409,
        )
    db.session.delete(target)
    db.session.commit()


def require_recent_sign_in() -> None:
    """For accounts without a password: sensitive changes need a sign-in from the last 15 minutes."""
    created = g.get("session_created_at")
    if created is None or _now() - created > RECENT_SIGN_IN:
        raise ApiError(
            "reauth_required",
            "For your security, sign out and sign in again, then retry within 15 minutes.",
            403,
        )
