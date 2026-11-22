from sqlalchemy import select

from app.common.counters import rebuild_all
from app.extensions import db
from app.modules.harnesses.models import Harness
from app.modules.notifications.models import Notification
from tests.conftest import auth_header, harness_body, make_user


def _create(client, github, user, **over):
    github.add("ada", "spec-first-harness")
    r = client.post("/api/harnesses", json=harness_body(**over), headers=auth_header(user))
    assert r.status_code == 201, r.json
    return r.json["data"]


def test_create_and_detail(client, github):
    owner = make_user("ada")
    h = _create(client, github, owner)
    assert h["slug"] == "spec-first-claude-harness"
    assert h["tags"] == ["spec-driven", "hooks"]
    assert h["repo"]["url"] == "https://github.com/ada/spec-first-harness"
    assert h["repo"]["stars"] == 10 and h["repo"]["license"] == "MIT"
    assert h["viewer"]["is_owner"] is True and h["viewer"]["can_edit"] is True
    assert h["category"] == {"slug": "agent-orchestration", "name": "Agent orchestration"}
    anon = client.get(f"/api/harnesses/{h['id']}").json["data"]
    assert anon["viewer"] == {
        "is_owner": False, "has_voted": False, "has_interest": False,
        "has_bookmarked": False, "can_edit": False, "can_moderate": False,
    }
    assert anon["rating_summary"]["count"] == 0


def test_duplicate_repo_returns_409(client, github):
    a, b = make_user("ada"), make_user("bob")
    h = _create(client, github, a)
    r = client.post(
        "/api/harnesses",
        json=harness_body(repo_url="https://github.com/ADA/spec-first-harness.git", name="Copy"),
        headers=auth_header(b),
    )
    assert r.status_code == 409
    assert r.json["error"]["code"] == "duplicate" and r.json["error"]["details"]["existing_id"] == h["id"]


def test_private_or_missing_repo_returns_422(client, github):
    u = make_user("ada")
    github.repos[("ada", "secret")] = "private"
    for repo in ("secret", "missing"):
        r = client.post(
            "/api/harnesses", json=harness_body(repo_url=f"https://github.com/ada/{repo}"), headers=auth_header(u)
        )
        assert r.status_code == 422 and r.json["error"]["code"] == "repo_unavailable"
    r = client.post("/api/harnesses", json=harness_body(repo_url="https://gitlab.com/a/b"), headers=auth_header(u))
    assert r.status_code == 400 and "repo_url" in r.json["error"]["details"]["fields"]


def test_validation_errors(client, github):
    u = make_user("ada")
    r = client.post(
        "/api/harnesses",
        json=harness_body(short_description="too short", tools=[], category="nope", extra_field=1),
        headers=auth_header(u),
    )
    assert r.status_code == 400
    fields = r.json["error"]["details"]["fields"]
    assert "short_description" in fields and "tools" in fields and "extra_field" in fields


def test_owner_only_edit_and_delete_permissions(client, github):
    owner, other, mod = make_user("ada"), make_user("bob"), make_user("mod", role="moderator")
    h = _create(client, github, owner)
    url = f"/api/harnesses/{h['id']}"
    assert client.patch(url, json={"name": "New name!"}, headers=auth_header(other)).status_code == 403
    assert client.patch(url, json={"name": "New name!"}, headers=auth_header(mod)).status_code == 403
    r = client.patch(url, json={"name": "Renamed Harness", "tags": ["x"]}, headers=auth_header(owner))
    assert r.status_code == 200 and r.json["data"]["slug"] == "renamed-harness"
    assert client.delete(url, headers=auth_header(other)).status_code == 403
    assert client.delete(url, headers=auth_header(mod)).status_code == 204
    assert client.get(url).status_code == 404
    # The repo can be listed again after a soft delete.
    assert client.post("/api/harnesses", json=harness_body(), headers=auth_header(other)).status_code == 201


