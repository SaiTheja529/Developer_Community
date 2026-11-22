"""Builds model context from platform entities and GitHub, with accurate source lists (spec §9.4)."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from app.common.content import can_view, categories_by_id, model_for, public_clause
from app.common.text import snippet
from app.extensions import db

CONTEXT_BUDGET = 24_000
MIN_SECTION = 300


@dataclass
class Section:
    source: dict
    text: str


@dataclass
class BuiltContext:
    text: str
    sources: list[dict]
    title: str | None = None
    sections: list[Section] = field(default_factory=list)


def _esc(value) -> str:
    """Prevent content from closing our wrapper tags."""
    s = "" if value is None else str(value)
    return s.replace("</platform_content", "&lt;/platform_content").replace(
        "</untrusted_repository_content", "&lt;/untrusted_repository_content"
    )


def _platform(source: str, entity_id, body: str) -> str:
    return f'<platform_content source="{source}" id="{entity_id}">\n{body}\n</platform_content>'


def _repo_block(repo: str, path: str, content: str, truncated: bool) -> str:
    return (
        f'<untrusted_repository_content repo="{repo}" path="{_esc(path)}" truncated="{str(truncated).lower()}">\n'
        f"{_esc(content)}\n</untrusted_repository_content>"
    )


def _fit(sections: list[Section], budget: int = CONTEXT_BUDGET) -> list[Section]:
    """Truncate lowest-priority (last) sections first until the total fits the budget."""
    total = sum(len(s.text) for s in sections)
    for sec in reversed(sections):
        if total <= budget:
            break
        excess = total - budget
        if len(sec.text) - excess >= MIN_SECTION:
            sec.text = sec.text[: len(sec.text) - excess] + "\n…[truncated]"
            sec.source["truncated"] = True
            total = budget
        else:
            total -= len(sec.text)
            sec.text = ""
            sec.source["status"] = "omitted"
            sec.source["reason"] = "context budget"
    return [s for s in sections if s.text]


def github_sections(snapshot, include_metadata: bool = True) -> list[Section]:
    repo = f"{snapshot.owner}/{snapshot.repo}"
    base = f"https://github.com/{repo}"
    branch = snapshot.default_branch
    if not snapshot.usable:
        reason = {
            "rate_limited": "GitHub rate limit",
            "not_found": "Repository not found",
            "private": "Repository is private",
        }.get(snapshot.status, "GitHub unavailable")
        return [Section({"kind": "github", "label": "Repository content", "status": "failed", "reason": reason}, "")]
    out: list[Section] = []
    stale = snapshot.status == "stale"
    if include_metadata and snapshot.metadata:
        m = snapshot.metadata
        lines = [
            f"Repository: {repo}",
            f"Description: {_esc(m.get('description'))}",
            f"Language: {m.get('language')}; License: {m.get('license')}; Stars: {m.get('stars')}; "
            f"Last push: {m.get('pushed_at')}; Archived: {m.get('archived')}",
            f"Topics: {', '.join(m.get('topics') or [])}",
        ]
        out.append(
            Section(
                {"kind": "github", "label": "Repository metadata", "url": base, "status": "included", "stale": stale},
                _repo_block(repo, "(metadata)", "\n".join(lines), False),
            )
        )
    if snapshot.readme:
        out.append(
            Section(
                {
                    "kind": "github",
                    "label": "README.md",
                    "url": f"{base}/blob/{branch}/README.md",
                    "status": "included",
                    "truncated": snapshot.readme_truncated,
                    "stale": stale,
                },
                _repo_block(repo, "README.md", snapshot.readme, snapshot.readme_truncated),
            )
        )
    for path, content in snapshot.key_files.items():
        trunc = bool(snapshot.key_files_truncated.get(path))
        out.append(
            Section(
                {
                    "kind": "github",
                    "label": path,
                    "url": f"{base}/blob/{branch}/{path}",
                    "status": "included",
                    "truncated": trunc,
                    "stale": stale,
                },
                _repo_block(repo, path, content, trunc),
            )
        )
    if snapshot.tree:
        shown = snapshot.tree[:400]
        truncated = len(shown) < snapshot.tree_total
        out.append(
            Section(
                {
                    "kind": "github",
                    "label": f"Repository file tree ({len(shown):,} of {snapshot.tree_total:,} paths)",
                    "status": "included",
                    "truncated": truncated,
                    "stale": stale,
                },
                _repo_block(repo, "(file tree)", "\n".join(shown), truncated),
            )
        )
    return out


def _harness_sections(h) -> list[Section]:
    from app.integrations.github import get_repo_snapshot
    from app.modules.harnesses.models import HarnessReview
    from app.modules.suggestions.models import Suggestion

    cat = categories_by_id([h.category_id]).get(h.category_id)
    comps = "\n".join(
        f"- [{c.get('type')}] {_esc(c.get('name'))}: {_esc(c.get('description') or '')}" for c in (h.components or [])
    )
    body = "\n\n".join(
        [
            f"Name: {_esc(h.name)}",
            f"Repository: {h.repo_url}",
            f"Category: {cat.name if cat else ''}; Tools: {', '.join(h.tools)}; Tags: {', '.join(h.tags)}",
            f"Short description:\n{_esc(h.short_description)}",
            f"Detailed explanation:\n{_esc(h.detailed_explanation)}",
            f"Architecture:\n{_esc(h.architecture or '(not provided)')}",
            f"Components:\n{comps or '(none listed)'}",
            f"Setup instructions:\n{_esc(h.setup_instructions or '(not provided)')}",
            f"Limitations:\n{_esc(h.limitations or '(not provided)')}",
        ]
    )
    sections = [
        Section(
            {"kind": "platform", "label": f"Harness: {h.name} (submitted fields)", "status": "included"},
            _platform("harness", h.id, body),
        )
    ]
    sugg = db.session.execute(
        select(Suggestion)
        .where(Suggestion.harness_id == h.id, public_clause(Suggestion))
        .order_by(Suggestion.vote_count.desc())
        .limit(5)
    ).scalars().all()
    if sugg:
        text = "\n".join(f"- ({s.kind}, {s.status}) {_esc(s.title)}: {_esc(snippet(s.body, 300))}" for s in sugg)
        sections.append(
            Section(
                {"kind": "platform", "label": f"Top {len(sugg)} community suggestions", "status": "included"},
                _platform("suggestions", h.id, text),
            )
        )
    reviews = db.session.execute(
        select(HarnessReview)
        .where(HarnessReview.harness_id == h.id, public_clause(HarnessReview))
        .order_by(HarnessReview.vote_count.desc())
        .limit(3)
    ).scalars().all()
    if reviews:
        text = "\n".join(
            f"- Tested: {_esc(snippet(r.what_tested, 300))} | Worked: {_esc(snippet(r.worked_well, 200))} | "
            f"Didn't: {_esc(snippet(r.did_not_work, 200))} | Overall rating: {r.rating_overall}"
            for r in reviews
        )
        sections.append(
            Section(
                {"kind": "platform", "label": f"Top {len(reviews)} testing reports (summaries)", "status": "included"},
                _platform("reviews", h.id, text),
            )
        )
    sections.extend(github_sections(get_repo_snapshot(h.repo_owner, h.repo_name)))
    return sections


def _idea_sections(i) -> list[Section]:
    from app.modules.comments.models import Comment
    from app.modules.suggestions.models import Suggestion

    features = "\n".join(f"- {_esc(f.get('title'))}: {_esc(f.get('detail') or '')}" for f in (i.expected_features or []))
    body = "\n\n".join(
        [
            f"Title: {_esc(i.title)}",
            f"Problem:\n{_esc(i.problem_statement)}",
            f"Proposed solution:\n{_esc(i.proposed_solution)}",
            f"Description:\n{_esc(i.description or '(not provided)')}",
            f"Expected features:\n{features or '(none listed)'}",
            f"Tech stack: {', '.join(i.tech_stack) or '(not specified)'}",
            f"Collaboration status: {i.collaboration_status}",
        ]
    )
    sections = [
        Section(
            {"kind": "platform", "label": f"Idea: {i.title} (submitted fields)", "status": "included"},
            _platform("idea", i.id, body),
        )
    ]
    sugg = db.session.execute(
        select(Suggestion)
        .where(Suggestion.idea_id == i.id, public_clause(Suggestion))
        .order_by(Suggestion.vote_count.desc())
        .limit(5)
    ).scalars().all()
    if sugg:
        text = "\n".join(f"- ({s.kind}) {_esc(s.title)}: {_esc(snippet(s.body, 300))}" for s in sugg)
        sections.append(
            Section(
                {"kind": "platform", "label": f"Top {len(sugg)} community suggestions", "status": "included"},
                _platform("suggestions", i.id, text),
            )
        )
    comments = db.session.execute(
        select(Comment)
        .where(Comment.idea_id == i.id, public_clause(Comment))
        .order_by(Comment.created_at.desc())
        .limit(10)
    ).scalars().all()
    if comments:
        text = "\n".join(f"- {_esc(snippet(c.body, 300))}" for c in comments)
        sections.append(
            Section(
                {"kind": "platform", "label": f"{len(comments)} newest comments (snippets)", "status": "included"},
                _platform("comments", i.id, text),
            )
        )
    return sections


def _resource_sections(r) -> list[Section]:
    cat = categories_by_id([r.category_id]).get(r.category_id)
    body = "\n".join(
        [
            f"Name: {_esc(r.name)}",
            f"URL: {r.url}",
            f"Type: {r.resource_type}; Category: {cat.name if cat else ''}; Level: {r.level or 'n/a'}",
            f"Official domain verified: {r.official_verified}",
            f"Link status: {r.link_status}",
            f"Description:\n{_esc(r.description)}",
            "NOTE: The external page itself was NOT fetched. Do not claim to have read it.",
        ]
    )
    return [
        Section(
            {"kind": "platform", "label": f"Resource: {r.name} (submitted fields)", "status": "included"},
            _platform("resource", r.id, body),
        ),
        Section({"kind": "external", "label": "External page content", "status": "not_fetched", "url": r.url}, ""),
    ]


def _collection_sections(c, viewer) -> list[Section]:
    from app.modules.collections.models import CollectionItem
    from app.modules.resources.models import Resource

    rows = db.session.execute(
        select(CollectionItem, Resource)
        .join(Resource, Resource.id == CollectionItem.resource_id)
        .where(CollectionItem.collection_id == c.id)
        .order_by(CollectionItem.position)
    ).all()
    lines = [
        f"{n + 1}. {_esc(r.name)} — {r.url} ({r.resource_type})" + (f"\n   Note: {_esc(item.note)}" if item.note else "")
        for n, (item, r) in enumerate(rows)
        if can_view(r, viewer)
    ]
    body = f"Title: {_esc(c.title)}\nDescription:\n{_esc(c.description or '(none)')}\n\nItems:\n" + (
        "\n".join(lines) or "(empty)"
    )
    return [
        Section(
            {"kind": "platform", "label": f"Collection: {c.title} ({len(lines)} items)", "status": "included"},
            _platform("collection", c.id, body),
        )
    ]


def build(context_type: str | None, context_id, viewer) -> BuiltContext:
    if not context_type or context_id is None:
        return BuiltContext(text="", sources=[])
    model = model_for(context_type)
    obj = db.session.get(model, context_id)
    if obj is None or not can_view(obj, viewer):
        return BuiltContext(
            text="",
            sources=[{"kind": "platform", "label": f"{context_type.capitalize()} context", "status": "unavailable"}],
        )
    if context_type == "harness":
        sections = _harness_sections(obj)
    elif context_type == "idea":
        sections = _idea_sections(obj)
    elif context_type == "resource":
        sections = _resource_sections(obj)
    else:
        sections = _collection_sections(obj, viewer)
    sources = [s.source for s in sections]
    fitted = _fit([s for s in sections if s.text])
    return BuiltContext(
        text="\n\n".join(s.text for s in fitted),
        sources=sources,
        title=getattr(obj, "name", None) or getattr(obj, "title", None),
        sections=fitted,
    )
