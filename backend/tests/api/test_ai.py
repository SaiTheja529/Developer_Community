import json

from sqlalchemy import func, select

from app.common.url_safety import LinkCheckResult
from app.extensions import db
from app.modules.ai.client import AIError
from app.modules.ai.models import AIMessage, AIUsage
from app.modules.suggestions.models import Suggestion
from tests.conftest import auth_header, harness_body, make_user, resource_body


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = [ln for ln in block.splitlines() if not ln.startswith(":")]
        if not lines:
            continue
        name = lines[0].split(": ", 1)[1]
        data = json.loads(lines[1].split(": ", 1)[1])
        events.append((name, data))
    return events


def test_chat_sse_event_order_and_persistence(client, ai):
    u = make_user("ada")
    h = auth_header(u)
    ai.stream_chunks = ["Here are ", "three ways."]
    r = client.post("/api/ai/chat", json={"message": "How do I write hooks?"}, headers=h)
    assert r.status_code == 200 and r.mimetype == "text/event-stream"
    events = parse_sse(r.get_data(as_text=True))
    assert [e[0] for e in events] == ["meta", "delta", "delta", "done"]
    meta, done = events[0][1], events[-1][1]
    assert done["status"] == "complete" and done["conversation_title"] == "Sample conversation title"
    conv = client.get(f"/api/ai/conversations/{meta['conversation_id']}", headers=h).json["data"]
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["messages"][1]["content"] == "Here are three ways." and conv["message_count"] == 2
    features = sorted(db.session.execute(select(AIUsage.feature)).scalars())
    assert features == ["chat", "chat_title"]

    # Second message reuses history; regenerate replaces the last assistant message.
    client.post(
        "/api/ai/chat", json={"conversation_id": meta["conversation_id"], "message": "More?"}, headers=h
    ).get_data()
    assert ai.calls[-1]["messages"][-1]["content"] == "More?" and len(ai.calls[-1]["messages"]) == 3
    r = client.post(f"/api/ai/conversations/{meta['conversation_id']}/regenerate", headers=h)
    assert [e[0] for e in parse_sse(r.get_data(as_text=True))][-1] == "done"
    conv = client.get(f"/api/ai/conversations/{meta['conversation_id']}", headers=h).json["data"]
    assert len(conv["messages"]) == 4 and conv["message_count"] == 4

    other = auth_header(make_user("bob"))
    assert client.get(f"/api/ai/conversations/{meta['conversation_id']}", headers=other).status_code == 404
    assert client.get("/api/ai/conversations", headers=h).json["meta"]["total"] == 1


def test_chat_with_context_and_github_down(client, ai, github):
    u = make_user("ada")
    github.add("ada", "spec-first-harness")
    hid = client.post("/api/harnesses", json=harness_body(), headers=auth_header(u)).json["data"]["id"]
    github.down = True
    r = client.post(
        "/api/ai/chat", json={"message": "Improve hooks?", "context": {"type": "harness", "id": hid}},
        headers=auth_header(u),
    )
    meta = parse_sse(r.get_data(as_text=True))[0][1]
    labels = {s["label"]: s["status"] for s in meta["context_sources"]}
    assert labels["Harness: Spec-First Claude Harness (submitted fields)"] == "included"
    assert labels["Repository content"] == "failed"
    assert "<platform_content" in ai.calls[0]["instructions"]


def test_chat_cancel_saves_partial(client, ai):
    u = make_user("ada")
    ai.stream_chunks = ["partial ", "answer ", "never sent"]
    ai.delay_seconds = 0.2
    r = client.post("/api/ai/chat", json={"message": "Long question"}, headers=auth_header(u), buffered=False)
    it = iter(r.response)
    chunks = [next(it), next(it)]  # meta + first delta
    assert b"event: meta" in chunks[0] and b"partial" in chunks[1]
    r.close()  # client pressed Stop
    msg = db.session.execute(select(AIMessage).where(AIMessage.role == "assistant")).scalar_one()
    db.session.refresh(msg)
    assert msg.status == "cancelled" and msg.content.startswith("partial")
    assert db.session.execute(select(AIUsage.outcome)).scalar_one() == "cancelled"


