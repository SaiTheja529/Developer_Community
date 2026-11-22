from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.extensions import db
from app.modules.harnesses.models import Harness
from app.modules.reports.models import ModerationAction
from tests.conftest import auth_header, harness_body, make_user, resource_body, walk_keys


def _harness(client, github, user):
    github.add("ada", "spec-first-harness")
    return client.post("/api/harnesses", json=harness_body(), headers=auth_header(user)).json["data"]


def test_hidden_content_visible_only_to_owner_and_mods(client, github):
    owner, other, mod = make_user("ada"), make_user("bob"), make_user("mod", role="moderator")
    h = _harness(client, github, owner)
    r = client.post(
        "/api/admin/moderate",
        json={"target_type": "harness", "target_id": h["id"], "action": "hide", "reason": "spam"},
        headers=auth_header(mod),
    )
    assert r.status_code == 200 and r.json["data"]["status"] == "hidden"
    assert client.get("/api/harnesses").json["meta"]["total"] == 0
    assert client.get(f"/api/harnesses/{h['id']}").status_code == 404
    assert client.get(f"/api/harnesses/{h['id']}", headers=auth_header(other)).status_code == 404
    mine = client.get(f"/api/harnesses/{h['id']}", headers=auth_header(owner)).json["data"]
    assert mine["status"] == "hidden"
    contrib = client.get("/api/users/ada/contributions?type=harnesses", headers=auth_header(owner)).json["data"]
    assert contrib[0]["status"] == "hidden"
    assert client.get("/api/users/ada/contributions?type=harnesses").json["meta"]["total"] == 0
    assert client.get(f"/api/harnesses/{h['id']}", headers=auth_header(mod)).status_code == 200

    client.post(
        "/api/admin/moderate",
        json={"target_type": "harness", "target_id": h["id"], "action": "restore"},
        headers=auth_header(mod),
    )
    client.post(
        "/api/admin/moderate",
        json={"target_type": "harness", "target_id": h["id"], "action": "feature"},
        headers=auth_header(mod),
    )
    assert client.get("/api/harnesses?featured=true").json["meta"]["total"] == 1
    actions = [a.action for a in db.session.execute(select(ModerationAction)).scalars()]
    assert sorted(actions) == ["feature", "hide", "restore"]  # every moderator action is audited
    log = client.get("/api/admin/moderation-log", headers=auth_header(mod)).json
    assert log["meta"]["total"] == 3
    notifications = client.get("/api/notifications", headers=auth_header(owner)).json["data"]
    assert {n["type"] for n in notifications} == {"content_moderated"}


def test_regular_users_cannot_moderate(client, github):
    owner = make_user("ada")
    h = _harness(client, github, owner)
    r = client.post(
        "/api/admin/moderate",
        json={"target_type": "harness", "target_id": h["id"], "action": "hide"},
        headers=auth_header(owner),
    )
    assert r.status_code == 403
    assert client.get("/api/admin/reports", headers=auth_header(owner)).status_code == 403
    mod = make_user("mod", role="moderator")
    assert client.get("/api/admin/users", headers=auth_header(mod)).status_code == 403


def test_reports_auto_hide_and_resolution(client, github):
    owner, mod = make_user("ada"), make_user("mod", role="moderator")
    h = _harness(client, github, owner)
    reporters = [make_user(f"rep{i}") for i in range(3)]
    body = {"target_type": "harness", "target_id": h["id"], "reason": "spam", "details": "Looks like spam"}
    r = client.post("/api/reports", json=body, headers=auth_header(reporters[0]))
    assert r.status_code == 201
    assert client.post("/api/reports", json=body, headers=auth_header(reporters[0])).status_code == 409
    client.post("/api/reports", json=body, headers=auth_header(reporters[1]))
    assert client.get(f"/api/harnesses/{h['id']}").status_code == 200
    client.post("/api/reports", json=body, headers=auth_header(reporters[2]))
    assert client.get(f"/api/harnesses/{h['id']}").status_code == 404  # auto-hidden
    action = db.session.execute(select(ModerationAction)).scalar_one()
    assert action.reason == "auto_hide"

    queue = client.get("/api/admin/reports", headers=auth_header(mod)).json
    assert queue["meta"]["total"] == 3
    assert queue["data"][0]["target_preview"]["title"] == "Spec-First Claude Harness"
    rid = queue["data"][0]["id"]
    r = client.patch(f"/api/admin/reports/{rid}", json={"status": "dismissed", "resolution_note": "ok"}, headers=auth_header(mod))
    assert r.json["data"]["status"] == "dismissed"
    assert client.patch(f"/api/admin/reports/{rid}", json={"status": "resolved"}, headers=auth_header(mod)).status_code == 409


