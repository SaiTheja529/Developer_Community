"""AI generation tasks and drafts (spec §9.6, §9.7, §9.11)."""

from __future__ import annotations

import copy
import json
import logging
import time
from datetime import UTC, datetime

from flask import g
from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from app.common import enums
from app.common.content import load_target
from app.common.errors import ApiError, bad_request, not_found, pydantic_fields, validation_error
from app.common.text import try_normalize_tags, validate_http_url
from app.extensions import db
from app.extensions import settings as get_settings
from app.modules.ai import context_builder
from app.modules.ai.client import AIError, get_ai_client
from app.modules.ai.models import AIDraft
from app.modules.ai.prompt_loader import system_prompt
from app.modules.ai.schemas import (
    DRAFT_OUTPUT_SCHEMAS,
    FeedbackOutput,
    HarnessDocDraft,
    ProjectIdeaDrafts,
    RefineOutput,
    ResourceRecommendations,
    SectionOutput,
)
from app.modules.ai.usage import record_usage

log = logging.getLogger("devcommons.ai.generation")

HISTORY_MAX = 10
FEEDBACK_LABEL = "AI-generated suggestions, not a community review"


def _categories(module: str) -> list[str]:
    from app.modules.meta.models import Category

    return list(
        db.session.execute(
            select(Category.slug).where(Category.module == module, Category.is_active.is_(True)).order_by(Category.sort_order)
        ).scalars()
    )


def _map_ai_error(e: AIError) -> ApiError:
    if e.code == "upstream_timeout":
        return ApiError("upstream_timeout", "The AI service took too long. Try again.", 504)
    if e.code == "ai_unavailable":
        return ApiError("ai_unavailable", e.message or "The AI service is busy. Try again shortly.", 503)
    return ApiError("upstream_error", "The AI service returned an error. Try again.", 502)


def run_structured(feature: str, instructions: str, input_text: str, schema: type[BaseModel], post_validate=None):
    """Structured call with one retry on invalid output; usage recorded for every model call."""
    s = get_settings()
    client = get_ai_client()
    attempt_input = input_text
    for attempt in range(2):
        started = time.monotonic()
        model, i, o, c, outcome, err = s.ai_model, 0, 0, 0, "success", None
        try:
            res = client.generate_structured(
                instructions=instructions,
                input=attempt_input,
                schema=schema,
                max_output_tokens=s.AI_MAX_OUTPUT_TOKENS_GENERATION,
                request_id=g.get("request_id", ""),
            )
            model, i, o, c = res.model, res.input_tokens, res.output_tokens, res.cached_input_tokens
            if res.refusal:
                outcome, err = "error", "ai_refused"
                raise ApiError("ai_refused", res.refusal, 422, {"message": res.refusal})
            parsed = res.parsed
            if parsed is None:
                raise AIError("invalid_output", "No structured output returned.")
            if post_validate is not None:
                post_validate(parsed)
            return parsed
        except AIError as e:
            outcome = "timeout" if e.code == "upstream_timeout" else "error"
            err = e.code
            if e.code == "invalid_output" and attempt == 0:
                attempt_input = f"{input_text}\n\nYour previous answer was invalid: {e.message[:500]}. Return valid output."
                continue
            if e.code == "invalid_output":
                raise ApiError("upstream_error", "The AI returned an invalid answer. Try again.", 502) from e
            raise _map_ai_error(e) from e
        except ValueError as e:  # post_validate failure
            outcome, err = "error", "invalid_output"
            if attempt == 0:
                attempt_input = f"{input_text}\n\nYour previous answer was invalid: {str(e)[:500]}. Return valid output."
                continue
            raise ApiError("upstream_error", "The AI returned an invalid answer. Try again.", 502) from e
        finally:
            record_usage(
                user_id=g.current_user.id,
                feature=feature,
                model=model,
                input_tokens=i,
                cached_input_tokens=c,
                output_tokens=o,
                latency_ms=int((time.monotonic() - started) * 1000),
                outcome=outcome,
                error_code=err,
            )
    raise ApiError("upstream_error", "The AI returned an invalid answer. Try again.", 502)  # pragma: no cover


# Prefill mappings (draft output -> module create-form fields) ---------------------------------


