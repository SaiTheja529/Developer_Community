"""GitHub integration: URL parsing, repo metadata, README, tree, key files, cache (spec §10.1).

Never executes, builds or installs anything from a repository.
"""

from __future__ import annotations

import base64
import fnmatch
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, urlsplit

import httpx

from app.common.errors import ApiError

log = logging.getLogger("devcommons.github")

OWNER_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
SNAPSHOT_TTL = timedelta(hours=6)
SNAPSHOT_BUDGET_SECONDS = 20.0
README_MAX = 30_000
TREE_MAX = 1_000
KEY_FILE_MAX = 8_000
KEY_FILES_TOTAL_MAX = 40_000
LOW_RATE_LIMIT = 50

# (pattern, max matches) in priority order (spec §9.4).
KEY_FILE_PATTERNS: list[tuple[str, int]] = [
    ("CLAUDE.md", 1),
    ("AGENTS.md", 1),
    (".claude/settings.json", 1),
    (".claude/agents/*.md", 5),
    (".claude/commands/*.md", 5),
    (".claude/skills/*/SKILL.md", 5),
    (".mcp.json", 1),
    (".cursor/rules/*", 5),
    (".cursorrules", 1),
    (".github/copilot-instructions.md", 1),
    (".windsurfrules", 1),
    ("GEMINI.md", 1),
]


@dataclass(frozen=True)
class RepoRef:
    owner: str
    repo: str

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


def parse_repo_url(url: str) -> RepoRef:
    """Accept only https://github.com/{owner}/{repo} (optional .git, trailing slash, /tree/{branch})."""
    if not isinstance(url, str):
        raise ValueError("Must be a public GitHub repository URL.")
    url = url.strip()
    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in ("github.com", "www.github.com"):
        raise ValueError("Must be a public GitHub repository URL (https://github.com/owner/repo).")
    if parts.port not in (None, 443) or parts.username or parts.password:
        raise ValueError("Must be a public GitHub repository URL.")
    segs = [s for s in parts.path.split("/") if s]
    if len(segs) < 2:
        raise ValueError("Must point at a repository root (https://github.com/owner/repo).")
    owner, repo = segs[0], segs[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    rest = segs[2:]
    if rest and not (rest[0] == "tree" and len(rest) >= 2):
        raise ValueError("Must point at a repository root (https://github.com/owner/repo).")
    if not OWNER_RE.match(owner) or not REPO_RE.match(repo) or repo in (".", ".."):
        raise ValueError("Must be a valid GitHub owner/repository.")
    return RepoRef(owner, repo)


class GitHubError(Exception):
    def __init__(self, status: str, message: str = ""):
        super().__init__(message or status)
        self.status = status  # not_found | private | error | rate_limited


def normalize_metadata(raw: dict) -> dict:
    lic = raw.get("license") or {}
    return {
        "owner": (raw.get("owner") or {}).get("login"),
        "name": raw.get("name"),
        "description": raw.get("description"),
        "stars": raw.get("stargazers_count", 0),
        "forks": raw.get("forks_count", 0),
        "language": raw.get("language"),
        "license": lic.get("spdx_id") if lic.get("spdx_id") not in (None, "NOASSERTION") else lic.get("name"),
        "topics": raw.get("topics") or [],
        "pushed_at": raw.get("pushed_at"),
        "default_branch": raw.get("default_branch") or "main",
        "archived": bool(raw.get("archived")),
    }


class GitHubClient:
    def __init__(self, token: str | None = None, transport: httpx.BaseTransport | None = None):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DevCommons-App",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers=headers,
            timeout=httpx.Timeout(10.0, connect=5.0),
            transport=transport,
        )
        self.rate_remaining: int | None = None

    def _get(self, path: str, *, raw: bool = False, etag: str | None = None, params: dict | None = None) -> httpx.Response:
        headers = {}
        if raw:
            headers["Accept"] = "application/vnd.github.raw+json"
        if etag:
            headers["If-None-Match"] = etag
        try:
            resp = self._client.get(path, headers=headers, params=params)
        except httpx.TimeoutException as e:
            raise GitHubError("error", "timeout") from e
        except httpx.HTTPError as e:
            raise GitHubError("error", "connection error") from e
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining is not None and remaining.isdigit():
            self.rate_remaining = int(remaining)
        if resp.status_code in (403, 429) and (resp.headers.get("X-RateLimit-Remaining") == "0" or resp.status_code == 429):
            raise GitHubError("rate_limited", "GitHub rate limit")
        return resp

    def get_repo_metadata(self, owner: str, repo: str, etag: str | None = None) -> tuple[dict | None, str | None]:
        """Returns (normalized metadata or None if 304 Not Modified, etag)."""
        resp = self._get(f"/repos/{owner}/{repo}", etag=etag)
        if resp.status_code == 304:
            return None, etag
        if resp.status_code in (404, 451):
            raise GitHubError("not_found")
        if resp.status_code in (401, 403):
            raise GitHubError("private")
        if resp.status_code >= 400:
            raise GitHubError("error", f"GitHub status {resp.status_code}")
        data = resp.json()
        if data.get("private") is True or data.get("visibility") in ("private", "internal"):
            raise GitHubError("private")
        return normalize_metadata(data), resp.headers.get("ETag")

    def get_readme(self, owner: str, repo: str) -> str | None:
        resp = self._get(f"/repos/{owner}/{repo}/readme", raw=True)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise GitHubError("error", f"README status {resp.status_code}")
        return resp.text

    def get_tree(self, owner: str, repo: str, branch: str) -> list[str]:
        resp = self._get(f"/repos/{owner}/{repo}/git/trees/{quote(branch, safe='')}", params={"recursive": "1"})
        if resp.status_code in (404, 409):
            return []
        if resp.status_code >= 400:
            raise GitHubError("error", f"tree status {resp.status_code}")
        return [e["path"] for e in resp.json().get("tree", []) if e.get("type") == "blob"]

    def get_file(self, owner: str, repo: str, path: str, ref: str) -> str | None:
        resp = self._get(f"/repos/{owner}/{repo}/contents/{quote(path)}", raw=True, params={"ref": ref})
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise GitHubError("error", f"file status {resp.status_code}")
        if resp.headers.get("content-type", "").startswith("application/json"):
            try:
                payload = resp.json()
                if isinstance(payload, dict) and payload.get("encoding") == "base64":
                    return base64.b64decode(payload.get("content", "")).decode("utf-8", "replace")
            except ValueError:
                pass
        return resp.text


