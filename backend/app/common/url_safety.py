"""SSRF-safe URL checks (spec §10.2).

Every server-side fetch of a user-provided URL goes through this module.
"""

from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

USER_AGENT = "DevCommons-LinkChecker/1.0"
MAX_REDIRECTS = 3
TOTAL_BUDGET_SECONDS = 10.0
MAX_BODY_BYTES = 64 * 1024


class UrlBlocked(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class LinkCheckResult:
    status: str  # ok | redirected | broken | unreachable | blocked
    http_status: int | None = None
    final_url: str | None = None
    reason: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status in ("ok", "redirected")


_NAT64 = ipaddress.ip_network("64:ff9b::/96")


def _embedded_ipv4(ip: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """IPv4 carried inside IPv4-mapped, NAT64 (64:ff9b::/96), 6to4 or Teredo addresses."""
    if ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    if ip in _NAT64:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if ip.sixtofour is not None:
        return ip.sixtofour
    if ip.teredo is not None:
        return ip.teredo[1]
    return None


def _ip_is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address):
        embedded = _embedded_ipv4(ip)
        if embedded is not None:
            ip = embedded
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"))
    )


def resolve_host(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return list({info[4][0] for info in infos})


# Swappable resolver (tests replace it so they never depend on real DNS).
RESOLVER = resolve_host


def assert_url_allowed(url: str, resolver=None) -> None:
    """Steps 1-2: scheme/port checks, then every resolved IP must be public."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as e:
        raise UrlBlocked("invalid_url") from e
    if parts.scheme.lower() not in ("http", "https"):
        raise UrlBlocked("scheme_not_allowed")
    if port not in (None, 80, 443):
        raise UrlBlocked("port_not_allowed")
    host = parts.hostname
    if not host:
        raise UrlBlocked("invalid_url")
    if host.lower() in ("localhost",) or host.lower().endswith(".localhost") or host.lower().endswith(".internal"):
        raise UrlBlocked("private_address")
    # Literal IP?
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        if not _ip_is_public(literal):
            raise UrlBlocked("private_address")
        return
    try:
        ips = (resolver or RESOLVER)(host)
    except (socket.gaierror, UnicodeError, OSError) as e:
        raise UrlBlocked("dns_failure") from e
    if not ips:
        raise UrlBlocked("dns_failure")
    for ip in ips:
        try:
            addr = ipaddress.ip_address(ip.split("%")[0])
        except ValueError as e:
            raise UrlBlocked("private_address") from e
        if not _ip_is_public(addr):
            raise UrlBlocked("private_address")


def static_block_reason(url: str) -> str | None:
    """Like assert_url_allowed but returns the reason instead of raising. DNS failures are not 'blocked'."""
    try:
        assert_url_allowed(url)
    except UrlBlocked as e:
        if e.reason == "dns_failure":
            return None
        return e.reason
    return None


def _classify(status: int) -> str:
    if 200 <= status < 300:
        return "ok"
    if status in (404, 410):
        return "broken"
    return "unreachable"


def safe_check(url: str, *, client: httpx.Client | None = None, resolver=None) -> LinkCheckResult:
    deadline = time.monotonic() + TOTAL_BUDGET_SECONDS
    own_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=httpx.Timeout(5.0, connect=3.0),
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
        )
    current = url
    try:
        for _hop in range(MAX_REDIRECTS + 1):
            try:
                assert_url_allowed(current, resolver=resolver)
            except UrlBlocked as e:
                if e.reason == "dns_failure":
                    return LinkCheckResult("unreachable", reason="dns_failure")
                return LinkCheckResult("blocked", reason=e.reason)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return LinkCheckResult("unreachable", reason="timeout")
            try:
                resp = client.request("HEAD", current, timeout=min(remaining, 5.0))
                if resp.status_code in (403, 405, 501):
                    with client.stream("GET", current, timeout=min(max(deadline - time.monotonic(), 0.1), 5.0)) as r:
                        read = 0
                        for chunk in r.iter_bytes():
                            read += len(chunk)
                            if read >= MAX_BODY_BYTES:
                                break
                        resp = r
            except httpx.TimeoutException:
                return LinkCheckResult("unreachable", reason="timeout")
            except httpx.HTTPError:
                return LinkCheckResult("unreachable", reason="connection_error")

            status = resp.status_code
            if 300 <= status < 400 and resp.headers.get("location"):
                current = urljoin(current, resp.headers["location"])
                continue
            result = _classify(status)
            if result == "ok" and current != url:
                return LinkCheckResult("redirected", http_status=status, final_url=current)
            return LinkCheckResult(result, http_status=status, final_url=current if current != url else None)
        return LinkCheckResult("unreachable", reason="too_many_redirects")
    finally:
        if own_client:
            client.close()