def test_chat_upstream_timeout_emits_error_event(client, ai):
    u = make_user("ada")
    ai.fail_stream = AIError("upstream_timeout", "slow")
    events = parse_sse(client.post("/api/ai/chat", json={"message": "Hi"}, headers=auth_header(u)).get_data(as_text=True))
    assert events[-1][0] == "error" and events[-1][1]["code"] == "upstream_timeout"
    assert db.session.execute(select(AIMessage.status).where(AIMessage.role == "assistant")).scalar_one() == "error"


def test_quota_disabled_and_budget(client, settings):
    u = make_user("ada")
    h = auth_header(u)
    db.session.add(AIUsage(user_id=u.id, feature="chat", model="fake-model", input_tokens=150_000, output_tokens=60_000,
                           outcome="success"))
    db.session.commit()
    r = client.post("/api/ai/chat", json={"message": "Hi"}, headers=h)
    assert r.status_code == 429 and r.json["error"]["code"] == "ai_quota_exceeded"
    assert r.json["error"]["details"]["resets_at"].endswith("Z")
    # Moderators get a 5x multiplier.
    mod = make_user("mod", role="moderator")
    db.session.add(AIUsage(user_id=mod.id, feature="chat", model="fake-model", input_tokens=210_000, outcome="success"))
    db.session.commit()
    assert client.post("/api/ai/chat", json={"message": "Hi"}, headers=auth_header(mod)).status_code == 200

    settings.AI_ENABLED = False
    r = client.post("/api/ai/chat", json={"message": "Hi"}, headers=h)
    assert r.status_code == 503 and r.json["error"]["details"]["reason"] == "disabled"
    assert client.get("/api/ai/status").json["data"] == {"enabled": False, "model_label": "GPT-6", "reason": "disabled"}
    settings.AI_ENABLED = True
    settings.AI_MONTHLY_BUDGET_USD = 0.0
    r = client.post("/api/ai/refine", json={"text": "x", "action": "clarity", "field": "f"}, headers=h)
    assert r.status_code == 503 and r.json["error"]["details"]["reason"] == "budget_exhausted"


def test_unverified_users_cannot_use_ai(client):
    u = make_user("ada", verified=False)
    r = client.post("/api/ai/chat", json={"message": "Hi"}, headers=auth_header(u))
    assert r.status_code == 403 and r.json["error"]["code"] == "email_not_verified"


def test_harness_draft_prefill_and_publish(client, ai, github):
    u = make_user("ada")
    h = auth_header(u)
    github.add("ada", "spec-first-harness")
    ai.structured["HarnessDocDraft"] = {
        "name": "Spec-First Harness",
        "short_description": "A harness that writes a spec before code is generated by the agent.",
        "problem_addressed": "Agents start coding without a plan.",
        "detailed_explanation": "It uses a subagent and a hook. " * 5,
        "architecture": "Subagent + hook",
        "components": [{"type": "subagent", "name": "spec-writer", "description": "Writes SPEC.md",
                        "evidence_path": ".claude/agents/spec.md"}],
        "setup_instructions": "1. Clone",
        "limitations": "TS only",
        "suggested_tools": ["claude_code", "made_up_tool"],
        "suggested_category": "not-a-category",
        "suggested_tags": ["Spec Driven", "bad/tag"],
        "gaps_and_uncertainties": ["No tests found"],
    }
    r = client.post("/api/ai/generate/harness", json={"repo_url": "https://github.com/ada/spec-first-harness"}, headers=h)
    assert r.status_code == 201, r.json
    draft = r.json["data"]
    assert draft["output"]["suggested_tools"] == ["claude_code"]
    assert draft["output"]["suggested_category"] == "other" and draft["output"]["suggested_tags"] == ["spec-driven"]
    assert {s["label"] for s in draft["context_sources"]} >= {"README.md", "CLAUDE.md"}
    prefill = draft["prefill"]
    assert prefill["detailed_explanation"].startswith("## Problem")

    # Publish via the normal create endpoint with source_draft_id.
    body = {k: v for k, v in prefill.items() if v is not None}
    body["source_draft_id"] = draft["id"]
    created = client.post("/api/harnesses", json=body, headers=h)
    assert created.status_code == 201, created.json
    assert created.json["data"]["ai_assisted"] is True
    d = client.get(f"/api/ai/drafts/{draft['id']}", headers=h).json["data"]
    assert d["status"] == "published" and d["published_target"]["id"] == created.json["data"]["id"]
    other = make_user("bob")
    assert client.get(f"/api/ai/drafts/{draft['id']}", headers=auth_header(other)).status_code == 404


