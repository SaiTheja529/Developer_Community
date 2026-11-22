import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.auth.models import AuthSession
from app.extensions import db
from app.modules.users.models import User
from tests.conftest import CSRF_HEADERS, PASSWORD, auth_header, harness_body, make_user


def _register(client, email="ada@example.com", username="ada", password=PASSWORD):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "username": username, "display_name": "Ada L."},
    )


def _token_from(outbox, kind="verify-email"):
    body = outbox[-1]["text"]
    return re.search(rf"/{kind}\?token=([A-Za-z0-9_\-]+)", body).group(1)


def _refresh(client):
    return client.post("/api/auth/refresh", headers=CSRF_HEADERS)


def test_full_flow_register_verify_login_refresh_logout(client, outbox):
    r = _register(client)
    assert r.status_code == 201, r.json
    data = r.json["data"]
    assert data["token_type"] == "Bearer" and data["expires_in"] == 900
    assert data["user"]["email_verified"] is False
    assert "dc_refresh=" in r.headers["Set-Cookie"] and "HttpOnly" in r.headers["Set-Cookie"]
    assert "Path=/api/auth" in r.headers["Set-Cookie"] and "SameSite=Strict" in r.headers["Set-Cookie"]
    access = {"Authorization": f"Bearer {data['access_token']}"}

    # Unverified users can read their profile but cannot write content.
    assert client.get("/api/users/me", headers=access).status_code == 200
    r = client.post("/api/harnesses", json=harness_body(), headers=access)
    assert r.status_code == 403 and r.json["error"]["code"] == "email_not_verified"

    token = _token_from(outbox)
    r = client.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    # Single use.
    assert client.post("/api/auth/verify-email", json={"token": token}).json["error"]["code"] == "invalid_token"

    r = client.post("/api/auth/login", json={"email": "ADA@example.com", "password": PASSWORD})
    assert r.status_code == 200
    assert r.json["data"]["user"]["email_verified"] is True

    r = _refresh(client)
    assert r.status_code == 200, r.json
    new_access = r.json["data"]["access_token"]
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {new_access}"}).status_code == 200

    assert client.post("/api/auth/logout", headers=CSRF_HEADERS).status_code == 204
    r = client.get("/api/users/me", headers={"Authorization": f"Bearer {new_access}"})
    assert r.status_code == 401 and r.json["error"]["code"] == "session_revoked"
    # Idempotent logout.
    assert client.post("/api/auth/logout", headers=CSRF_HEADERS).status_code == 204


def test_register_errors(client):
    assert _register(client).status_code == 201
    r = _register(client, username="other")
    assert r.status_code == 409 and r.json["error"]["code"] == "email_taken"
    r = _register(client, email="b@example.com")
    assert r.status_code == 409 and r.json["error"]["code"] == "username_taken"
    r = _register(client, email="c@example.com", username="admin")
    assert r.status_code == 400 and "username" in r.json["error"]["details"]["fields"]
    r = _register(client, email="d@example.com", username="dee", password="qwertyuiop")
    assert r.status_code == 400 and "password" in r.json["error"]["details"]["fields"]
    r = client.post("/api/auth/register", json={"email": "x@example.com", "unknown": 1})
    assert r.status_code == 400 and r.json["error"]["code"] == "validation_error"


def test_login_identical_for_unknown_email_and_wrong_password(client):
    make_user("bob")
    a = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"})
    b = client.post("/api/auth/login", json={"email": "bob@example.com", "password": "wrong-password-1"})
    assert a.status_code == b.status_code == 401
    assert a.json["error"]["code"] == b.json["error"]["code"] == "invalid_credentials"
    assert a.json["error"]["message"] == b.json["error"]["message"]


