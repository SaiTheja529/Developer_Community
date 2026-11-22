"""Single source of truth for enum value lists and field limits (spec §7.1, §7.12).

Exported to the frontend via GET /api/meta/config.
"""

from __future__ import annotations

ROLES = ["user", "moderator", "admin"]
USER_STATUSES = ["active", "suspended", "deleted"]
CONTACT_VISIBILITY = ["hidden", "collaborators", "public"]
CONTENT_STATUSES = ["published", "hidden", "removed"]
SESSION_REVOKE_REASONS = [
    "logout",
    "logout_all",
    "password_change",
    "password_reset",
    "suspended",
    "reuse_detected",
    "admin",
]
EMAIL_TOKEN_PURPOSES = ["verify_email", "reset_password", "change_email"]
OAUTH_PROVIDERS = ["github", "google"]

CATEGORY_MODULES = ["harness", "idea", "resource"]
TRUSTED_DOMAIN_KINDS = ["official_docs", "reputable"]

TOOLS = [
    "claude_code",
    "github_copilot",
    "cursor",
    "devin",
    "openai_codex",
    "windsurf",
    "cline",
    "aider",
    "gemini_cli",
    "other",
]
COMPONENT_TYPES = [
    "rule",
    "instruction_file",
    "agent",
    "subagent",
    "skill",
    "hook",
    "mcp_server",
    "slash_command",
    "workflow",
    "other",
]
COLLABORATION_STATUSES = ["sharing", "seeking_collaborators", "team_formed"]
RESOURCE_TYPES = [
    "official_docs",
    "tutorial",
    "article",
    "guide",
    "video",
    "course",
    "book",
    "repository",
    "tool",
    "other",
]
RESOURCE_LEVELS = ["beginner", "intermediate", "advanced"]
LINK_STATUSES = ["pending", "ok", "redirected", "broken", "unreachable", "blocked"]
COLLECTION_VISIBILITY = ["public", "private"]

SUGGESTION_KINDS = {
    "harness": ["improvement", "bug_report", "component_recommendation"],
    "idea": ["feature", "tech_stack", "architecture"],
    "resource": ["alternative_resource", "correction"],
}
SUGGESTION_STATUSES = ["open", "acknowledged", "planned", "implemented", "declined"]

VOTE_TARGETS = ["harness", "idea", "resource", "collection", "comment", "suggestion", "review"]
VOTE_KINDS = ["upvote", "interest"]
BOOKMARK_TARGETS = ["harness", "idea", "resource", "collection"]
COMMENT_TARGETS = ["harness", "idea", "resource", "collection"]
SUGGESTION_TARGETS = ["harness", "idea", "resource"]

COLLAB_STATUSES = ["pending", "accepted", "declined", "withdrawn"]

REPORT_TARGETS = [
    "harness",
    "idea",
    "resource",
    "collection",
    "comment",
    "suggestion",
    "review",
    "user",
    "ai_message",
    "ai_draft",
]
REPORT_REASONS = [
    "spam",
    "abuse",
    "broken_link",
    "outdated",
    "misleading",
    "inaccurate_ai",
    "unsafe_ai",
    "copyright",
    "privacy",
    "other",
]
REPORT_STATUSES = ["open", "resolved", "dismissed"]
MODERATE_ACTIONS = ["hide", "restore", "remove", "feature", "unfeature"]

NOTIFICATION_TYPES = [
    "comment_on_content",
    "reply_to_comment",
    "suggestion_on_content",
    "suggestion_status_changed",
    "review_on_harness",
    "collab_request_received",
    "collab_request_accepted",
    "collab_request_declined",
    "content_moderated",
    "resource_link_broken",
]