def harness_prefill(out: dict, input_: dict) -> dict:
    explanation = out.get("detailed_explanation", "")
    if out.get("problem_addressed"):
        explanation = f"## Problem\n\n{out['problem_addressed']}\n\n{explanation}"
    return {
        "name": out.get("name", "")[:100],
        "repo_url": input_.get("repo_url"),
        "short_description": out.get("short_description", "")[:280],
        "detailed_explanation": explanation,
        "architecture": out.get("architecture"),
        "components": [
            {"type": c["type"], "name": c["name"][:100], "description": c.get("description")}
            for c in out.get("components", [])
        ][:50],
        "setup_instructions": out.get("setup_instructions"),
        "limitations": out.get("limitations"),
        "tools": out.get("suggested_tools", [])[:10],
        "category": out.get("suggested_category"),
        "tags": out.get("suggested_tags", [])[:8],
    }


def idea_prefill(idea: dict) -> dict:
    sections = [idea.get("summary", "")]
    if idea.get("target_users"):
        sections.append(f"## Target users\n\n{idea['target_users']}")
    if idea.get("architecture"):
        sections.append(f"## Architecture\n\n{idea['architecture']}")
    if idea.get("milestones"):
        sections.append("## Milestones\n\n" + "\n".join(f"{n}. {m}" for n, m in enumerate(idea["milestones"], 1)))
    if idea.get("challenges"):
        sections.append("## Challenges\n\n" + "\n".join(f"- {c}" for c in idea["challenges"]))
    return {
        "title": idea.get("title", "")[:120],
        "problem_statement": idea.get("problem_statement"),
        "proposed_solution": idea.get("proposed_solution"),
        "description": "\n\n".join(s for s in sections if s),
        "tech_stack": idea.get("tech_stack", [])[:20],
        "expected_features": idea.get("expected_features", [])[:30],
        "category": idea.get("suggested_category"),
        "tags": idea.get("suggested_tags", [])[:8],
    }


def draft_dict(d: AIDraft) -> dict:
    data = {
        "id": str(d.id),
        "task": d.task,
        "title": d.title,
        "input": d.input,
        "output": d.output,
        "context_sources": d.context_sources,
        "history_count": len(d.history or []),
        "revision": d.revision,
        "status": d.status,
        "published_target": (
            {"type": d.published_target_type, "id": str(d.published_target_id)} if d.published_target_id else None
        ),
        "model": d.model,
        "prompt_version": d.prompt_version,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }
    if d.task == "harness_doc":
        data["prefill"] = harness_prefill(d.output, d.input)
    elif d.task == "project_idea":
        data["prefill"] = [idea_prefill(i) for i in d.output.get("ideas", [])]
    elif d.task == "feedback_suggestions":
        data["label"] = FEEDBACK_LABEL
    return data


def draft_history(d: AIDraft) -> list:
    return d.history or []


# Task implementations ------------------------------------------------------------------------


def _harness_task(input_: dict) -> tuple[dict, list[dict], str, str]:
    from app.integrations.github import get_repo_snapshot, parse_repo_url

    try:
        ref = parse_repo_url(input_["repo_url"])
    except ValueError as e:
        raise validation_error({"repo_url": str(e)}) from e
    snapshot = get_repo_snapshot(ref.owner, ref.repo)
    if not snapshot.usable:
        raise ApiError(
            "repo_unavailable",
            "Couldn't read the repository. Try again later or fill the form manually.",
            422,
            {"reason": snapshot.status},
        )
    sections = context_builder.github_sections(snapshot)
    sources = [s.source for s in sections]
    fitted = context_builder._fit([s for s in sections if s.text])
    instructions, version = system_prompt(
        "harness_doc", TOOLS=", ".join(enums.TOOLS), CATEGORIES=", ".join(_categories("harness"))
    )
    notes = input_.get("additional_context")
    text = "\n\n".join(s.text for s in fitted)
    if notes:
        text += f"\n\n<platform_content source=\"author_notes\" id=\"input\">\n{notes}\n</platform_content>"
    parsed = run_structured("generate_harness", instructions, text, HarnessDocDraft)
    out = parsed.model_dump()
    cats = set(_categories("harness"))
    out["suggested_tools"] = [t for t in dict.fromkeys(out["suggested_tools"]) if t in enums.TOOLS]
    if out["suggested_category"] not in cats:
        out["suggested_category"] = "other" if "other" in cats else None
    out["suggested_tags"] = try_normalize_tags(out["suggested_tags"])
    out["short_description"] = out["short_description"][:280]
    return out, sources, version, out.get("name") or f"{ref.owner}/{ref.repo}"