def test_anonymous_and_unverified_cannot_write(client, github):
    unverified = make_user("unv", verified=False)
    github.add("ada", "spec-first-harness")
    assert client.post("/api/harnesses", json=harness_body()).status_code == 401
    r = client.post("/api/harnesses", json=harness_body(), headers=auth_header(unverified))
    assert r.json["error"]["code"] == "email_not_verified"


def test_list_filters_sorts_and_search(client, github):
    u = make_user("ada")
    github.add("ada", "one")
    github.add("ada", "two")
    a = client.post(
        "/api/harnesses",
        json=harness_body(repo_url="https://github.com/ada/one", name="Testing Harness", tags=["tdd"], tools=["cursor"],
                          category="testing"),
        headers=auth_header(u),
    ).json["data"]
    b = client.post(
        "/api/harnesses",
        json=harness_body(repo_url="https://github.com/ada/two", name="Orchestrator Harness", tags=["agents"]),
        headers=auth_header(u),
    ).json["data"]
    voter = make_user("vee")
    client.put(f"/api/votes/harness/{a['id']}", headers=auth_header(voter))

    ids = lambda r: [x["id"] for x in r.json["data"]]  # noqa: E731
    assert ids(client.get("/api/harnesses?sort=recent")) == [b["id"], a["id"]]
    assert ids(client.get("/api/harnesses?sort=popular"))[0] == a["id"]
    assert ids(client.get("/api/harnesses?sort=trending"))[0] == a["id"]
    assert ids(client.get("/api/harnesses?category=testing")) == [a["id"]]
    assert ids(client.get("/api/harnesses?tags=agents")) == [b["id"]]
    assert ids(client.get("/api/harnesses?tools=cursor,aider")) == [a["id"]]
    assert ids(client.get("/api/harnesses?q=orchestrator")) == [b["id"]]
    assert ids(client.get("/api/harnesses?q=tdd")) == [a["id"]]
    assert ids(client.get("/api/harnesses?author=ada&page_size=1")) == [b["id"]]
    r = client.get("/api/harnesses?page_size=1&page=2")
    assert r.json["meta"] == {"page": 2, "page_size": 1, "total": 2, "total_pages": 2}
    bad = client.get("/api/harnesses?sort=bogus")
    assert bad.status_code == 400 and bad.json["error"]["code"] == "bad_request"
    assert client.get("/api/harnesses?page_size=51").status_code == 400


def test_votes_bookmarks_and_counters(client, github):
    owner, v1, v2 = make_user("ada"), make_user("bob"), make_user("cat")
    h = _create(client, github, owner)
    url = f"/api/votes/harness/{h['id']}"
    assert client.put(url, headers=auth_header(owner)).status_code == 403  # own content
    assert client.put(url, headers=auth_header(v1)).json["data"] == {"count": 1, "active": True, "kind": "upvote"}
    assert client.put(url, headers=auth_header(v1)).json["data"]["count"] == 1  # idempotent
    assert client.put(url, headers=auth_header(v2)).json["data"]["count"] == 2
    assert client.delete(url, headers=auth_header(v2)).json["data"] == {"count": 1, "active": False, "kind": "upvote"}
    assert client.delete(url, headers=auth_header(v2)).json["data"]["count"] == 1
    assert client.put(f"{url}?kind=interest", headers=auth_header(v1)).status_code == 400

    bm = f"/api/bookmarks/harness/{h['id']}"
    assert client.put(bm, headers=auth_header(v1)).json["data"] == {"count": 1, "active": True}
    assert client.put(bm, headers=auth_header(v1)).json["data"]["count"] == 1
    listed = client.get("/api/users/me/bookmarks", headers=auth_header(v1)).json["data"]
    assert listed[0]["item"]["id"] == h["id"] and listed[0]["bookmarked_at"]
    detail = client.get(f"/api/harnesses/{h['id']}", headers=auth_header(v1)).json["data"]
    assert detail["viewer"]["has_voted"] and detail["viewer"]["has_bookmarked"]

    # Comments, suggestions and reviews also maintain counters; rebuild must agree.
    hid = h["id"]
    c = client.post(f"/api/harnesses/{hid}/comments", json={"body": "Nice"}, headers=auth_header(v1)).json["data"]
    client.post(f"/api/harnesses/{hid}/comments", json={"body": "Reply", "parent_id": c["id"]}, headers=auth_header(v2))
    client.post(
        f"/api/harnesses/{hid}/suggestions",
        json={"kind": "improvement", "title": "Add tests", "body": "Please add a smoke test."},
        headers=auth_header(v1),
    )
    client.post(f"/api/harnesses/{hid}/reviews", json={"what_tested": "Ran it on a 20k LOC monorepo."}, headers=auth_header(v2))
    before = client.get(f"/api/harnesses/{hid}").json["data"]["counts"]
    assert before == {"votes": 1, "comments": 2, "suggestions": 1, "reviews": 1, "bookmarks": 1}
    db.session.execute(Harness.__table__.update().values(vote_count=99, comment_count=0, review_count=5))
    db.session.commit()
    rebuild_all()
    assert client.get(f"/api/harnesses/{hid}").json["data"]["counts"] == before


