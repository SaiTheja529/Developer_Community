"""Sign in with GitHub / Google: state + PKCE, account creation, linking, takeover protection, unlinking."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from sqlalchemy import select, update

from app.auth.models import AuthSession, OAuthAccount
from app.extensions import db
from app.modules.users.models import User
from tests.conftest import CSRF_HEADERS, PASSWORD, auth_header, make_user

FRONT = "http://localhost:5173"


@pytest.fixture(autouse=True)
def providers_on(settings):
    from pydantic import SecretStr

    settings.GITHUB_OAUTH_CLIENT_ID = "gh-client"
    settings.GITHUB_OAUTH_CLIENT_SECRET = SecretStr("gh-secret")
    settings.GOOGLE_OAUTH_CLIENT_ID = "g-client"
    settings.GOOGLE_OAUTH_CLIENT_SECRET = SecretStr("g-secret")
    settings.API_PUBLIC_URL = "http://localhost:5001"


def mock_github(gh_id=101, login="octo-ada", email="ada@example.com", verified=True, primary=True, token_ok=True):
    respx.post("https://github.com/login/oauth/access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "gho_x"} if token_ok else {"error": "bad_verification_code"})
    )
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json={"id": gh_id, "login": login, "name": "Ada Lovelace", "avatar_url": "https://avatars.githubusercontent.com/u/1"})
    )
    emails = [{"email": email, "primary": primary, "verified": verified}] if email else []
    respx.get("https://api.github.com/user/emails").mock(return_value=httpx.Response(200, json=emails))


def mock_google(sub="g-777", email="grace@example.com", verified=True, name="Grace Hopper"):
    respx.post("https://oauth2.googleapis.com/token").mock(return_value=httpx.Response(200, json={"access_token": "ya29"}))
    respx.get("https://openidconnect.googleapis.com/v1/userinfo").mock(
        return_value=httpx.Response(200, json={"sub": sub, "email": email, "email_verified": verified, "name": name})
    )


def start(client, provider="github", **params):
    r = client.get(f"/api/auth/oauth/{provider}/start", query_string=params)
    assert r.status_code == 302, r.data
    return r, parse_qs(urlsplit(r.location).query)


def finish(client, provider="github", state=None, **extra):
    _, q = start(client, provider, next="/harnesses/new")
    params = {"code": "abc", "state": state or q["state"][0], **extra}
    return client.get(f"/api/auth/oauth/{provider}/callback", query_string=params)


def humans():
    return db.session.execute(select(User).where(User.email.is_not(None))).scalars().all()


def landing(r):
    u = urlsplit(r.location)
    return f"{u.scheme}://{u.netloc}", u.path, {k: v[0] for k, v in parse_qs(u.query).items()}


def test_providers_endpoint(client, settings):
    assert client.get("/api/auth/providers").json["data"] == {"github": True, "google": True}
    settings.GOOGLE_OAUTH_CLIENT_ID = None
    settings.GOOGLE_OAUTH_CLIENT_SECRET = None
    assert client.get("/api/auth/providers").json["data"] == {"github": True, "google": False}


def test_start_redirects_with_state_pkce_and_cookie(client):
    r, q = start(client, "github", next="/ideas")
    assert r.location.startswith("https://github.com/login/oauth/authorize?")
    assert q["client_id"] == ["gh-client"]
    assert q["redirect_uri"] == ["http://localhost:5001/api/auth/oauth/github/callback"]
    assert q["code_challenge_method"] == ["S256"] and len(q["code_challenge"][0]) == 43
    assert len(q["state"][0]) >= 32
    cookie = r.headers["Set-Cookie"]
    assert "dc_oauth=" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Path=/api/auth/oauth" in cookie
    assert "gh-secret" not in r.location


@respx.mock
def test_github_sign_up_creates_verified_user_and_session(client):
    mock_github()
    r = finish(client)
    origin, path, q = landing(r)
    assert (origin, path) == (FRONT, "/auth/callback")
    assert q == {"next": "/harnesses/new", "provider": "github", "new": "1"}
    assert "dc_refresh=" in r.headers.get("Set-Cookie", "") or client.get_cookie("dc_refresh", path="/api/auth")
    user = db.session.execute(select(User).where(User.email == "ada@example.com")).scalar_one()
    assert user.email_verified_at is not None and user.password_hash is None
    assert user.username == "octo-ada" and user.github_username == "octo-ada"
    # The PKCE verifier was sent to GitHub.
    sent = respx.calls[0].request.content.decode()
    assert "code_verifier=" in sent and "client_secret=gh-secret" in sent
    # The frontend's silent refresh now works with the cookie that was set.
    me = client.post("/api/auth/refresh", headers=CSRF_HEADERS)
    assert me.status_code == 200 and me.json["data"]["user"]["has_password"] is False


@respx.mock
def test_second_sign_in_matches_by_provider_id_not_email(client):
    mock_github()
    finish(client)
    respx.reset()
    mock_github(email="new-address@example.com")
    r = finish(client)
    assert landing(r)[2].get("new") is None
    assert len(humans()) == 1


@respx.mock
def test_google_links_to_existing_verified_account(client):
    user = make_user("grace", email="grace@example.com")
    mock_google()
    r = finish(client, "google")
    assert landing(r)[1] == "/auth/callback"
    acct = db.session.execute(select(OAuthAccount)).scalar_one()
    assert acct.user_id == user.id and acct.provider == "google"
    db.session.refresh(user)
    assert user.password_hash is not None  # verified account keeps its password


@respx.mock
def test_unverified_account_is_claimed_and_its_password_removed(client):
    squatter = make_user("squat", email="grace@example.com", verified=False)
    old = auth_header(squatter)
    mock_google()
    r = finish(client, "google")
    assert landing(r)[2].get("password_removed") == "1"
    db.session.refresh(squatter)
    assert squatter.password_hash is None and squatter.email_verified_at is not None
    assert client.get("/api/users/me", headers=old).status_code == 401  # old sessions signed out


@respx.mock
def test_unverified_provider_email_is_refused(client):
    mock_github(verified=False)
    r = finish(client)
    assert landing(r)[1:] == ("/sign-in", {"oauth_error": "email_not_verified", "provider": "github"})
    assert humans() == []


@respx.mock
def test_bad_code_and_cancel_and_state_mismatch(client):
    mock_github(token_ok=False)
    assert landing(finish(client))[2]["oauth_error"] == "provider_error"
    assert landing(finish(client, error="access_denied"))[2]["oauth_error"] == "cancelled"
    assert landing(finish(client, state="forged"))[2]["oauth_error"] == "state_mismatch"
    client.delete_cookie("dc_oauth", path="/api/auth/oauth")
    r = client.get("/api/auth/oauth/github/callback", query_string={"code": "x", "state": "y"})
    assert landing(r)[2]["oauth_error"] == "state_expired"


@respx.mock
def test_suspended_user_cannot_sign_in(client):
    make_user("sus", email="ada@example.com", status="suspended")
    mock_github()
    assert landing(finish(client))[2]["oauth_error"] == "account_suspended"


def test_open_redirects_are_blocked(client):
    for bad in ("//evil.example", "https://evil.example", "/\\evil.example"):
        r, _ = start(client, next=bad, return_to="https://evil.example")
        from app.auth.oauth import _serializer

        raw = client.get_cookie("dc_oauth", path="/api/auth/oauth").value
        state = _serializer("oauth-state").loads(raw)
        assert state["n"] == "/" and state["r"] == FRONT


def test_dev_allows_other_localhost_port(client, settings):
    settings.APP_ENV = "development"
    start(client, return_to="http://localhost:5174")
    from app.auth.oauth import _serializer

    state = _serializer("oauth-state").loads(client.get_cookie("dc_oauth", path="/api/auth/oauth").value)
    assert state["r"] == "http://localhost:5174"


def test_unconfigured_provider_goes_back_with_error(client, settings):
    settings.GITHUB_OAUTH_CLIENT_ID = None
    settings.GITHUB_OAUTH_CLIENT_SECRET = None
    r = client.get("/api/auth/oauth/github/start")
    assert landing(r)[2]["oauth_error"] == "provider_not_configured"
    assert client.get("/api/auth/oauth/gitlab/start").status_code == 404


@respx.mock
def test_link_from_settings_then_unlink(client):
    user = make_user("lin", email="lin@example.com")
    h = auth_header(user)
    token = client.post("/api/auth/oauth/github/link", headers=h).json["data"]["link_token"]
    mock_github(gh_id=55, login="lin-gh", email="other@example.com")
    _, q = start(client, link=token)
    r = client.get("/api/auth/oauth/github/callback", query_string={"code": "c", "state": q["state"][0]})
    assert landing(r)[1:] == ("/settings/account", {"linked": "github"})
    conns = client.get("/api/auth/connections", headers=h).json["data"]
    assert conns["has_password"] is True and [a["provider"] for a in conns["accounts"]] == ["github"]
    assert client.delete("/api/auth/connections/github", headers=h).status_code == 204
    assert client.get("/api/auth/connections", headers=h).json["data"]["accounts"] == []


@respx.mock
def test_cannot_link_identity_owned_by_someone_else(client):
    mock_github(gh_id=9)
    finish(client)  # creates the owner of GitHub id 9
    other = make_user("oth")
    token = client.post("/api/auth/oauth/github/link", headers=auth_header(other)).json["data"]["link_token"]
    _, q = start(client, link=token)
    r = client.get("/api/auth/oauth/github/callback", query_string={"code": "c", "state": q["state"][0]})
    assert landing(r)[2]["oauth_error"] == "already_linked_elsewhere"


@respx.mock
def test_last_sign_in_method_cannot_be_unlinked(client):
    mock_github()
    finish(client)
    (user,) = humans()
    r = client.delete("/api/auth/connections/github", headers=auth_header(user))
    assert r.status_code == 409 and r.json["error"]["code"] == "last_sign_in_method"


@respx.mock
def test_passwordless_account_needs_recent_sign_in(client):
    mock_github()
    finish(client)
    (user,) = humans()
    h = auth_header(user)
    # Fresh session: can set a first password without a current one.
    r = client.post("/api/users/me/password", json={"new_password": "a brand new passphrase"}, headers=h)
    assert r.status_code == 200, r.json
    db.session.refresh(user)
    assert user.password_hash is not None
    # Password accounts still need the current password.
    r = client.post("/api/users/me/password", json={"new_password": "yet another passphrase"}, headers=h)
    assert r.status_code == 400


@respx.mock
def test_passwordless_delete_requires_recent_session(client):
    mock_github()
    finish(client)
    (user,) = humans()
    h = auth_header(user)
    db.session.execute(update(AuthSession).values(created_at=datetime.now(UTC) - timedelta(hours=2)))
    db.session.commit()
    r = client.delete("/api/users/me", json={}, headers=h)
    assert r.status_code == 403 and r.json["error"]["code"] == "reauth_required"
    db.session.execute(update(AuthSession).values(created_at=datetime.now(UTC)))
    db.session.commit()
    assert client.delete("/api/users/me", json={}, headers=h).status_code == 204
    assert db.session.execute(select(OAuthAccount)).first() is None


def test_password_login_unchanged(client):
    make_user("pw", email="pw@example.com")
    r = client.post("/api/auth/login", json={"email": "pw@example.com", "password": PASSWORD})
    assert r.status_code == 200 and r.json["data"]["user"]["has_password"] is True


def test_username_suggestions(app):
    from app.auth.oauth import Identity, suggest_username

    make_user("taken-name")
    ident = lambda **k: Identity("github", "1", None, False, k.get("login"), k.get("name"), None)  # noqa: E731
    assert suggest_username(ident(login="Taken-Name")) == "taken-name-2"
    assert suggest_username(ident(login="a")) == "a-dev"
    assert suggest_username(ident(login="admin")) == "admin-2"
    assert suggest_username(Identity("google", "1", "j.doe+x@example.com", True, None, None, None)) == "j-doe-x"