def get_client() -> GitHubClient:
    from flask import current_app

    client = current_app.extensions.get("github_client")
    if client is None:
        client = GitHubClient(current_app.extensions["settings"].GITHUB_TOKEN)
        current_app.extensions["github_client"] = client
    return client


def repo_unavailable(status: str) -> ApiError:
    messages = {
        "not_found": "Repository not found. Only public GitHub repositories can be submitted.",
        "private": "This repository is private. Only public GitHub repositories can be submitted.",
        "rate_limited": "GitHub is rate-limiting requests right now. Try again in a few minutes.",
        "error": "Couldn't read the repository. Try again later or fill the form manually.",
    }
    return ApiError("repo_unavailable", messages.get(status, messages["error"]), 422, {"reason": status})


def fetch_repo_for_submission(url: str) -> tuple[RepoRef, dict]:
    """Parse + fetch metadata. 400 validation_error for bad URLs, 422 repo_unavailable otherwise."""
    from app.common.errors import validation_error

    try:
        ref = parse_repo_url(url)
    except ValueError as e:
        raise validation_error({"repo_url": str(e)}) from e
    try:
        meta, _ = get_client().get_repo_metadata(ref.owner, ref.repo)
    except GitHubError as e:
        raise repo_unavailable(e.status) from e
    # Use GitHub's canonical casing.
    ref = RepoRef(meta.get("owner") or ref.owner, meta.get("name") or ref.repo)
    return ref, meta or {}


# Snapshot (AI context) ---------------------------------------------------------------------


@dataclass
class RepoSnapshot:
    owner: str
    repo: str
    status: str  # ok | stale | not_found | private | error | rate_limited
    metadata: dict | None = None
    readme: str | None = None
    readme_truncated: bool = False
    tree: list[str] = field(default_factory=list)
    tree_total: int = 0
    key_files: dict[str, str] = field(default_factory=dict)
    key_files_truncated: dict[str, bool] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return self.status in ("ok", "stale")

    @property
    def default_branch(self) -> str:
        return (self.metadata or {}).get("default_branch") or "main"


def discover_key_files(paths: list[str]) -> list[str]:
    selected: list[str] = []
    for pattern, max_n in KEY_FILE_PATTERNS:
        if "*" in pattern:
            matches = sorted(p for p in paths if _glob_match(p, pattern))
        else:
            matches = [p for p in paths if p == pattern]
        for m in matches[:max_n]:
            if m not in selected:
                selected.append(m)
    return selected