def test_reviews_rules_and_rating_summary(client, github):
    owner, a, b = make_user("ada"), make_user("bob"), make_user("cat")
    h = _create(client, github, owner)
    url = f"/api/harnesses/{h['id']}/reviews"
    body = {"what_tested": "Ran the spec-first flow end to end.", "ratings": {"overall": 4, "setup": 3}}
    assert client.post(url, json=body, headers=auth_header(owner)).status_code == 403
    r = client.post(url, json=body, headers=auth_header(a))
    assert r.status_code == 201 and r.json["data"]["disclaimer_key"] == "community_opinion"
    assert client.post(url, json=body, headers=auth_header(a)).status_code == 409
    client.post(url, json={**body, "ratings": {"overall": 5}}, headers=auth_header(b))
    summary = client.get(f"/api/harnesses/{h['id']}").json["data"]["rating_summary"]
    assert summary["count"] == 2 and summary["overall"] == 4.5 and summary["setup"] == 3.0
    assert summary["coordination"] is None and summary["counts"]["setup"] == 1
    rid = r.json["data"]["id"]
    assert client.patch(f"/api/reviews/{rid}", json={"environment": "macOS"}, headers=auth_header(b)).status_code == 403
    assert client.patch(f"/api/reviews/{rid}", json={"environment": "macOS"}, headers=auth_header(a)).status_code == 200
    assert client.delete(f"/api/reviews/{rid}", headers=auth_header(a)).status_code == 204
    assert client.get(url).json["meta"]["total"] == 1
    n = db.session.execute(select(Notification).where(Notification.type == "review_on_harness")).scalar_one()
    assert n.data["count"] == 2  # batched into one unread notification


def test_comments_threading_edit_delete(client, github):
    owner, a, b = make_user("ada"), make_user("bob"), make_user("cat")
    h = _create(client, github, owner)
    url = f"/api/harnesses/{h['id']}/comments"
    top = client.post(url, json={"body": "Top"}, headers=auth_header(a)).json["data"]
    reply = client.post(url, json={"body": "Reply", "parent_id": top["id"]}, headers=auth_header(b)).json["data"]
    nested = client.post(url, json={"body": "Nested", "parent_id": reply["id"]}, headers=auth_header(a)).json["data"]
    assert nested["parent_id"] == top["id"]  # replies to replies attach to the top-level parent
    listed = client.get(url).json["data"]
    assert len(listed) == 1 and listed[0]["reply_count"] == 2 and len(listed[0]["replies"]) == 2
    assert client.patch(f"/api/comments/{top['id']}", json={"body": "Edited"}, headers=auth_header(b)).status_code == 403
    edited = client.patch(f"/api/comments/{top['id']}", json={"body": "Edited"}, headers=auth_header(a)).json["data"]
    assert edited["edited_at"] is not None
    # Target owner may delete comments on their content; thread keeps a placeholder.
    assert client.delete(f"/api/comments/{top['id']}", headers=auth_header(owner)).status_code == 204
    listed = client.get(url).json["data"]
    assert listed[0]["deleted"] is True and listed[0]["body"] is None and listed[0]["author"] is None
    assert len(client.get(f"/api/comments/{top['id']}/replies").json["data"]) == 2
    types = {n.type for n in db.session.execute(select(Notification)).scalars()}
    assert {"comment_on_content", "reply_to_comment"} <= types


