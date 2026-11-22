"""Test fixtures: real Postgres (docker compose), real JWTs (no bypass), fakes for GitHub/links/AI (spec §6.10, §15)."""

from __future__ import annotations

import base64
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app import create_app
from app.common.url_safety import LinkCheckResult
from app.config import Settings
from app.extensions import db
from app.integrations.github import GitHubError

TEST_DB = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://devcommons:devcommons@localhost:5433/devcommons_test"
)
ORIGIN = "http://localhost:5173"
CSRF_HEADERS = {"Origin": ORIGIN, "X-Requested-With": "devcommons"}
PASSWORD = "correct horse battery staple"


def make_settings(**overrides) -> Settings:
    values = dict(
        APP_ENV="test",
        SECRET_KEY="test-secret-key-test-secret-key-0123456789",
        DATABASE_URL=TEST_DB,
        CORS_ORIGINS=ORIGIN,
        JWT_SIGNING_KEYS={"test": base64.b64encode(b"k" * 32).decode()},
        JWT_ACTIVE_KID="test",
        FRONTEND_URL=ORIGIN,
        COOKIE_SECURE=False,
        EMAIL_PROVIDER="console",
        AI_ENABLED=True,
        AI_PROVIDER="fake",
        AI_PRICING_JSON={"fake-model": {"input_per_1m": 1.0, "cached_input_per_1m": 0.1, "output_per_1m": 2.0}},
        RATELIMIT_ENABLED=False,
        JOB_SECRET="job-secret-job-secret-job-secret",
        LOG_LEVEL="WARNING",
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


# Fakes ---------------------------------------------------------------------------------------


class FakeGitHub:
    """Stands in for GitHubClient. Configure `repos[(owner, repo)] = metadata | 'not_found' | 'private'`."""

    def __init__(self):
        self.repos: dict = {}
        self.readmes: dict = {}
        self.trees: dict = {}
        self.files: dict = {}
        self.rate_remaining = 5000
        self.down = False

    def add(self, owner, repo, **meta):
        self.repos[(owner.lower(), repo.lower())] = {
            "owner": owner,
            "name": repo,
            "description": meta.get("description", "A harness"),
            "stars": meta.get("stars", 10),
            "forks": 1,
            "language": "TypeScript",
            "license": "MIT",
            "topics": ["claude-code"],
            "pushed_at": "2026-11-01T00:00:00Z",
            "default_branch": "main",
            "archived": meta.get("archived", False),
        }

    def _get(self, owner, repo):
        if self.down:
            raise GitHubError("rate_limited")
        v = self.repos.get((owner.lower(), repo.lower()), "not_found")
        if isinstance(v, str):
            raise GitHubError(v)
        return v

    def get_repo_metadata(self, owner, repo, etag=None):
        return dict(self._get(owner, repo)), '"etag"'

    def get_readme(self, owner, repo):
        self._get(owner, repo)
        return self.readmes.get((owner.lower(), repo.lower()), "# README\nUse it.")

    def get_tree(self, owner, repo, branch):
        self._get(owner, repo)
        return self.trees.get((owner.lower(), repo.lower()), ["README.md", "CLAUDE.md", ".claude/agents/spec.md"])

    def get_file(self, owner, repo, path, ref):
        return self.files.get(path, f"content of {path}")


class FakeLinks:
    def __init__(self):
        self.results: dict[str, LinkCheckResult] = {}
        self.default = LinkCheckResult("ok", http_status=200)
        self.calls: list[str] = []

    def __call__(self, url):
        self.calls.append(url)
        return self.results.get(url, self.default)


# Fixtures ------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app():
    application = create_app(make_settings())
    with application.app_context():
        db.session.execute(text("DROP SCHEMA public CASCADE"))
        db.session.execute(text("CREATE SCHEMA public"))
        db.session.commit()
        from flask_migrate import upgrade

        upgrade()
    yield application


_KEEP = {"categories", "trusted_domains", "alembic_version"}


@pytest.fixture(autouse=True)
def _clean(app):
    from app.common import url_safety
    from app.modules.ai.client import FakeAIClient
    from app.modules.ai.quota import reset_cost_cache
    from app.modules.ai.verification import clear_cache

    url_safety.RESOLVER = lambda host: ["10.0.0.9"] if host.startswith("internal.") else ["93.184.216.34"]
    ctx = app.app_context()
    ctx.push()
    app.extensions["github_client"] = FakeGitHub()
    app.extensions["link_checker"] = FakeLinks()
    app.extensions["ai_client"] = FakeAIClient()
    app.extensions["email_sender"].outbox.clear()
    settings = app.extensions["settings"]
    original = settings.model_copy()
    reset_cost_cache()
    clear_cache()
    yield
    db.session.rollback()
    db.session.remove()
    app.extensions["settings"] = original
    tables = [
        r[0]
        for r in db.session.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        ).all()
        if r[0] not in _KEEP
    ]
    db.session.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    db.session.commit()
    from app.cli import seed_reference_data

    seed_reference_data()  # TRUNCATE ... CASCADE also empties trusted_domains (FK added_by -> users)
    ctx.pop()
    url_safety.RESOLVER = url_safety.resolve_host


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def github(app):
    return app.extensions["github_client"]


