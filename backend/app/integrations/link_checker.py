"""Applies SSRF-safe link checks to resources, with flap protection (spec §10.2)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.common.url_safety import LinkCheckResult, safe_check

FAILURE_THRESHOLD = 2
BOT_BLOCK_STATUSES = (401, 403, 429)


def check_url(url: str) -> LinkCheckResult:
    from flask import current_app

    checker = current_app.extensions.get("link_checker", safe_check)
    return checker(url)


def apply_result(resource, result: LinkCheckResult) -> bool:
    """Update the resource's link fields. Returns True when the link newly became broken."""
    now = datetime.now(UTC)
    previous = resource.link_status
    resource.link_last_checked_at = now
    resource.link_http_status = result.http_status

    if result.is_success:
        resource.link_status = result.status
        resource.link_final_url = result.final_url
        resource.link_consecutive_failures = 0
        resource.link_broken_since = None
        return False

    if result.status == "blocked":
        resource.link_status = "blocked"
        resource.link_consecutive_failures = 0
        return False

    resource.link_consecutive_failures = (resource.link_consecutive_failures or 0) + 1
    if resource.link_consecutive_failures < FAILURE_THRESHOLD:
        return False  # a single failure keeps the previous status

    resource.link_status = result.status
    bot_blocked = result.http_status in BOT_BLOCK_STATUSES
    if bot_blocked:
        resource.link_broken_since = None  # sites that block bots are not hidden from listings
    elif resource.link_broken_since is None:
        resource.link_broken_since = now
    return result.status == "broken" and previous != "broken"