def test_lockout_after_five_failures(client):
    make_user("carol")
    codes = [
        client.post("/api/auth/login", json={"email": "carol@example.com", "password": "nope-nope-1"}).status_code
        for _ in range(5)
    ]
    assert codes[:4] == [401] * 4 and codes[4] == 429
    r = client.post("/api/auth/login", json={"email": "carol@example.com", "password": PASSWORD})
    assert r.status_code == 429 and r.json["error"]["code"] == "too_many_attempts" and "Retry-After" in r.headers


def test_suspended_user_cannot_login(client):
    make_user("sus", status="suspended")
    r = client.post("/api/auth/login", json={"email": "sus@example.com", "password": PASSWORD})
    assert r.status_code == 403 and r.json["error"]["code"] == "account_suspended"


def test_refresh_requires_csrf_headers(client):
    _register(client)
    assert client.post("/api/auth/refresh").status_code == 403
    assert client.post("/api/auth/refresh", headers={"Origin": "https://evil.example", "X-Requested-With": "devcommons"}).status_code == 403
    assert client.post("/api/auth/refresh", headers={"Origin": CSRF_HEADERS["Origin"]}).status_code == 403
    assert _refresh(client).status_code == 200


def test_refresh_without_cookie(client):
    r = _refresh(client)
    assert r.status_code == 401 and r.json["error"]["code"] == "unauthenticated"


def test_refresh_reuse_detection_and_race(client, outbox):
    r = _register(client)
    old_cookie = client.get_cookie("dc_refresh", path="/api/auth").value

    assert _refresh(client).status_code == 200
    # Replaying the old token within 10 s is treated as a benign race.
    client.set_cookie("dc_refresh", old_cookie, path="/api/auth")
    r = _refresh(client)
    assert r.status_code == 409 and r.json["error"]["code"] == "refresh_conflict"

    # Pretend the rotation happened long ago: replaying the old token is now reuse => revoke.
    db.session.execute(update(AuthSession).values(rotated_at=datetime.now(UTC) - timedelta(minutes=5)))
    db.session.commit()
    client.set_cookie("dc_refresh", old_cookie, path="/api/auth")
    r = _refresh(client)
    assert r.status_code == 401 and r.json["error"]["code"] == "session_revoked"
    sess = db.session.execute(select(AuthSession)).scalar_one()
    assert sess.revoked_reason == "reuse_detected"
    assert any("Security alert" in m["subject"] for m in outbox)


def test_concurrent_refresh_retry_succeeds(client):
    _register(client)
    old_cookie = client.get_cookie("dc_refresh", path="/api/auth").value
    first = _refresh(client)
    new_cookie = client.get_cookie("dc_refresh", path="/api/auth").value
    assert first.status_code == 200
    # A second tab still sends the old cookie => 409; its retry carries the new cookie => 200.
    client.set_cookie("dc_refresh", old_cookie, path="/api/auth")
    assert _refresh(client).status_code == 409
    client.set_cookie("dc_refresh", new_cookie, path="/api/auth")
    assert _refresh(client).status_code == 200


def test_password_reset_revokes_all_sessions(client, outbox):
    user = make_user("dave")
    h1, h2 = auth_header(user), auth_header(user)
    r = client.post("/api/auth/forgot-password", json={"email": "dave@example.com"})
    assert r.status_code == 202
    unknown = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert unknown.status_code == 202 and unknown.json == r.json
    token = _token_from(outbox, "reset-password")
    new_password = "a brand new passphrase"
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": new_password}).status_code == 204
    for h in (h1, h2):
        assert client.get("/api/users/me", headers=h).json["error"]["code"] == "session_revoked"
    assert client.post("/api/auth/login", json={"email": "dave@example.com", "password": new_password}).status_code == 200


def test_change_password_keeps_current_session_only(client):
    user = make_user("erin")
    current, other = auth_header(user), auth_header(user)
    r = client.post(
        "/api/users/me/password",
        json={"current_password": PASSWORD, "new_password": "another long passphrase"},
        headers=current,
    )
    assert r.status_code == 200 and r.json["data"]["access_token"]
    assert client.get("/api/users/me", headers=current).status_code == 200
    assert client.get("/api/users/me", headers=other).status_code == 401


