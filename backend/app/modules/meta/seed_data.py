"""Seed data for categories and trusted domains (spec §7.3). Used by the data migration and `flask seed`."""

from __future__ import annotations


def _title(slug: str) -> str:
    special = {
        "ai": "AI",
        "agentic-ai": "Agentic AI",
        "ai-coding": "AI coding",
        "devops": "DevOps",
        "javascript-typescript": "JavaScript / TypeScript",
        "web-development": "Web development",
        "developer-tools": "Developer tools",
        "developer-productivity": "Developer productivity",
        "agent-orchestration": "Agent orchestration",
        "code-review": "Code review",
    }
    return special.get(slug, slug.replace("-", " ").capitalize())


CATEGORY_SLUGS = {
    "harness": [
        "ai-coding",
        "testing",
        "agent-orchestration",
        "developer-productivity",
        "code-review",
        "documentation",
        "devops",
        "security",
        "other",
    ],
    "idea": [
        "ai",
        "agentic-ai",
        "web-development",
        "mobile",
        "cloud",
        "developer-tools",
        "data",
        "devops",
        "security",
        "other",
    ],
    "resource": [
        "java",
        "python",
        "javascript-typescript",
        "ai",
        "agentic-ai",
        "cloud",
        "devops",
        "databases",
        "web",
        "mobile",
        "security",
        "other",
    ],
}

CATEGORIES = [
    {"module": module, "slug": slug, "name": _title(slug), "sort_order": i}
    for module, slugs in CATEGORY_SLUGS.items()
    for i, slug in enumerate(slugs)
]

TRUSTED_DOMAINS = [
    ("docs.python.org", "Python"),
    ("developer.mozilla.org", "MDN Web Docs"),
    ("react.dev", "React"),
    ("docs.spring.io", "Spring"),
    ("platform.openai.com", "OpenAI"),
    ("docs.anthropic.com", "Anthropic"),
    ("docs.claude.com", "Claude"),
    ("docs.aws.amazon.com", "AWS"),
    ("learn.microsoft.com", "Microsoft Learn"),
    ("cloud.google.com", "Google Cloud"),
    ("kubernetes.io", "Kubernetes"),
    ("docs.docker.com", "Docker"),
    ("postgresql.org", "PostgreSQL"),
    ("langchain-ai.github.io", "LangGraph"),
    ("python.langchain.com", "LangChain"),
    ("docs.github.com", "GitHub"),
    ("modelcontextprotocol.io", "Model Context Protocol"),
    ("docs.oracle.com", "Java (Oracle)"),
    ("dev.java", "Java"),
    ("typescriptlang.org", "TypeScript"),
    ("nodejs.org", "Node.js"),
    ("go.dev", "Go"),
    ("doc.rust-lang.org", "Rust"),
    ("docs.djangoproject.com", "Django"),
    ("flask.palletsprojects.com", "Flask"),
    ("fastapi.tiangolo.com", "FastAPI"),
    ("docs.sqlalchemy.org", "SQLAlchemy"),
    ("nextjs.org", "Next.js"),
    ("vuejs.org", "Vue"),
    ("angular.dev", "Angular"),
    ("developer.android.com", "Android"),
    ("developer.apple.com", "Apple Developer"),
    ("terraform.io", "Terraform"),
    ("developer.hashicorp.com", "HashiCorp"),
    ("redis.io", "Redis"),
    ("docs.pydantic.dev", "Pydantic"),
    ("git-scm.com", "Git"),
]
