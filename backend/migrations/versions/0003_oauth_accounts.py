"""oauth_accounts: GitHub / Google sign-in

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_user_id", sa.Text(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("login", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("provider IN ('github','google')", name=op.f("ck_oauth_accounts_provider")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_oauth_accounts_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_accounts")),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_accounts_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_oauth_accounts_user_provider"),
    )
    op.create_index(op.f("ix_oauth_accounts_user_id"), "oauth_accounts", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_oauth_accounts_user_id"), table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