def test_harness_generation_repo_unavailable(client, github):
    u = make_user("ada")
    r = client.post("/api/ai/generate/harness", json={"repo_url": "https://github.com/ada/missing"}, headers=auth_header(u))
    assert r.status_code == 422 and r.json["error"]["code"] == "repo_unavailable"


def test_resource_recommendations_drop_unreachable(client, ai, links):
    u = make_user("ada")
    hub = client.post("/api/resources", json=resource_body(), headers=auth_header(u)).json["data"]
    from app.modules.resources.models import Resource

    db.session.execute(Resource.__table__.update().values(link_status="ok"))
    db.session.commit()
    links.results["https://dead.example/x"] = LinkCheckResult("broken", http_status=404)
    ai.structured["ResourceRecommendations"] = {
        "learning_path_notes": "Start with the tutorial.",
        "recommendations": [
            {"name": "Hub", "url": None, "hub_resource_id": hub["id"], "description": "d", "resource_type": "official_docs",
             "category": "python", "level": "beginner"},
            {"name": "Official", "url": "https://docs.python.org/3/library/", "hub_resource_id": None, "description": "d",
             "resource_type": "official_docs", "category": "python", "level": "beginner"},
            {"name": "Blog", "url": "https://someblog.example/p", "hub_resource_id": None, "description": "d",
             "resource_type": "article", "category": "python", "level": "beginner"},
            {"name": "Dead", "url": "https://dead.example/x", "hub_resource_id": None, "description": "d",
             "resource_type": "article", "category": "python", "level": "beginner"},
        ],
    }
    r = client.post("/api/ai/generate/resources", json={"topic": "python tutorial"}, headers=auth_header(u))
    assert r.status_code == 201, r.json
    out = r.json["data"]["output"]
    statuses = [(x["name"], x["verification"]["status"]) for x in out["recommendations"]]
    assert statuses == [("Python tutorial", "verified_hub"), ("Official", "verified_official_domain"),
                        ("Blog", "reachable_unverified")]
    assert out["omitted"] == [{"name": "Dead", "url": "https://dead.example/x", "reason": "broken"}]
    assert [x["order"] for x in out["recommendations"]] == [1, 2, 3]


def test_feedback_suggestions_never_posted(client, ai, github):
    owner, u = make_user("ada"), make_user("bob")
    github.add("ada", "spec-first-harness")
    hid = client.post("/api/harnesses", json=harness_body(), headers=auth_header(owner)).json["data"]["id"]
    r = client.post("/api/ai/feedback-suggestions", json={"target_type": "harness", "target_id": hid}, headers=auth_header(u))
    assert r.status_code == 201
    assert r.json["data"]["output"]["label"] == "AI-generated suggestions, not a community review"
    assert db.session.execute(select(func.count()).select_from(Suggestion)).scalar_one() == 0