def test_suggestions_kinds_and_status(client, github):
    owner, a = make_user("ada"), make_user("bob")
    h = _create(client, github, owner)
    url = f"/api/harnesses/{h['id']}/suggestions"
    bad = client.post(url, json={"kind": "feature", "title": "Wrong kind", "body": "Not valid for harness"}, headers=auth_header(a))
    assert bad.status_code == 400
    s = client.post(
        url,
        json={"kind": "component_recommendation", "title": "Add an MCP server", "body": "Use a GitHub MCP server.",
              "payload": {"component_type": "mcp_server", "component_name": "github"}},
        headers=auth_header(a),
    ).json["data"]
    sid = s["id"]
    assert client.patch(f"/api/suggestions/{sid}", json={"status": "planned"}, headers=auth_header(a)).status_code == 403
    r = client.patch(f"/api/suggestions/{sid}", json={"status": "planned", "owner_response": "Good idea"}, headers=auth_header(owner))
    assert r.status_code == 200 and r.json["data"]["status"] == "planned"
    assert client.patch(f"/api/suggestions/{sid}", json={"title": "Changed"}, headers=auth_header(owner)).status_code == 403
    notif = db.session.execute(
        select(Notification).where(Notification.type == "suggestion_status_changed")
    ).scalar_one()
    assert notif.recipient_id.hex == a.id.hex and "#suggestion-" in notif.data["url_path"]
    assert client.get(f"{url}?status=planned").json["meta"]["total"] == 1
    assert client.get(f"{url}?kind=bogus").status_code == 400


def test_github_preview(client, github):
    u = make_user("ada")
    github.add("ada", "spec-first-harness")
    r = client.get("/api/github/repo-preview?url=https://github.com/ada/spec-first-harness", headers=auth_header(u))
    assert r.status_code == 200 and r.json["data"]["already_listed"] is None
    _create(client, github, u)
    r = client.get("/api/github/repo-preview?url=https://github.com/ada/spec-first-harness", headers=auth_header(u))
    assert r.json["data"]["already_listed"]["name"] == "Spec-First Claude Harness"
    r = client.get("/api/github/repo-preview?url=https://github.com/ada/nope", headers=auth_header(u))
    assert r.status_code == 422


def test_notifications_endpoints(client, github):
    owner, a = make_user("ada"), make_user("bob")
    h = _create(client, github, owner)
    client.post(f"/api/harnesses/{h['id']}/comments", json={"body": "Hello"}, headers=auth_header(a))
    oh = auth_header(owner)
    assert client.get("/api/notifications/unread-count", headers=oh).json["data"]["count"] == 1
    items = client.get("/api/notifications", headers=oh).json["data"]
    assert items[0]["type"] == "comment_on_content" and items[0]["data"]["actor_display_name"] == "Bob"
    assert client.post(f"/api/notifications/{items[0]['id']}/read", headers=oh).status_code == 200
    assert client.get("/api/notifications/unread-count", headers=oh).json["data"]["count"] == 0
    assert client.post(f"/api/notifications/{items[0]['id']}/read", headers=auth_header(a)).status_code == 404
    assert client.post("/api/notifications/read-all", headers=oh).status_code == 200