def _idea_task(input_: dict) -> tuple[dict, list[dict], str, str]:
    count = input_.get("count", 1)
    instructions, version = system_prompt("project_idea", COUNT=count, CATEGORIES=", ".join(_categories("idea")))
    lines = []
    for key in ("domain", "problem", "interests"):
        if input_.get(key):
            lines.append(f"{key.capitalize()}: {input_[key]}")
    if input_.get("tech_preferences"):
        lines.append(f"Preferred technologies: {', '.join(input_['tech_preferences'])}")
    text = "<platform_content source=\"user_request\" id=\"input\">\n" + "\n".join(lines) + "\n</platform_content>"

    def post(parsed: ProjectIdeaDrafts):
        if not parsed.ideas:
            raise ValueError("Return at least one idea.")

    parsed = run_structured("generate_idea", instructions, text, ProjectIdeaDrafts, post)
    out = parsed.model_dump()
    out["ideas"] = out["ideas"][:count]
    cats = set(_categories("idea"))
    for idea in out["ideas"]:
        if idea["suggested_category"] not in cats:
            idea["suggested_category"] = "other"
        idea["suggested_tags"] = try_normalize_tags(idea["suggested_tags"])
        idea["tech_stack"] = try_normalize_tags(idea["tech_stack"], 20)
    title = out["ideas"][0]["title"] if len(out["ideas"]) == 1 else f"{len(out['ideas'])} project ideas"
    return out, [], version, title


def _hub_candidates(topic: str, goal: str | None):
    from app.common.listing import fts
    from app.modules.resources.models import Resource

    q = f"{topic} {goal or ''}".strip()
    clause, rank = fts(Resource, topic)
    stmt = (
        select(Resource)
        .where(
            Resource.deleted_at.is_(None),
            Resource.status == "published",
            Resource.link_status.in_(("ok", "redirected")),
        )
        .order_by(rank.desc(), Resource.vote_count.desc())
        .limit(15)
    )
    rows = db.session.execute(stmt.where(clause)).scalars().all()
    if goal and len(rows) < 15:
        clause2, _ = fts(Resource, q)
        extra = db.session.execute(stmt.where(clause2)).scalars().all()
        seen = {r.id for r in rows}
        rows += [r for r in extra if r.id not in seen][: 15 - len(rows)]
    return rows