AI_CONTEXT_TYPES = ["harness", "idea", "resource", "collection"]
AI_MESSAGE_STATUSES = ["streaming", "complete", "cancelled", "error"]
AI_DRAFT_TASKS = ["harness_doc", "project_idea", "resource_recommendations", "feedback_suggestions"]
AI_DRAFT_STATUSES = ["draft", "published", "discarded"]
AI_USAGE_OUTCOMES = ["success", "error", "timeout", "cancelled", "rate_limited"]
AI_REFINE_ACTIONS = [
    "clarity",
    "rewrite",
    "expand",
    "organize",
    "setup_steps",
    "complete_proposal",
    "architecture",
    "custom",
]
AI_FEEDBACK_CATEGORIES = [
    "missing_feature",
    "architecture",
    "testing",
    "documentation",
    "security",
    "maintainability",
]
AI_VERIFICATION_STATUSES = ["verified_hub", "verified_official_domain", "reachable_unverified"]

RESERVED_USERNAMES = {
    "admin",
    "api",
    "me",
    "settings",
    "new",
    "edit",
    "devcommons",
    "support",
    "moderator",
    "null",
    "undefined",
}
USERNAME_PATTERN = r"^[a-z0-9][a-z0-9_-]{2,29}$"

LIMITS = {
    "tags": {"max_items": 8, "item_min": 1, "item_max": 30, "pattern": "^[a-z0-9.+#-]{1,30}$"},
    "username": {"min": 3, "max": 30, "pattern": USERNAME_PATTERN},
    "display_name": {"min": 1, "max": 60},
    "password": {"min": 10, "max": 128},
    "bio": {"max": 500},
    "skills": {"max_items": 15},
    "interests": {"max_items": 15},
    "contact_links": {"max_items": 5, "label_max": 40},
    "url": {"max": 2048},
    "harness": {
        "name": {"min": 3, "max": 100},
        "short_description": {"min": 20, "max": 280},
        "detailed_explanation": {"min": 50, "max": 20000},
        "architecture": {"max": 20000},
        "setup_instructions": {"max": 20000},
        "limitations": {"max": 10000},
        "components": {"max_items": 50},
        "component_name": {"min": 1, "max": 100},
        "component_description": {"max": 2000},
        "tools": {"min_items": 1, "max_items": 10},
    },
    "review": {
        "what_tested": {"min": 20, "max": 5000},
        "worked_well": {"max": 5000},
        "did_not_work": {"max": 5000},
        "recommendations": {"max": 5000},
        "environment": {"max": 500},
        "rating": {"min": 1, "max": 5},
    },
    "idea": {
        "title": {"min": 5, "max": 120},
        "problem_statement": {"min": 20, "max": 5000},
        "proposed_solution": {"min": 20, "max": 5000},
        "description": {"max": 20000},
        "tech_stack": {"max_items": 20},
        "expected_features": {"max_items": 30},
        "feature_title": {"min": 1, "max": 150},
        "feature_detail": {"max": 2000},
    },
    "resource": {"name": {"min": 3, "max": 150}, "description": {"min": 20, "max": 3000}},
    "collection": {
        "title": {"min": 3, "max": 120},
        "description": {"max": 5000},
        "items": {"max_items": 100},
        "item_note": {"max": 500},
    },
    "comment": {"body": {"min": 1, "max": 10000}, "edit_window_days": 7},
    "suggestion": {"title": {"min": 5, "max": 150}, "body": {"min": 10, "max": 10000}, "owner_response": {"max": 2000}},
    "collaboration": {"message": {"min": 20, "max": 2000}, "skills": {"max_items": 10}, "response_message": {"max": 1000}},
    "report": {"details": {"max": 1000}},
    "ai": {"refine_text": {"max": 20000}, "refine_instruction": {"max": 500}, "additional_context": {"max": 4000}},
    "page_size": {"default": 20, "max": 50},
}

SORTS = {
    "harnesses": ["recent", "popular", "trending", "most_reviewed", "most_discussed"],
    "ideas": ["recent", "popular", "trending", "most_interest", "most_discussed"],
    "resources": ["recent", "popular", "trending"],
    "collections": ["recent", "popular", "trending"],
    "comments": ["oldest", "newest", "top"],
    "suggestions": ["top", "recent"],
    "reviews": ["helpful", "recent"],
}
