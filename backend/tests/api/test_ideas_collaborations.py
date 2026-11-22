from tests.conftest import auth_header, idea_body, make_user


def _idea(client, user, **over):
    r = client.post("/api/ideas", json=idea_body(**over), headers=auth_header(user))
    assert r.status_code == 201, r.json
    return r.json["data"]


def test_idea_crud_and_interest(client):
    owner, other = make_user("ada"), make_user("bob")
    idea = _idea(client, owner)
    assert idea["tech_stack"] == ["python", "fastapi"]
    assert idea["collaboration"] == {"status": "seeking_collaborators", "collaborator_count": 0, "viewer_request": None,
                                     "pending_requests": 0}
    iid = idea["id"]
    r = client.put(f"/api/votes/idea/{iid}?kind=interest", headers=auth_header(other))
    assert r.json["data"] == {"count": 1, "active": True, "kind": "interest"}
    detail = client.get(f"/api/ideas/{iid}", headers=auth_header(other)).json["data"]
    assert detail["counts"]["interest"] == 1 and detail["viewer"]["has_interest"] is True
    assert detail["viewer"]["has_voted"] is False
    assert client.patch(f"/api/ideas/{iid}", json={"title": "Hijacked title"}, headers=auth_header(other)).status_code == 403
    r = client.patch(f"/api/ideas/{iid}", json={"collaboration_status": "team_formed"}, headers=auth_header(owner))
    assert r.json["data"]["collaboration_status"] == "team_formed"
    lst = client.get("/api/ideas?sort=most_interest&collaboration_status=team_formed").json
    assert lst["meta"]["total"] == 1
    assert client.get("/api/ideas?tech=fastapi").json["meta"]["total"] == 1
    assert client.get("/api/ideas?sort=most_reviewed").status_code == 400


def test_collaboration_accept_reveals_contact_only_when_opted_in(client):
    owner, req = make_user("ada"), make_user("bob")
    client.patch(
        "/api/users/me",
        json={"contact_links": [{"label": "LinkedIn", "url": "https://linkedin.com/in/bob"}],
              "contact_visibility": "collaborators"},
        headers=auth_header(req),
    )
    idea = _idea(client, owner)
    url = f"/api/ideas/{idea['id']}/collaboration-requests"
    body = {"message": "I have built three FastAPI services and want to help.", "skills": ["FastAPI"], "share_contact": True}
    assert client.post(url, json=body, headers=auth_header(owner)).status_code == 403
    r = client.post(url, json=body, headers=auth_header(req))
    assert r.status_code == 201
    cr = r.json["data"]
    assert cr["status"] == "pending" and cr["counterpart_contact"] is None
    assert client.post(url, json=body, headers=auth_header(req)).status_code == 409  # one pending per user

    viewer_req = client.get(f"/api/ideas/{idea['id']}", headers=auth_header(req)).json["data"]["collaboration"]
    assert viewer_req["viewer_request"] == {"id": cr["id"], "status": "pending"}
    inbox = client.get("/api/collaborations?role=received", headers=auth_header(owner)).json["data"]
    assert inbox[0]["id"] == cr["id"]
    assert client.get(url, headers=auth_header(req)).status_code == 403  # only the owner lists requests
    assert client.get(url, headers=auth_header(owner)).json["meta"]["total"] == 1

    assert client.post(f"/api/collaborations/{cr['id']}/accept", json={}, headers=auth_header(req)).status_code == 403
    r = client.post(
        f"/api/collaborations/{cr['id']}/accept", json={"message": "Welcome aboard!", "share_contact": False},
        headers=auth_header(owner),
    )
    assert r.status_code == 200
    owner_view = r.json["data"]
    # Requester opted in => owner sees requester's email + non-hidden links.
    assert owner_view["counterpart_contact"] == {
        "email": "bob@example.com", "links": [{"label": "LinkedIn", "url": "https://linkedin.com/in/bob"}]
    }
    # Owner did not opt in => requester sees nothing.
    req_view = client.get(f"/api/collaborations/{cr['id']}", headers=auth_header(req)).json["data"]
    assert req_view["status"] == "accepted" and req_view["counterpart_contact"] is None
    assert client.get(f"/api/ideas/{idea['id']}").json["data"]["counts"]["collaborators"] == 1
    # Third parties cannot see the request.
    assert client.get(f"/api/collaborations/{cr['id']}", headers=auth_header(make_user("eve"))).status_code == 404


def test_declined_and_withdrawn_reveal_nothing(client):
    owner, a, b = make_user("ada"), make_user("bob"), make_user("cat")
    idea = _idea(client, owner)
    url = f"/api/ideas/{idea['id']}/collaboration-requests"
    body = {"message": "Happy to help with the backend and tests.", "share_contact": True}
    ra = client.post(url, json=body, headers=auth_header(a)).json["data"]
    rb = client.post(url, json=body, headers=auth_header(b)).json["data"]
    declined = client.post(f"/api/collaborations/{ra['id']}/decline", json={"message": "Sorry"}, headers=auth_header(owner))
    assert declined.json["data"]["status"] == "declined" and declined.json["data"]["counterpart_contact"] is None
    assert client.post(f"/api/collaborations/{rb['id']}/withdraw", headers=auth_header(owner)).status_code == 403
    w = client.post(f"/api/collaborations/{rb['id']}/withdraw", headers=auth_header(b)).json["data"]
    assert w["status"] == "withdrawn" and w["counterpart_contact"] is None
    assert client.post(f"/api/collaborations/{rb['id']}/accept", json={}, headers=auth_header(owner)).status_code == 409


def test_requests_only_when_seeking_and_withdrawn_on_delete(client):
    owner, a = make_user("ada"), make_user("bob")
    sharing = _idea(client, owner, collaboration_status="sharing")
    r = client.post(
        f"/api/ideas/{sharing['id']}/collaboration-requests",
        json={"message": "Could I join this project please?"},
        headers=auth_header(a),
    )
    assert r.status_code == 409
    idea = _idea(client, owner)
    cr = client.post(
        f"/api/ideas/{idea['id']}/collaboration-requests",
        json={"message": "Could I join this project please?"},
        headers=auth_header(a),
    ).json["data"]
    assert client.delete(f"/api/ideas/{idea['id']}", headers=auth_header(owner)).status_code == 204
    assert client.get(f"/api/collaborations/{cr['id']}", headers=auth_header(a)).json["data"]["status"] == "withdrawn"


def test_idea_suggestions_tech_stack_payload(client):
    owner, a = make_user("ada"), make_user("bob")
    idea = _idea(client, owner)
    r = client.post(
        f"/api/ideas/{idea['id']}/suggestions",
        json={"kind": "tech_stack", "title": "Use pgvector", "body": "pgvector makes semantic search easy.",
              "payload": {"technologies": ["PgVector", "fastapi"]}},
        headers=auth_header(a),
    )
    assert r.status_code == 201 and r.json["data"]["payload"] == {"technologies": ["pgvector", "fastapi"]}
    bad = client.post(
        f"/api/ideas/{idea['id']}/suggestions",
        json={"kind": "tech_stack", "title": "Use pgvector", "body": "pgvector makes semantic search easy.",
              "payload": {"oops": 1}},
        headers=auth_header(a),
    )
    assert bad.status_code == 400