def _resources_task(input_: dict) -> tuple[dict, list[dict], str, str]:
    from flask import current_app

    from app.common.url_safety import safe_check
    from app.modules.ai.verification import verify_urls
    from app.modules.meta.models import TrustedDomain

    hub = _hub_candidates(input_["topic"], input_.get("goal"))
    hub_by_id = {str(r.id): r for r in hub}
    hub_text = "\n".join(
        f'- id="{r.id}" name="{r.name}" url="{r.url}" type={r.resource_type} level={r.level or "n/a"}: '
        f"{r.description[:200]}"
        for r in hub
    )
    instructions, version = system_prompt(
        "resource_recommendations",
        RESOURCE_TYPES=", ".join(enums.RESOURCE_TYPES),
        CATEGORIES=", ".join(_categories("resource")),
    )
    request_text = f"Topic: {input_['topic']}"
    if input_.get("goal"):
        request_text += f"\nGoal: {input_['goal']}"
    if input_.get("level"):
        request_text += f"\nLevel: {input_['level']}"
    text = (
        f"<platform_content source=\"user_request\" id=\"input\">\n{request_text}\n</platform_content>\n\n"
        f"<hub_resources>\n{hub_text or '(no matching Knowledge Hub resources)'}\n</hub_resources>"
    )
    parsed = run_structured("generate_resources", instructions, text, ResourceRecommendations)

    checker = current_app.extensions.get("link_checker", safe_check)
    official = list(
        db.session.execute(select(TrustedDomain.domain).where(TrustedDomain.kind == "official_docs")).scalars()
    )
    now = datetime.now(UTC)
    external: list[str] = []
    for rec in parsed.recommendations:
        if not (rec.hub_resource_id and rec.hub_resource_id in hub_by_id) and rec.url:
            try:
                external.append(validate_http_url(rec.url))
            except ValueError:
                continue
    results = verify_urls(external, checker, official) if external else {}

    recs, omitted = [], []
    cats = set(_categories("resource"))
    for rec in parsed.recommendations:
        if rec.hub_resource_id and rec.hub_resource_id in hub_by_id:
            r = hub_by_id[rec.hub_resource_id]
            recs.append(
                {
                    "name": r.name,
                    "url": r.url,
                    "description": rec.description or r.description[:300],
                    "resource_type": r.resource_type,
                    "category": rec.category if rec.category in cats else None,
                    "level": r.level,
                    "source": "knowledge_hub",
                    "hub_resource_id": str(r.id),
                    "verification": {"status": "verified_hub", "checked_at": now},
                }
            )
            continue
        url = rec.url
        try:
            url = validate_http_url(url) if url else None
        except ValueError:
            url = None
        if not url:
            omitted.append({"name": rec.name, "url": rec.url, "reason": "invalid_url"})
            continue
        v = results.get(url)
        if v is None or not v.reachable:
            omitted.append({"name": rec.name, "url": url, "reason": v.status if v else "unreachable"})
            continue
        recs.append(
            {
                "name": rec.name,
                "url": url,
                "description": rec.description,
                "resource_type": rec.resource_type if rec.resource_type in enums.RESOURCE_TYPES else "other",
                "category": rec.category if rec.category in cats else None,
                "level": rec.level if rec.level in enums.RESOURCE_LEVELS else None,
                "source": "model",
                "hub_resource_id": None,
                "verification": {"status": v.status, "http_status": v.http_status, "checked_at": v.checked_at},
            }
        )
    for n, rec in enumerate(recs, 1):
        rec["order"] = n
    out = json.loads(
        json.dumps(
            {"learning_path_notes": parsed.learning_path_notes, "recommendations": recs, "omitted": omitted},
            default=lambda o: o.isoformat().replace("+00:00", "Z") if isinstance(o, datetime) else str(o),
        )
    )
    sources = [{"kind": "platform", "label": f"{len(hub)} Knowledge Hub resources", "status": "included"}]
    return out, sources, version, f"Learning path: {input_['topic']}"[:120]


def _feedback_task(input_: dict, user) -> tuple[dict, list[dict], str, str]:
    target = load_target(input_["target_type"], input_["target_id"], user)
    built = context_builder.build(input_["target_type"], target.id, user)
    instructions, version = system_prompt(
        "feedback_suggestions",
        TARGET_KIND="AI coding harness" if input_["target_type"] == "harness" else "project idea",
        CATEGORIES=", ".join(enums.AI_FEEDBACK_CATEGORIES),
    )
    parsed = run_structured("feedback_suggestions", instructions, built.text or "(no context)", FeedbackOutput)
    out = {"label": FEEDBACK_LABEL, "suggestions": parsed.model_dump()["suggestions"]}
    return out, built.sources, version, f"Feedback: {built.title or input_['target_type']}"[:120]


TASK_RUNNERS = {
    "harness_doc": lambda inp, user: _harness_task(inp),
    "project_idea": lambda inp, user: _idea_task(inp),
    "resource_recommendations": lambda inp, user: _resources_task(inp),
    "feedback_suggestions": _feedback_task,
}


def generate(task: str, input_: dict, user) -> AIDraft:
    out, sources, version, title = TASK_RUNNERS[task](input_, user)
    draft = AIDraft(
        user_id=user.id,
        task=task,
        title=title[:120] or task,
        input=input_,
        output=out,
        context_sources=sources,
        model=get_settings().ai_model,
        prompt_version=version,
    )
    db.session.add(draft)
    db.session.commit()
    return draft


# Refine -----------------------------------------------------------------------------------


def refine(body) -> dict:
    instruction = f"User instruction: {body.instruction}" if body.instruction else ""
    instructions, _ = system_prompt("refine", FIELD=body.field, ACTION=body.action, INSTRUCTION=instruction)
    parsed = run_structured("refine", instructions, f"<user_text>\n{body.text}\n</user_text>", RefineOutput)
    return {"text": parsed.text[:20000], "change_summary": parsed.change_summary[:500]}