def test_idea_generation_and_draft_operations(client, ai):
    u = make_user("ada")
    h = auth_header(u)
    assert client.post("/api/ai/generate/project-idea", json={"count": 1}, headers=h).status_code == 400
    r = client.post("/api/ai/generate/project-idea", json={"domain": "devtools", "count": 2}, headers=h)
    assert r.status_code == 201
    draft = r.json["data"]
    assert len(draft["prefill"]) == 2 and "## Target users" in draft["prefill"][0]["description"]
    did = draft["id"]

    output = draft["output"]
    output["ideas"][0]["title"] = "Edited title"
    r = client.patch(f"/api/ai/drafts/{did}", json={"output": output}, headers=h)
    assert r.json["data"]["revision"] == 2 and r.json["data"]["history_count"] == 1
    assert client.patch(f"/api/ai/drafts/{did}", json={"output": {"ideas": "nope"}}, headers=h).status_code == 400

    ai.structured["SectionOutput"] = {"value": "Shorter architecture."}
    r = client.post(f"/api/ai/drafts/{did}/refine-section", json={"field": "ideas.0.architecture",
                                                                  "instruction": "Make it shorter"}, headers=h)
    assert r.json["data"]["output"]["ideas"][0]["architecture"] == "Shorter architecture."
    assert r.json["data"]["output"]["ideas"][0]["title"] == "Edited title"
    assert client.post(f"/api/ai/drafts/{did}/refine-section", json={"field": "ideas.0.milestones",
                                                                     "instruction": "x"}, headers=h).status_code == 400

    r = client.post(f"/api/ai/drafts/{did}/restore", json={"history_index": 0}, headers=h)
    assert r.json["data"]["output"]["ideas"][0]["architecture"] != "Shorter architecture."
    assert client.post(f"/api/ai/drafts/{did}/regenerate", json={}, headers=h).status_code == 200
    assert client.post(f"/api/ai/drafts/{did}/discard", headers=h).json["data"]["status"] == "discarded"
    assert client.get("/api/ai/drafts?status=discarded", headers=h).json["meta"]["total"] == 1


def test_refine_and_refusal_and_retry(client, ai):
    u = make_user("ada")
    h = auth_header(u)
    assert client.post("/api/ai/refine", json={"text": "x", "action": "custom", "field": "f"}, headers=h).status_code == 400
    ai.structured["RefineOutput"] = {"text": "Clearer text.", "change_summary": "Fixed grammar."}
    r = client.post("/api/ai/refine", json={"text": "unclear txt", "action": "clarity", "field": "idea.description"},
                    headers=h)
    assert r.json["data"] == {"text": "Clearer text.", "change_summary": "Fixed grammar."}

    ai.structured["RefineOutput"] = {"__refusal__": "I can't help with that."}
    r = client.post("/api/ai/refine", json={"text": "x", "action": "rewrite", "field": "f"}, headers=h)
    assert r.status_code == 422 and r.json["error"]["code"] == "ai_refused"

    ai.structured["RefineOutput"] = [AIError("invalid_output", "bad json"), {"text": "ok", "change_summary": "ok"}]
    r = client.post("/api/ai/refine", json={"text": "x", "action": "rewrite", "field": "f"}, headers=h)
    assert r.status_code == 200 and r.json["data"]["text"] == "ok"

    usage = client.get("/api/ai/usage", headers=h).json["data"]
    assert usage["today"]["generations"] == 2 and usage["today"]["limit_generations"] == 30
    assert "cost_usd" not in usage["daily"][0]


def test_stream_survives_detached_session(app, ai):
    """Regression: under Gunicorn the request session is gone before the SSE generator runs.

    The Flask test client shares one session across the request, so simulate a real server by
    removing the session between prepare() and streaming.
    """
    from flask import g

    from app.modules.ai import chat_service
    from app.modules.ai.schemas import ChatRequest

    u = make_user("ada")
    with app.test_request_context("/api/ai/chat", method="POST"):
        g.current_user = u
        g.request_id = "req_test"
        prepared = chat_service.prepare(u, ChatRequest(message="Hello"))
        db.session.remove()  # what Flask-SQLAlchemy teardown does on a real server
        events = [name for name, _ in chat_service.ChatRun(prepared).events()]
    assert events[-1] == "done"
    msg = db.session.get(AIMessage, prepared.assistant_message_id)
    assert msg.status == "complete" and msg.content


def test_cleanup_marks_abandoned_streams(client):
    from datetime import UTC, datetime, timedelta

    from app.modules.ai.models import AIConversation

    u = make_user("ada")
    conv = AIConversation(user_id=u.id)
    db.session.add(conv)
    db.session.flush()
    db.session.add(AIMessage(conversation_id=conv.id, role="assistant", content="", status="streaming",
                             created_at=datetime.now(UTC) - timedelta(minutes=30)))
    db.session.commit()
    r = client.post("/api/internal/jobs/cleanup", headers={"X-Job-Secret": "job-secret-job-secret-job-secret"})
    assert r.json["data"]["result"]["stale_streams"] == 1
    assert db.session.execute(select(AIMessage.status)).scalar_one() == "error"
