"""`flask seed --demo`: sample users and content so the frontend has data to render (dev only)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.common.text import normalize_url, slugify, url_domain
from app.extensions import db
from app.extensions import settings as get_settings

DEMO_PASSWORD = "devcommons-demo-password"

HARNESSES = [
    ("Spec-First Claude Harness", "anthropics", "claude-code", "agent-orchestration", ["claude_code"], ["spec-driven", "hooks"]),
    ("TDD Guard Rails", "nizos", "tdd-guard", "testing", ["claude_code"], ["tdd", "hooks"]),
    ("Cursor Rules Starter", "PatrickJS", "awesome-cursorrules", "ai-coding", ["cursor"], ["rules", "starter"]),
    ("Copilot Review Instructions", "github", "awesome-copilot", "code-review", ["github_copilot"], ["review"]),
    ("Aider Conventions Pack", "Aider-AI", "aider", "developer-productivity", ["aider"], ["conventions"]),
    ("MCP Docs Workflow", "modelcontextprotocol", "servers", "documentation", ["claude_code", "cursor"], ["mcp", "docs"]),
    ("Secure Agent Sandbox", "openai", "codex", "security", ["openai_codex"], ["sandbox", "security"]),
    ("Gemini CLI Playbook", "google-gemini", "gemini-cli", "devops", ["gemini_cli"], ["cli", "devops"]),
    ("Cline Task Templates", "cline", "cline", "ai-coding", ["cline"], ["templates"]),
    ("Windsurf Monorepo Rules", "vercel", "turborepo", "developer-productivity", ["windsurf"], ["monorepo"]),
]

IDEAS = [
    ("AI code-review bot for small teams", "agentic-ai", ["python", "fastapi", "postgresql"]),
    ("Offline-first habit tracker", "mobile", ["react-native", "sqlite"]),
    ("Docs search with semantic ranking", "ai", ["python", "pgvector"]),
    ("Self-hosted feature flag service", "developer-tools", ["go", "redis"]),
    ("Cloud cost anomaly alerts", "cloud", ["typescript", "aws-lambda"]),
    ("Open dataset quality checker", "data", ["python", "duckdb"]),
    ("Accessible form builder", "web-development", ["react", "typescript"]),
    ("Secrets leak pre-commit scanner", "security", ["rust"]),
    ("Kubernetes cost dashboard", "devops", ["go", "kubernetes"]),
    ("Pair-programming agent for juniors", "agentic-ai", ["python", "langgraph"]),
]

RESOURCES = [
    ("The Python Tutorial", "https://docs.python.org/3/tutorial/", "python", "official_docs", "beginner"),
    ("React: Learn", "https://react.dev/learn", "javascript-typescript", "official_docs", "beginner"),
    ("MDN Web Docs: JavaScript Guide", "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "web", "guide", "beginner"),
    ("LangGraph concepts", "https://langchain-ai.github.io/langgraph/concepts/", "agentic-ai", "official_docs", "intermediate"),
    ("Model Context Protocol docs", "https://modelcontextprotocol.io/introduction", "ai", "official_docs", "intermediate"),
    ("Kubernetes basics", "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "devops", "tutorial", "beginner"),
    ("PostgreSQL documentation", "https://www.postgresql.org/docs/current/", "databases", "official_docs", "advanced"),
    ("Docker get started", "https://docs.docker.com/get-started/", "devops", "tutorial", "beginner"),
    ("Spring Boot reference", "https://docs.spring.io/spring-boot/index.html", "java", "official_docs", "intermediate"),
    ("AWS Well-Architected", "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html", "cloud", "guide", "advanced"),
]


def _user(username: str, display: str, role: str = "user"):
    from app.modules.users.models import User

    u = db.session.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if u is None:
        u = User(
            email=f"{username}@demo.devcommons.local",
            email_verified_at=datetime.now(UTC),
            password_hash=hash_password(DEMO_PASSWORD),
            username=username,
            display_name=display,
            role=role,
            bio=f"Demo account ({display}).",
            skills=["python", "typescript"],
        )
        db.session.add(u)
        db.session.flush()
    return u


def _cat(module: str, slug: str) -> int:
    from app.modules.meta.models import Category

    return db.session.execute(select(Category.id).where(Category.module == module, Category.slug == slug)).scalar_one()


def seed_demo() -> dict:
    if get_settings().is_production:
        raise RuntimeError("Demo data must not be seeded in production.")
    from app.modules.collections.models import Collection, CollectionItem
    from app.modules.harnesses.models import Harness
    from app.modules.ideas.models import Idea
    from app.modules.resources.models import Resource
    from app.modules.resources.service import is_official_domain

    ada = _user("ada", "Ada Lovelace", "admin")
    grace = _user("grace", "Grace Hopper", "moderator")
    linus = _user("linus", "Linus T.")
    authors = [ada, grace, linus]
    added = {"harnesses": 0, "ideas": 0, "resources": 0, "collections": 0}

    for n, (name, owner, repo, cat, tools, tags) in enumerate(HARNESSES):
        exists = db.session.execute(
            select(Harness.id).where(Harness.repo_owner == owner, Harness.repo_name == repo, Harness.deleted_at.is_(None))
        ).first()
        if exists:
            continue
        db.session.add(
            Harness(
                slug=slugify(name), author_id=authors[n % 3].id, name=name,
                repo_url=f"https://github.com/{owner}/{repo}", repo_owner=owner, repo_name=repo,
                short_description=f"{name}: a sample harness that shows how to structure agent rules and hooks.",
                detailed_explanation=f"## How it works\n\n{name} combines instruction files, subagents and hooks "
                "to keep the AI coding agent on track. This is demo content.",
                architecture="- Instruction file sets conventions\n- Subagent drafts plans\n- Hook enforces checks",
                components=[{"type": "instruction_file", "name": "CLAUDE.md", "description": "Project conventions"},
                            {"type": "hook", "name": "pre-tool-check", "description": "Blocks risky edits"}],
                setup_instructions="1. Clone the repository\n2. Copy the config into your project\n3. Restart your agent",
                limitations="Demo data; not verified.",
                tools=tools, category_id=_cat("harness", cat), tags=tags, accepts_collaboration=n % 2 == 0,
                repo_metadata={"owner": owner, "name": repo, "stars": 100 * (n + 1), "forks": 5 * n,
                               "language": "TypeScript", "license": "MIT", "topics": tags, "archived": False,
                               "default_branch": "main", "description": name},
                repo_metadata_fetched_at=datetime.now(UTC), vote_count=n, is_featured=n < 2,
            )
        )
        added["harnesses"] += 1

    for n, (title, cat, tech) in enumerate(IDEAS):
        if db.session.execute(select(Idea.id).where(Idea.title == title)).first():
            continue
        db.session.add(
            Idea(
                slug=slugify(title), author_id=authors[(n + 1) % 3].id, title=title,
                problem_statement=f"Developers lack a simple way to handle: {title.lower()}.",
                proposed_solution=f"Build {title.lower()} as a small, focused open-source project.",
                description="Demo idea. Goals: ship an MVP in six weeks.",
                tech_stack=tech, expected_features=[{"title": "MVP", "detail": "Core workflow end to end"}],
                category_id=_cat("idea", cat), tags=[cat],
                collaboration_status="seeking_collaborators" if n % 2 == 0 else "sharing",
                vote_count=10 - n, interest_count=n, is_featured=n < 2,
            )
        )
        added["ideas"] += 1

    resources = []
    for n, (name, url, cat, rtype, level) in enumerate(RESOURCES):
        norm = normalize_url(url)
        r = db.session.execute(select(Resource).where(Resource.url_normalized == norm)).scalar_one_or_none()
        if r is None:
            domain = url_domain(url)
            r = Resource(
                submitter_id=authors[n % 3].id, name=name, url=url, url_normalized=norm, domain=domain,
                description=f"{name} — a well-known learning resource (demo entry).",
                category_id=_cat("resource", cat), resource_type=rtype, official_verified=is_official_domain(domain),
                tags=[cat], level=level, language="en", link_status="pending", vote_count=n, is_featured=n < 2,
            )
            db.session.add(r)
            db.session.flush()
            added["resources"] += 1
        resources.append(r)

    if not db.session.execute(select(Collection.id).where(Collection.title == "Start here: web fundamentals")).first():
        groups = [("Start here: web fundamentals", "web", resources[1:3]),
                  ("Agentic AI reading list", "agentic-ai", resources[3:5]),
                  ("Ship to production", "devops", resources[5:8])]
        for title, cat, items in groups:
            c = Collection(slug=slugify(title), owner_id=ada.id, title=title, description="Demo collection.",
                           category_id=_cat("resource", cat), tags=[cat], item_count=len(items))
            db.session.add(c)
            db.session.flush()
            for pos, r in enumerate(items):
                db.session.add(CollectionItem(collection_id=c.id, resource_id=r.id, position=pos))
                r.collection_count = (r.collection_count or 0) + 1
            added["collections"] += 1

    db.session.commit()
    added["login"] = {"emails": [u.email for u in authors], "password": DEMO_PASSWORD}
    return added
