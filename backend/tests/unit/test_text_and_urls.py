import httpx
import pytest
import respx

from app.common.text import clean_text, normalize_tags, normalize_url, slugify, validate_http_url
from app.common.url_safety import LinkCheckResult, UrlBlocked, assert_url_allowed, safe_check
from app.integrations.github import GitHubClient, GitHubError, discover_key_files, parse_repo_url
from app.integrations.link_checker import apply_result
from app.modules.ai.usage import estimate_cost


def test_clean_text_strips_control_chars_and_normalizes_newlines():
    assert clean_text("  a\x00b\r\nc\tz\x07 ") == "ab\nc\tz"


def test_normalize_tags():
    assert normalize_tags(["Spec Driven", "hooks", "HOOKS", "c#", "node.js"]) == ["spec-driven", "hooks", "c#", "node.js"]
    with pytest.raises(ValueError):
        normalize_tags(["bad/tag"])
    with pytest.raises(ValueError):
        normalize_tags([f"t{i}" for i in range(9)])


def test_slugify():
    assert slugify("Spec-First Claude Harness!") == "spec-first-claude-harness"
    assert slugify("Ünïcödé ✨") == "unicode"
    assert slugify("!!!") == "item"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.Example.com/Docs/?utm_source=x&b=2&a=1#frag", "example.com/Docs?a=1&b=2"),
        ("http://example.com:80/", "example.com/"),
        ("https://example.com:8443/x/", "example.com:8443/x"),
        ("https://example.com/path?ref=hn&fbclid=1&gclid=2", "example.com/path"),
    ],
)
def test_normalize_url(url, expected):
    assert normalize_url(url) == expected


@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "file:///etc/passwd", "ftp://x.com", "https://"])
def test_validate_http_url_rejects(url):
    with pytest.raises(ValueError):
        validate_http_url(url)


# SSRF ----------------------------------------------------------------------------------------


def _resolver(mapping):
    return lambda host: mapping.get(host, ["93.184.216.34"])


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://[::1]/",
        "http://localhost/",
        "http://example.com:8080/",
        "http://0.0.0.0/",
    ],
)
def test_assert_url_allowed_blocks_private(url):
    with pytest.raises(UrlBlocked):
        assert_url_allowed(url, resolver=_resolver({}))


def test_hostname_resolving_to_private_is_blocked():
    with pytest.raises(UrlBlocked):
        assert_url_allowed("https://evil.example/", resolver=_resolver({"evil.example": ["10.1.2.3"]}))


@respx.mock
def test_redirect_to_private_is_blocked():
    respx.head("https://good.example/").mock(
        return_value=httpx.Response(302, headers={"location": "http://169.254.169.254/"})
    )
    result = safe_check("https://good.example/", resolver=_resolver({}))
    assert result.status == "blocked"


@respx.mock
def test_safe_check_classifies():
    respx.head("https://a.example/ok").mock(return_value=httpx.Response(200))
    respx.head("https://a.example/gone").mock(return_value=httpx.Response(404))
    respx.head("https://a.example/moved").mock(return_value=httpx.Response(301, headers={"location": "/new"}))
    respx.head("https://a.example/new").mock(return_value=httpx.Response(200))
    respx.head("https://a.example/bot").mock(return_value=httpx.Response(403))
    respx.get("https://a.example/bot").mock(return_value=httpx.Response(403))
    r = _resolver({})
    assert safe_check("https://a.example/ok", resolver=r).status == "ok"
    assert safe_check("https://a.example/gone", resolver=r).status == "broken"
    moved = safe_check("https://a.example/moved", resolver=r)
    assert moved.status == "redirected" and moved.final_url == "https://a.example/new"
    assert safe_check("https://a.example/bot", resolver=r).status == "unreachable"


def test_link_status_needs_two_consecutive_failures():
    class R:
        link_status = "ok"
        link_consecutive_failures = 0
        link_broken_since = None
        link_last_checked_at = None
        link_http_status = None
        link_final_url = None

    r = R()
    broken = LinkCheckResult("broken", http_status=404)
    assert apply_result(r, broken) is False
    assert r.link_status == "ok"
    assert apply_result(r, broken) is True
    assert r.link_status == "broken" and r.link_broken_since is not None
    apply_result(r, LinkCheckResult("ok", http_status=200))
    assert r.link_status == "ok" and r.link_consecutive_failures == 0


