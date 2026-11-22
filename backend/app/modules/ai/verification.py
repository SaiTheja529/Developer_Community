"""URL verification for AI-recommended resources (spec §9.8).

A successful HTTP response is never treated as proof that the content is correct.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime

from app.common.text import host_matches, normalize_url, url_domain
from app.common.url_safety import LinkCheckResult

WORKERS = 8
TOTAL_BUDGET_SECONDS = 15.0
CACHE_TTL_SECONDS = 3600

_cache: dict[str, tuple[float, LinkCheckResult]] = {}
_cache_lock = threading.Lock()


@dataclass
class VerificationResult:
    status: str  # verified_official_domain | reachable_unverified | unreachable | broken | blocked
    http_status: int | None
    final_url: str | None
    checked_at: datetime

    @property
    def reachable(self) -> bool:
        return self.status in ("verified_official_domain", "reachable_unverified")


def registrable(host: str) -> str:
    """Naive registrable domain: last two labels (good enough to compare redirect targets)."""
    parts = host.lower().rstrip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _cached(url: str) -> LinkCheckResult | None:
    key = normalize_url(url)
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.monotonic() - hit[0] < CACHE_TTL_SECONDS:
            return hit[1]
    return None


def _store(url: str, result: LinkCheckResult) -> None:
    with _cache_lock:
        _cache[normalize_url(url)] = (time.monotonic(), result)


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()


def classify(url: str, result: LinkCheckResult, official_domains: list[str]) -> VerificationResult:
    now = datetime.now(UTC)
    if not result.is_success:
        return VerificationResult(result.status, result.http_status, result.final_url, now)
    host = url_domain(url)
    same_site = True
    if result.status == "redirected" and result.final_url:
        same_site = registrable(url_domain(result.final_url)) == registrable(host)
    official = any(host_matches(host, d) for d in official_domains)
    status = "verified_official_domain" if (official and same_site) else "reachable_unverified"
    return VerificationResult(status, result.http_status, result.final_url, now)


def verify_urls(urls: list[str], checker, official_domains: list[str]) -> dict[str, VerificationResult]:
    """Check URLs in parallel (8 workers, 15 s total). URLs not finished in time count as unreachable."""
    unique = list(dict.fromkeys(urls))
    results: dict[str, LinkCheckResult] = {}
    pending = []
    for u in unique:
        hit = _cached(u)
        if hit is not None:
            results[u] = hit
        else:
            pending.append(u)
    if pending:
        pool = ThreadPoolExecutor(max_workers=WORKERS)
        futures = {pool.submit(checker, u): u for u in pending}
        done, _not_done = wait(futures, timeout=TOTAL_BUDGET_SECONDS)
        for fut in done:
            u = futures[fut]
            try:
                res = fut.result()
            except Exception:
                res = LinkCheckResult("unreachable", reason="error")
            results[u] = res
            _store(u, res)
        pool.shutdown(wait=False, cancel_futures=True)
    out = {}
    for u in unique:
        res = results.get(u) or LinkCheckResult("unreachable", reason="timeout")
        out[u] = classify(u, res, official_domains)
    return out
