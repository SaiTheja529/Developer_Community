from datetime import UTC, datetime, timedelta

from app.common.url_safety import LinkCheckResult
from app.extensions import db
from app.modules.resources.models import Resource
from tests.conftest import auth_header, make_user, resource_body


def _resource(client, user, **over):
    r = client.post("/api/resources", json=resource_body(**over), headers=auth_header(user))
    assert r.status_code == 201, r.json
    return r.json["data"]


def test_create_official_flag_and_duplicates(client):
    u, v = make_user("ada"), make_user("bob")
    r = _resource(client, u)
    assert r["official_verified"] is True and r["domain"] == "docs.python.org"
    assert r["link"]["status"] == "pending"
    unofficial = _resource(client, u, url="https://someblog.example/python-tips", resource_type="official_docs")
    assert unofficial["official_verified"] is False
    dup = client.post(
        "/api/resources",
        json=resource_body(url="https://www.docs.python.org/3/tutorial?utm_source=x#intro"),
        headers=auth_header(v),
    )
    assert dup.status_code == 409 and dup.json["error"]["details"]["existing_id"] == r["id"]
    check = client.get("/api/resources/check-url?url=https://docs.python.org/3/tutorial/", headers=auth_header(v)).json["data"]
    assert check["duplicate"]["id"] == r["id"] and check["valid"] is True and check["official_domain"] is True


def test_url_blocked_and_invalid(client):
    u = make_user("ada")
    for url in ("http://127.0.0.1/admin", "http://169.254.169.254/latest", "http://localhost:8080/"):
        r = client.post("/api/resources", json=resource_body(url=url), headers=auth_header(u))
        assert r.status_code == 422 and r.json["error"]["code"] == "url_blocked", url
    r = client.post("/api/resources", json=resource_body(url="javascript:alert(1)"), headers=auth_header(u))
    assert r.status_code == 400


def test_recheck_two_failures_and_listing_rules(client, links):
    u = make_user("ada")
    r = _resource(client, u)
    rid = r["id"]
    links.results["https://docs.python.org/3/tutorial/"] = LinkCheckResult("broken", http_status=404)

    # The recheck is limited per resource, so drive the second check through the service directly.
    res = client.post(f"/api/resources/{rid}/recheck", headers=auth_header(u)).json["data"]
    assert res["link"]["status"] == "pending"  # first failure keeps the previous status
    from app.modules.resources.service import run_link_check

    row = db.session.get(Resource, rid)
    assert run_link_check(row) is True
    db.session.commit()
    assert client.get(f"/api/resources/{rid}").json["data"]["link"]["status"] == "broken"

    # Broken for over 7 days => hidden from listings unless include_broken=true.
    db.session.execute(
        Resource.__table__.update().values(link_broken_since=datetime.now(UTC) - timedelta(days=8))
    )
    db.session.commit()
    assert client.get("/api/resources").json["meta"]["total"] == 0
    assert client.get("/api/resources?include_broken=true").json["meta"]["total"] == 1

    from sqlalchemy import select

    from app.modules.notifications.models import Notification

    n = db.session.execute(select(Notification)).scalar_one()
    assert n.type == "resource_link_broken"


def test_recheck_rate_limit_and_permissions(client, app, links, github, ai):
    from app import create_app
    from tests.conftest import make_settings

    owner, other = make_user("ada"), make_user("bob")
    rid = _resource(client, owner)["id"]
    assert client.post(f"/api/resources/{rid}/recheck", headers=auth_header(other)).status_code == 403

    limited = create_app(make_settings(RATELIMIT_ENABLED=True))
    limited.extensions.update(link_checker=links, github_client=github, ai_client=ai)
    lc = limited.test_client()
    with limited.app_context():
        h = auth_header(db.session.merge(owner))
        assert lc.post(f"/api/resources/{rid}/recheck", headers=h).status_code == 200
        r = lc.post(f"/api/resources/{rid}/recheck", headers=h)
        assert r.status_code == 429 and r.json["error"]["code"] == "rate_limited" and "Retry-After" in r.headers
        db.session.remove()