# GitHub ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,owner,repo",
    [
        ("https://github.com/ada/spec-harness", "ada", "spec-harness"),
        ("https://github.com/ada/spec-harness.git", "ada", "spec-harness"),
        ("https://github.com/ada/spec-harness/", "ada", "spec-harness"),
        ("https://github.com/ada/spec-harness/tree/main", "ada", "spec-harness"),
    ],
)
def test_parse_repo_url_ok(url, owner, repo):
    ref = parse_repo_url(url)
    assert (ref.owner, ref.repo) == (owner, repo)
    assert ref.canonical_url == f"https://github.com/{owner}/{repo}"


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/ada/x",
        "https://gitlab.com/ada/x",
        "https://github.com/ada",
        "https://github.com/ada/x/blob/main/README.md",
        "https://github.com/a_b/x",
    ],
)
def test_parse_repo_url_rejects(url):
    with pytest.raises(ValueError):
        parse_repo_url(url)


@respx.mock
def test_github_client_statuses():
    respx.get("https://api.github.com/repos/ada/missing").mock(return_value=httpx.Response(404))
    respx.get("https://api.github.com/repos/ada/secret").mock(
        return_value=httpx.Response(200, json={"name": "secret", "private": True})
    )
    respx.get("https://api.github.com/repos/ada/limited").mock(
        return_value=httpx.Response(403, headers={"X-RateLimit-Remaining": "0"})
    )
    respx.get("https://api.github.com/repos/ada/ok").mock(
        return_value=httpx.Response(
            200,
            json={"name": "ok", "owner": {"login": "ada"}, "stargazers_count": 3, "license": {"spdx_id": "MIT"}},
            headers={"X-RateLimit-Remaining": "4999", "ETag": '"abc"'},
        )
    )
    c = GitHubClient()
    for repo, status in (("missing", "not_found"), ("secret", "private"), ("limited", "rate_limited")):
        with pytest.raises(GitHubError) as e:
            c.get_repo_metadata("ada", repo)
        assert e.value.status == status
    meta, etag = c.get_repo_metadata("ada", "ok")
    assert meta["stars"] == 3 and meta["license"] == "MIT" and etag == '"abc"'
    assert c.rate_remaining == 4999


def test_discover_key_files():
    paths = [
        "CLAUDE.md",
        ".claude/agents/a.md",
        ".claude/agents/nested/b.md",
        ".claude/skills/x/SKILL.md",
        ".cursor/rules/r1.mdc",
        "src/CLAUDE.md",
    ]
    found = discover_key_files(paths)
    assert "CLAUDE.md" in found and ".claude/agents/a.md" in found and ".claude/skills/x/SKILL.md" in found
    assert ".claude/agents/nested/b.md" not in found and "src/CLAUDE.md" not in found


def test_estimate_cost():
    pricing = {"m": {"input_per_1m": 2.0, "cached_input_per_1m": 0.5, "output_per_1m": 8.0}}
    cost = estimate_cost("m", 1_000_000, 200_000, 500_000, pricing=pricing)
    # (800k * 2 + 200k * 0.5 + 500k * 8) / 1M = 1.6 + 0.1 + 4.0
    assert float(cost) == pytest.approx(5.7)
    assert float(estimate_cost("unknown", 10, 0, 10, pricing=pricing)) == 0


# Regression: NAT64 networks (64:ff9b::/96) must not make public sites look private,
# while NAT64/6to4 addresses that embed a private IPv4 must still be blocked.
def test_nat64_and_6to4_embedded_ipv4():
    public_nat64 = _resolver({"react.example": ["64:ff9b::4c4c:1516", "76.76.21.22"]})
    assert_url_allowed("https://react.example/", resolver=public_nat64)  # does not raise
    for addr in ("64:ff9b::a00:1", "64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe", "2002:a00:1::", "::ffff:10.0.0.1"):
        with pytest.raises(UrlBlocked):
            assert_url_allowed("https://x.example/", resolver=_resolver({"x.example": [addr]}))