def test_broken_link_report_increments_count(client):
    u, rep = make_user("ada"), make_user("bob")
    res = client.post("/api/resources", json=resource_body(), headers=auth_header(u)).json["data"]
    client.post(
        "/api/reports", json={"target_type": "resource", "target_id": res["id"], "reason": "broken_link"},
        headers=auth_header(rep),
    )
    assert client.get(f"/api/resources/{res['id']}").json["data"]["link"]["open_reports"] == 1


def test_ai_reports_require_ownership(client):
    a, b = make_user("ada"), make_user("bob")
    r = client.post("/api/ai/chat", json={"message": "Hello there"}, headers=auth_header(a))
    msg_id = next(line for line in r.get_data(as_text=True).splitlines() if line.startswith("data:"))
    import json

    meta = json.loads(msg_id[5:])
    body = {"target_type": "ai_message", "target_id": meta["assistant_message_id"], "reason": "inaccurate_ai"}
    assert client.post("/api/reports", json=body, headers=auth_header(b)).status_code == 404
    assert client.post("/api/reports", json=body, headers=auth_header(a)).status_code == 201
    mod = make_user("mod", role="moderator")
    preview = client.get("/api/admin/reports", headers=auth_header(mod)).json["data"][0]["target_preview"]
    assert "content" in preview


def test_admin_suspend_revokes_sessions_and_role_change(client):
    admin, u = make_user("boss", role="admin"), make_user("ada")
    uh = auth_header(u)
    r = client.patch(
        f"/api/admin/users/{u.id}", json={"status": "suspended", "reason": "abuse"}, headers=auth_header(admin)
    )
    assert r.status_code == 200 and r.json["data"]["status"] == "suspended"
    assert client.get("/api/users/me", headers=uh).status_code in (401, 403)
    r = client.patch(f"/api/admin/users/{u.id}", json={"role": "moderator", "reason": "trusted"}, headers=auth_header(admin))
    assert r.json["data"]["role"] == "moderator"
    assert client.patch(f"/api/admin/users/{admin.id}", json={"role": "user", "reason": "x"}, headers=auth_header(admin)).status_code == 400
    listed = client.get("/api/admin/users?status=suspended", headers=auth_header(admin)).json
    assert listed["meta"]["total"] == 1
    assert {a.action for a in db.session.execute(select(ModerationAction)).scalars()} == {"suspend_user", "set_role"}


def test_trusted_domains_and_official_flag(client):
    admin, mod, u = make_user("boss", role="admin"), make_user("mod", role="moderator"), make_user("ada")
    r = client.post("/api/admin/trusted-domains", json={"domain": "docs.example.org", "kind": "official_docs"},
                    headers=auth_header(admin))
    assert r.status_code == 201
    domain_id = r.json["data"]["id"]
    res = client.post(
        "/api/resources", json=resource_body(url="https://docs.example.org/guide"), headers=auth_header(u)
    ).json["data"]
    assert res["official_verified"] is True
    r = client.post(f"/api/admin/resources/{res['id']}/official", json={"official_verified": False}, headers=auth_header(mod))
    assert r.json["data"]["official_verified"] is False
    assert client.delete(f"/api/admin/trusted-domains/{domain_id}", headers=auth_header(admin)).status_code == 204
    assert client.delete(f"/api/admin/trusted-domains/{domain_id}", headers=auth_header(admin)).status_code == 404
    stats = client.get("/api/admin/stats", headers=auth_header(admin)).json["data"]
    assert stats["counts"]["resources"] == 1 and "cost_month_to_date_usd" in stats["ai"]