def test_resource_filters(client):
    u = make_user("ada")
    _resource(client, u)
    _resource(client, u, name="React docs", url="https://react.dev/learn", category="javascript-typescript",
              resource_type="guide", level="intermediate", tags=["react"])
    assert client.get("/api/resources?official=true").json["meta"]["total"] == 2
    assert client.get("/api/resources?domain=react.dev").json["meta"]["total"] == 1
    assert client.get("/api/resources?level=beginner").json["meta"]["total"] == 1
    assert client.get("/api/resources?resource_type=guide").json["meta"]["total"] == 1
    assert client.get("/api/resources?q=react").json["meta"]["total"] == 1


def test_collections_items_order_and_visibility(client):
    u, other = make_user("ada"), make_user("bob")
    r1 = _resource(client, u)
    r2 = _resource(client, u, name="React docs", url="https://react.dev/learn")
    r3 = _resource(client, u, name="MDN", url="https://developer.mozilla.org/en-US/")
    c = client.post(
        "/api/collections",
        json={"title": "Learn web", "category": "web", "items": [{"resource_id": r1["id"], "note": "Start here"}]},
        headers=auth_header(u),
    ).json["data"]
    cid = c["id"]
    assert c["counts"]["items"] == 1 and c["items"][0]["note"] == "Start here"
    h = auth_header(u)
    assert client.post(f"/api/collections/{cid}/items", json={"resource_id": r2["id"]}, headers=h).status_code == 201
    assert client.post(f"/api/collections/{cid}/items", json={"resource_id": r2["id"]}, headers=h).status_code == 409
    client.post(f"/api/collections/{cid}/items", json={"resource_id": r3["id"], "position": 0}, headers=h)
    order = [i["resource_id"] for i in client.get(f"/api/collections/{cid}").json["data"]["items"]]
    assert order == [r3["id"], r1["id"], r2["id"]]
    bad = client.put(f"/api/collections/{cid}/items/order", json={"resource_ids": [r1["id"], r2["id"]]}, headers=h)
    assert bad.status_code == 400
    ok = client.put(f"/api/collections/{cid}/items/order", json={"resource_ids": [r2["id"], r1["id"], r3["id"]]}, headers=h)
    assert [i["resource_id"] for i in ok.json["data"]["items"]] == [r2["id"], r1["id"], r3["id"]]
    assert client.delete(f"/api/collections/{cid}/items/{r1['id']}", headers=h).status_code == 204
    items = client.get(f"/api/collections/{cid}").json["data"]["items"]
    assert [i["position"] for i in items] == [0, 1]
    assert client.post(f"/api/collections/{cid}/items", json={"resource_id": r1["id"]}, headers=auth_header(other)).status_code == 403

    # Deleted resources stay as unavailable items.
    client.delete(f"/api/resources/{r3['id']}", headers=h)
    items = client.get(f"/api/collections/{cid}").json["data"]["items"]
    gone = next(i for i in items if i["resource_id"] == r3["id"])
    assert gone["unavailable"] is True and gone["resource"] is None

    mine = client.get(f"/api/users/me/collections?resource_id={r2['id']}", headers=h).json["data"]
    assert mine[0]["contains_resource"] is True
    preview = client.get(f"/api/resources/{r2['id']}").json["data"]["collections_preview"]
    assert preview[0]["id"] == cid

    # Private collections are owner-only.
    client.patch(f"/api/collections/{cid}", json={"visibility": "private"}, headers=h)
    assert client.get(f"/api/collections/{cid}").status_code == 404
    assert client.get(f"/api/collections/{cid}", headers=auth_header(other)).status_code == 404
    assert client.get(f"/api/collections/{cid}", headers=h).status_code == 200
    assert client.get("/api/collections").json["meta"]["total"] == 0
