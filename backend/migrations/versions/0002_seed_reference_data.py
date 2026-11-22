"""seed categories, trusted domains and the system user (spec §7.3, §7.10)

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Frozen copy of the seed data at the time of this migration (do not import app code in migrations).
CATEGORIES = {
    "harness": [
        ("ai-coding", "AI coding"), ("testing", "Testing"), ("agent-orchestration", "Agent orchestration"),
        ("developer-productivity", "Developer productivity"), ("code-review", "Code review"),
        ("documentation", "Documentation"), ("devops", "DevOps"), ("security", "Security"), ("other", "Other"),
    ],
    "idea": [
        ("ai", "AI"), ("agentic-ai", "Agentic AI"), ("web-development", "Web development"), ("mobile", "Mobile"),
        ("cloud", "Cloud"), ("developer-tools", "Developer tools"), ("data", "Data"), ("devops", "DevOps"),
        ("security", "Security"), ("other", "Other"),
    ],
    "resource": [
        ("java", "Java"), ("python", "Python"), ("javascript-typescript", "JavaScript / TypeScript"), ("ai", "AI"),
        ("agentic-ai", "Agentic AI"), ("cloud", "Cloud"), ("devops", "DevOps"), ("databases", "Databases"),
        ("web", "Web"), ("mobile", "Mobile"), ("security", "Security"), ("other", "Other"),
    ],
}

TRUSTED_DOMAINS = [
    ("docs.python.org", "Python"), ("developer.mozilla.org", "MDN Web Docs"), ("react.dev", "React"),
    ("docs.spring.io", "Spring"), ("platform.openai.com", "OpenAI"), ("docs.anthropic.com", "Anthropic"),
    ("docs.claude.com", "Claude"), ("docs.aws.amazon.com", "AWS"), ("learn.microsoft.com", "Microsoft Learn"),
    ("cloud.google.com", "Google Cloud"), ("kubernetes.io", "Kubernetes"), ("docs.docker.com", "Docker"),
    ("postgresql.org", "PostgreSQL"), ("langchain-ai.github.io", "LangGraph"), ("python.langchain.com", "LangChain"),
    ("docs.github.com", "GitHub"), ("modelcontextprotocol.io", "Model Context Protocol"),
    ("docs.oracle.com", "Java (Oracle)"), ("dev.java", "Java"), ("typescriptlang.org", "TypeScript"),
    ("nodejs.org", "Node.js"), ("go.dev", "Go"), ("doc.rust-lang.org", "Rust"),
    ("docs.djangoproject.com", "Django"), ("flask.palletsprojects.com", "Flask"),
    ("fastapi.tiangolo.com", "FastAPI"), ("docs.sqlalchemy.org", "SQLAlchemy"), ("nextjs.org", "Next.js"),
    ("vuejs.org", "Vue"), ("angular.dev", "Angular"), ("developer.android.com", "Android"),
    ("developer.apple.com", "Apple Developer"), ("terraform.io", "Terraform"),
    ("developer.hashicorp.com", "HashiCorp"), ("redis.io", "Redis"), ("docs.pydantic.dev", "Pydantic"),
    ("git-scm.com", "Git"),
]


def upgrade():
    conn = op.get_bind()
    for module, items in CATEGORIES.items():
        for order, (slug, name) in enumerate(items):
            conn.execute(
                sa.text(
                    "INSERT INTO categories (module, slug, name, sort_order) VALUES (:m, :s, :n, :o) "
                    "ON CONFLICT (module, slug) DO NOTHING"
                ),
                {"m": module, "s": slug, "n": name, "o": order},
            )
    for domain, label in TRUSTED_DOMAINS:
        conn.execute(
            sa.text(
                "INSERT INTO trusted_domains (domain, kind, label) VALUES (:d, 'official_docs', :l) "
                "ON CONFLICT (domain) DO NOTHING"
            ),
            {"d": domain, "l": label},
        )
    # System user: actor for automatic moderation (auto-hide). Has no email/password, so it cannot sign in.
    conn.execute(
        sa.text(
            "INSERT INTO users (username, display_name, role, status) VALUES ('devcommons', 'DevCommons', 'admin', 'active') "
            "ON CONFLICT (username) DO NOTHING"
        )
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM trusted_domains WHERE added_by IS NULL"))
    conn.execute(sa.text("DELETE FROM categories"))
    conn.execute(sa.text("DELETE FROM users WHERE username = 'devcommons' AND email IS NULL"))