def test_jobs_require_secret_and_run(client, links, github):
    assert client.post("/api/internal/jobs/link-check").status_code == 401
    assert client.post("/api/internal/jobs/link-check", headers={"X-Job-Secret": "wrong"}).status_code == 401
    h = {"X-Job-Secret": "job-secret-job-secret-job-secret"}
    u = make_user("ada")
    client.post("/api/resources", json=resource_body(), headers=auth_header(u))
    r = client.post("/api/internal/jobs/link-check", headers=h)
    assert r.status_code == 200 and r.json["data"]["result"]["checked"] == 1
    assert client.get("/api/resources").json["data"][0]["link"]["status"] == "ok"

    github.add("ada", "spec-first-harness")
    client.post("/api/harnesses", json=harness_body(), headers=auth_header(u))
    github.add("ada", "spec-first-harness", archived=True, stars=99)
    r = client.post("/api/internal/jobs/refresh-repos", headers=h)
    assert r.json["data"]["result"] == {"refreshed": 1, "flagged": 1}

    # Cleanup hard-deletes rows soft-deleted > 90 days ago.
    hid = db.session.execute(select(Harness.id)).scalar_one()
    db.session.execute(Harness.__table__.update().values(deleted_at=datetime.now(UTC) - timedelta(days=91)))
    db.session.commit()
    r = client.post("/api/internal/jobs/cleanup", headers=h)
    assert r.status_code == 200 and r.json["data"]["result"]["harnesses"] == 1
    assert db.session.get(Harness, hid) is None
    assert client.post("/api/internal/jobs/rebuild-counters", headers=h).status_code == 200


def test_meta_endpoints(client, github):
    assert client.get("/api/health").json == {"data": {"status": "ok"}}
    assert client.get("/api/health/ready").status_code == 200
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json["error"]["code"] == "not_found" and r.json["error"]["request_id"]
    assert r.headers["X-Request-ID"] == r.json["error"]["request_id"]
    assert client.get("/api/health", headers={"X-Request-ID": "req_custom"}).headers["X-Request-ID"] == "req_custom"
    cfg = client.get("/api/meta/config").json["data"]
    assert "agent-orchestration" in [c["slug"] for c in cfg["categories"]["harness"]]
    assert cfg["enums"]["tools"][0] == "claude_code" and cfg["ai"]["enabled"] is True
    assert cfg["limits"]["harness"]["short_description"]["max"] == 280

    u = make_user("ada")
    _harness(client, github, u)
    tags = client.get("/api/tags?module=harness&q=spe").json["data"]
    assert tags == [{"tag": "spec-driven", "count": 1}]
    home = client.get("/api/home").json["data"]
    assert home["counts"]["harnesses"] == 1 and len(home["harnesses"]["recent"]) == 1
    search = client.get("/api/search?q=spec").json["data"]
    assert len(search["harnesses"]) == 1 and search["ideas"] == []
    big = client.post("/api/auth/login", data="x" * (300 * 1024), content_type="application/json")
    assert big.status_code == 413 and big.json["error"]["code"] == "payload_too_large"
    assert client.get("/api/health").headers["X-Content-Type-Options"] == "nosniff"


def test_public_responses_never_leak_email(client, github):
    owner, other = make_user("ada"), make_user("bob")
    h = _harness(client, github, owner)
    client.post(f"/api/harnesses/{h['id']}/comments", json={"body": "Hi"}, headers=auth_header(other))
    client.post(f"/api/harnesses/{h['id']}/reviews", json={"what_tested": "Tested on a real project."},
                headers=auth_header(other))
    urls = [
        "/api/harnesses",
        f"/api/harnesses/{h['id']}",
        f"/api/harnesses/{h['id']}/comments",
        f"/api/harnesses/{h['id']}/reviews",
        "/api/users/ada",
        "/api/users/ada/contributions?type=harnesses",
        "/api/home",
        "/api/search?q=spec",
    ]
    for url in urls:
        for headers in ({}, auth_header(other)):
            body = client.get(url, headers=headers).json
            keys = set(walk_keys(body))
            assert "email" not in keys and "password_hash" not in keys, url
    assert db.session.execute(select(func.count()).select_from(Harness)).scalar_one() == 1