# Drafts -----------------------------------------------------------------------------------


def get_owned_draft(draft_id, user, lock: bool = False) -> AIDraft:
    stmt = select(AIDraft).where(AIDraft.id == draft_id)
    if lock:
        stmt = stmt.with_for_update()
    d = db.session.execute(stmt).scalar_one_or_none()
    if d is None or d.user_id != user.id:
        raise not_found()
    return d


def _push_history(d: AIDraft) -> None:
    history = list(d.history or [])
    history.insert(0, {"output": d.output, "revision": d.revision, "saved_at": datetime.now(UTC).isoformat()})
    d.history = history[:HISTORY_MAX]


def validate_output(task: str, output: dict) -> dict:
    schema = DRAFT_OUTPUT_SCHEMAS[task]
    try:
        return json.loads(schema.model_validate(output).model_dump_json())
    except ValidationError as e:
        raise ApiError("validation_error", "Some fields are invalid.", 400,
                       {"fields": {f"output.{k}": v for k, v in pydantic_fields(e).items()}}) from e


def patch_output(d: AIDraft, output: dict) -> AIDraft:
    if d.status == "discarded":
        raise ApiError("conflict", "This draft was discarded.", 409)
    validated = validate_output(d.task, output)
    _push_history(d)
    d.output = validated
    d.revision += 1
    db.session.commit()
    return d


def _resolve_path(obj, path: str):
    parts = path.split(".")
    parent, key = None, None
    cur = obj
    for p in parts:
        parent = cur
        if isinstance(cur, list):
            if not p.isdigit() or int(p) >= len(cur):
                raise bad_request(f"Unknown field '{path}'.")
            key = int(p)
        elif isinstance(cur, dict):
            if p not in cur:
                raise bad_request(f"Unknown field '{path}'.")
            key = p
        else:
            raise bad_request(f"Unknown field '{path}'.")
        cur = parent[key]
    return parent, key, cur


def refine_section(d: AIDraft, field: str, instruction: str) -> AIDraft:
    if d.status == "discarded":
        raise ApiError("conflict", "This draft was discarded.", 409)
    new_output = copy.deepcopy(d.output)
    parent, key, current = _resolve_path(new_output, field)
    if not isinstance(current, str):
        raise bad_request("Only text fields can be refined. Edit list fields directly.")
    instructions, _ = system_prompt("refine_section", FIELD=field, INSTRUCTION=instruction)
    text = (
        "<platform_content source=\"draft\" id=\"current\">\n"
        + json.dumps(d.output, default=str)[:20000]
        + "\n</platform_content>"
    )
    parsed = run_structured("refine_section", instructions, text, SectionOutput)
    parent[key] = parsed.value
    _push_history(d)
    d.output = new_output
    d.revision += 1
    db.session.commit()
    return d


def regenerate(d: AIDraft, user, additional_context: str | None) -> AIDraft:
    if d.status == "discarded":
        raise ApiError("conflict", "This draft was discarded.", 409)
    input_ = dict(d.input)
    if additional_context:
        if d.task == "harness_doc":
            input_["additional_context"] = additional_context
        elif d.task == "project_idea":
            input_["interests"] = f"{input_.get('interests') or ''}\n{additional_context}".strip()
        elif d.task == "resource_recommendations":
            input_["goal"] = f"{input_.get('goal') or ''}\n{additional_context}".strip()
    out, sources, version, title = TASK_RUNNERS[d.task](input_, user)
    _push_history(d)
    d.output = out
    d.context_sources = sources
    d.prompt_version = version
    d.title = title[:120]
    d.revision += 1
    db.session.commit()
    return d


def restore(d: AIDraft, index: int) -> AIDraft:
    history = list(d.history or [])
    if index >= len(history):
        raise bad_request("No such history entry.")
    entry = history.pop(index)
    history.insert(0, {"output": d.output, "revision": d.revision, "saved_at": datetime.now(UTC).isoformat()})
    d.history = history[:HISTORY_MAX]
    d.output = entry["output"]
    d.revision += 1
    db.session.commit()
    return d


def discard(d: AIDraft) -> AIDraft:
    if d.status == "published":
        raise ApiError("conflict", "Published drafts cannot be discarded.", 409)
    d.status = "discarded"
    db.session.commit()
    return d