def _glob_match(path: str, pattern: str) -> bool:
    """fnmatch where '*' does not cross '/' boundaries."""
    p_parts, pat_parts = path.split("/"), pattern.split("/")
    if len(p_parts) != len(pat_parts):
        return False
    return all(fnmatch.fnmatchcase(a, b) for a, b in zip(p_parts, pat_parts, strict=True))


def _from_cache(row) -> RepoSnapshot:
    meta = dict(row.metadata_ or {})
    tree_total = meta.pop("_tree_total", len(row.tree or []))
    truncated = meta.pop("_key_files_truncated", {})
    readme_trunc = meta.pop("_readme_truncated", False)
    return RepoSnapshot(
        owner=row.owner,
        repo=row.repo,
        status=row.fetch_status,
        metadata=meta or None,
        readme=row.readme,
        readme_truncated=readme_trunc,
        tree=list(row.tree or []),
        tree_total=tree_total,
        key_files=dict(row.key_files or {}),
        key_files_truncated=truncated,
    )


def get_repo_snapshot(owner: str, repo: str) -> RepoSnapshot:
    """All of metadata, README, tree and key files; cached in github_repo_cache for 6 h with ETags."""
    from app.extensions import db
    from app.integrations.models import GithubRepoCache

    key_owner, key_repo = owner.lower(), repo.lower()
    row = db.session.get(GithubRepoCache, (key_owner, key_repo))
    now = datetime.now(UTC)
    if row is not None and row.fetch_status == "ok" and now - row.fetched_at < SNAPSHOT_TTL:
        return _from_cache(row)

    client = get_client()
    if client.rate_remaining is not None and client.rate_remaining < LOW_RATE_LIMIT and row is not None:
        snap = _from_cache(row)
        if snap.status == "ok":
            snap.status = "stale"
        return snap

    deadline = time.monotonic() + SNAPSHOT_BUDGET_SECONDS
    try:
        meta, etag = client.get_repo_metadata(owner, repo, etag=row.etag if row is not None and row.fetch_status == "ok" else None)
        if meta is None and row is not None:  # 304: unchanged repo; refresh timestamp and reuse
            row.fetched_at = now
            db.session.commit()
            return _from_cache(row)
        snap = RepoSnapshot(owner=owner, repo=repo, status="ok", metadata=meta)
        readme = client.get_readme(owner, repo) if time.monotonic() < deadline else None
        if readme is not None:
            snap.readme_truncated = len(readme) > README_MAX
            snap.readme = readme[:README_MAX]
        tree = client.get_tree(owner, repo, snap.default_branch) if time.monotonic() < deadline else []
        snap.tree_total = len(tree)
        snap.tree = tree[:TREE_MAX]
        total = 0
        for path in discover_key_files(tree):
            if time.monotonic() >= deadline or total >= KEY_FILES_TOTAL_MAX:
                break
            content = client.get_file(owner, repo, path, snap.default_branch)
            if content is None:
                continue
            budget = min(KEY_FILE_MAX, KEY_FILES_TOTAL_MAX - total)
            snap.key_files_truncated[path] = len(content) > budget
            snap.key_files[path] = content[:budget]
            total += len(snap.key_files[path])
    except GitHubError as e:
        if row is not None and row.fetch_status == "ok" and e.status in ("rate_limited", "error"):
            stale = _from_cache(row)
            stale.status = "stale"
            return stale
        snap = RepoSnapshot(owner=owner, repo=repo, status=e.status)
        etag = None

    meta_store = dict(snap.metadata or {})
    meta_store["_tree_total"] = snap.tree_total
    meta_store["_key_files_truncated"] = snap.key_files_truncated
    meta_store["_readme_truncated"] = snap.readme_truncated
    if row is None:
        row = GithubRepoCache(owner=key_owner, repo=key_repo, fetch_status=snap.status)
        db.session.add(row)
    row.fetch_status = snap.status
    row.metadata_ = meta_store if snap.status == "ok" else None
    row.readme = snap.readme
    row.tree = snap.tree
    row.key_files = snap.key_files
    row.etag = etag
    row.fetched_at = now
    try:
        db.session.commit()
    except Exception:  # pragma: no cover - cache write failures are not fatal
        db.session.rollback()
        log.warning("github_cache_write_failed")
    return snap