@pytest.fixture
def links(app):
    return app.extensions["link_checker"]


@pytest.fixture
def ai(app):
    return app.extensions["ai_client"]


@pytest.fixture
def outbox(app):
    return app.extensions["email_sender"].outbox


@pytest.fixture
def settings(app):
    return app.extensions["settings"]


# Helpers -------------------------------------------------------------------------------------


def make_user(username=None, role="user", verified=True, status="active", password=PASSWORD, email=None):
    from app.auth.passwords import hash_password
    from app.modules.users.models import User

    username = username or f"user{uuid.uuid4().hex[:8]}"
    u = User(
        email=email or f"{username}@example.com",
        email_verified_at=datetime.now(UTC) if verified else None,
        password_hash=hash_password(password),
        username=username,
        display_name=username.capitalize(),
        role=role,
        status=status,
    )
    db.session.add(u)
    db.session.commit()
    return u


def auth_header(user) -> dict:
    """Creates a real auth_sessions row and mints a real access token (no bypass)."""
    from datetime import timedelta

    from app.auth.models import AuthSession
    from app.auth.sessions import hash_token, new_refresh_token
    from app.auth.tokens import issue_access_token

    now = datetime.now(UTC)
    sess = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_token(new_refresh_token()),
        expires_at=now + timedelta(days=30),
        absolute_expires_at=now + timedelta(days=90),
    )
    db.session.add(sess)
    db.session.commit()
    token, _ = issue_access_token(user, sess.id)
    return {"Authorization": f"Bearer {token}"}


def harness_body(**over) -> dict:
    body = {
        "name": "Spec-First Claude Harness",
        "repo_url": "https://github.com/ada/spec-first-harness",
        "short_description": "A Claude Code harness that forces a written spec before any code is produced.",
        "detailed_explanation": "## How it works\n" + "The harness writes a SPEC.md first and blocks edits. " * 3,
        "components": [{"type": "hook", "name": "block-edits", "description": "PreToolUse hook"}],
        "tools": ["claude_code"],
        "category": "agent-orchestration",
        "tags": ["spec-driven", "Hooks"],
        "accepts_collaboration": True,
    }
    body.update(over)
    return body


def idea_body(**over) -> dict:
    body = {
        "title": "AI code-review bot",
        "problem_statement": "Code reviews are slow and inconsistent across teams.",
        "proposed_solution": "A bot that pre-reviews pull requests with agent checks.",
        "tech_stack": ["Python", "fastapi"],
        "expected_features": [{"title": "PR summaries", "detail": "Summarize changes"}],
        "category": "agentic-ai",
        "tags": ["review"],
        "collaboration_status": "seeking_collaborators",
    }
    body.update(over)
    return body


def resource_body(**over) -> dict:
    body = {
        "name": "Python tutorial",
        "url": "https://docs.python.org/3/tutorial/",
        "description": "The official Python tutorial covering the basics of the language.",
        "category": "python",
        "resource_type": "official_docs",
        "tags": ["python"],
        "level": "beginner",
        "language": "en",
    }
    body.update(over)
    return body


def walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_keys(v)