def test_sessions_list_and_revoke_and_logout_all(client):
    user = make_user("fay")
    h1, h2 = auth_header(user), auth_header(user)
    sessions = client.get("/api/auth/sessions", headers=h1).json["data"]
    assert len(sessions) == 2 and sum(s["is_current"] for s in sessions) == 1
    other = next(s for s in sessions if not s["is_current"])
    assert client.delete(f"/api/auth/sessions/{other['id']}", headers=h1).status_code == 204
    assert client.get("/api/users/me", headers=h2).status_code == 401
    assert client.post("/api/auth/logout-all", headers=h1).status_code == 204
    assert client.get("/api/users/me", headers=h1).status_code == 401


def test_change_email_flow(client, outbox):
    user = make_user("gus")
    h = auth_header(user)
    r = client.post("/api/users/me/email", json={"new_email": "gus2@example.com", "password": PASSWORD}, headers=h)
    assert r.status_code == 202
    assert {m["to"] for m in outbox[-2:]} == {"gus2@example.com", "gus@example.com"}
    confirm = next(m for m in outbox if m["to"] == "gus2@example.com")
    token = re.search(r"token=([A-Za-z0-9_\-]+)", confirm["text"]).group(1)
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert client.get("/api/users/me", headers=h).json["data"]["email"] == "gus2@example.com"


def test_delete_account_anonymizes(client):
    user = make_user("hal")
    h = auth_header(user)
    assert client.delete("/api/users/me", json={"password": "wrong"}, headers=h).status_code == 400
    assert client.delete("/api/users/me", json={"password": PASSWORD}, headers=h).status_code == 204
    row = db.session.get(User, user.id)
    assert row.status == "deleted" and row.email is None and row.display_name == "Deleted user"
    assert client.get("/api/users/hal").status_code == 404
    # Email is freed for a new registration.
    assert _register(client, email="hal@example.com", username="hal2").status_code == 201


def test_tokens_rejected_when_tampered_or_expired(client, settings):
    import jwt

    user = make_user("ivy")
    h = auth_header(user)
    token = h["Authorization"].split()[1]
    bad = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    claims = jwt.decode(token, options={"verify_signature": False})
    claims["exp"] = int((datetime.now(UTC) - timedelta(minutes=5)).timestamp())
    expired = jwt.encode(claims, settings.signing_key("test"), algorithm="HS256", headers={"kid": "test"})
    r = client.get("/api/users/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json["error"]["code"] == "token_expired"
    none_alg = jwt.encode(claims, None, algorithm="none", headers={"kid": "test"}) if hasattr(jwt, "encode") else ""
    assert client.get("/api/users/me", headers={"Authorization": f"Bearer {none_alg}"}).status_code == 401


def test_profile_update_and_username_check(client):
    user = make_user("joe")
    h = auth_header(user)
    r = client.patch(
        "/api/users/me",
        json={"bio": "Hi", "skills": ["Python", "LangGraph"], "contact_links": [{"label": "Site", "url": "https://jo.dev"}],
              "contact_visibility": "public"},
        headers=h,
    )
    assert r.status_code == 200 and r.json["data"]["skills"] == ["python", "langgraph"]
    public = client.get("/api/users/joe").json["data"]
    assert public["contact_links"][0]["url"] == "https://jo.dev"
    assert "email" not in public
    assert client.get("/api/users/check-username?username=joe").json["data"] == {"available": False, "reason": "taken"}
    assert client.get("/api/users/check-username?username=admin").json["data"]["reason"] == "reserved"
    assert client.get("/api/users/check-username?username=x!").json["data"]["reason"] == "invalid"
    assert client.get("/api/users/check-username?username=freebie").json["data"] == {"available": True}
