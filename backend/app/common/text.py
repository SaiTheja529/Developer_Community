"""Text helpers: cleaning, tags, slugs, URL validation and normalization (spec §5.6, §7.7)."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TAG_RE = re.compile(r"^[a-z0-9.+#-]{1,30}$")
_TRACKING_PARAMS = {"ref", "fbclid", "gclid"}
MAX_URL_LENGTH = 2048


def clean_text(value):
    """Strip control chars (except \\n and \\t), normalize newlines, trim."""
    if value is None or not isinstance(value, str):
        return value
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _CONTROL_RE.sub("", value)
    return value.strip()


def clean_optional(value):
    value = clean_text(value)
    if isinstance(value, str) and value == "":
        return None
    return value


def normalize_tag(raw: str) -> str:
    tag = clean_text(raw or "").lower()
    tag = re.sub(r"\s+", "-", tag)
    tag = re.sub(r"-{2,}", "-", tag).strip("-")
    if not _TAG_RE.match(tag):
        raise ValueError(f"Invalid tag '{raw}'. Use 1-30 characters from a-z, 0-9, '.', '+', '#', '-'.")
    return tag


def normalize_tags(values, max_items: int = 8) -> list[str]:
    if values is None:
        return []
    out: list[str] = []
    for v in values:
        t = normalize_tag(str(v))
        if t not in out:
            out.append(t)
    if len(out) > max_items:
        raise ValueError(f"At most {max_items} items allowed.")
    return out


def try_normalize_tags(values, max_items: int = 8) -> list[str]:
    """Best-effort normalization used for AI output: drop invalid tags instead of failing."""
    out: list[str] = []
    for v in values or []:
        try:
            t = normalize_tag(str(v))
        except ValueError:
            continue
        if t not in out:
            out.append(t)
    return out[:max_items]


def slugify(value: str, max_len: int = 80) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    value = value[:max_len].strip("-")
    return value or "item"


def snippet(text: str | None, n: int = 140) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def validate_http_url(value: str) -> str:
    """http(s) only, ≤ 2048 chars, must parse cleanly with a host."""
    value = clean_text(value or "")
    if not value:
        raise ValueError("URL is required.")
    if len(value) > MAX_URL_LENGTH:
        raise ValueError("URL must be at most 2048 characters.")
    if any(c.isspace() for c in value):
        raise ValueError("URL must not contain whitespace.")
    try:
        parts = urlsplit(value)
        _ = parts.port  # raises on invalid port
    except ValueError as e:
        raise ValueError("URL is not valid.") from e
    if parts.scheme.lower() not in ("http", "https"):
        raise ValueError("URL must start with http:// or https://.")
    if not parts.hostname:
        raise ValueError("URL must include a host.")
    return value


def url_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def normalize_url(url: str) -> str:
    """Normalized form for duplicate detection: host + path + ?sorted_query (no scheme)."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    port = parts.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parts.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/") or "/"
    params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    ]
    params.sort()
    query = urlencode(params)
    normalized = host + path
    if path == "/" and not query:
        normalized = host + "/"
    if query:
        normalized += "?" + query
    return normalized


def canonical_url(url: str) -> str:
    """Rebuild a URL from parts (used for display/storage of cleaned URLs)."""
    p = urlsplit(url)
    return urlunsplit((p.scheme.lower(), p.netloc, p.path, p.query, ""))


def host_matches(host: str, domain: str) -> bool:
    host = host.lower().rstrip(".")
    domain = domain.lower().rstrip(".")
    return host == domain or host.endswith("." + domain)
