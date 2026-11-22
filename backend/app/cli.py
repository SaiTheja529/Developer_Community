"""Flask CLI commands: seed, counters rebuild, users set-role, db-upgrade-locked, jobs."""

from __future__ import annotations

import json
import zlib

import click
from flask import Flask
from flask.cli import AppGroup
from sqlalchemy import func, select, text

from app.extensions import db


def seed_reference_data() -> dict:
    """Idempotently insert categories, trusted domains and the system user."""
    from app.modules.meta.models import Category, TrustedDomain
    from app.modules.meta.seed_data import CATEGORIES, TRUSTED_DOMAINS
    from app.modules.reports.service import SYSTEM_USERNAME
    from app.modules.users.models import User

    added = {"categories": 0, "trusted_domains": 0, "system_user": 0}
    for c in CATEGORIES:
        exists = db.session.execute(
            select(Category).where(Category.module == c["module"], Category.slug == c["slug"])
        ).scalar_one_or_none()
        if exists is None:
            db.session.add(Category(**c))
            added["categories"] += 1
    for domain, label in TRUSTED_DOMAINS:
        if db.session.execute(select(TrustedDomain).where(TrustedDomain.domain == domain)).scalar_one_or_none() is None:
            db.session.add(TrustedDomain(domain=domain, kind="official_docs", label=label))
            added["trusted_domains"] += 1
    if db.session.execute(select(User).where(User.username == SYSTEM_USERNAME)).scalar_one_or_none() is None:
        db.session.add(
            User(username=SYSTEM_USERNAME, display_name="DevCommons", role="admin", status="active", email=None)
        )
        added["system_user"] = 1
    db.session.commit()
    return added


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    @click.option("--demo", is_flag=True, help="Also insert sample harnesses, ideas, resources and collections.")
    def seed(demo: bool):
        """Seed categories, trusted domains and the system user (and optional demo content)."""
        click.echo(json.dumps(seed_reference_data()))
        if demo:
            from app.demo_seed import seed_demo

            click.echo(json.dumps(seed_demo()))

    counters = AppGroup("counters", help="Denormalized counter maintenance.")

    @counters.command("rebuild")
    def counters_rebuild():
        """Recompute every denormalized counter from source tables."""
        from app.common.counters import rebuild_all

        rebuild_all()
        click.echo("Counters rebuilt.")

    app.cli.add_command(counters)

    users = AppGroup("users", help="User administration.")

    @users.command("set-role")
    @click.argument("username")
    @click.argument("role", type=click.Choice(["user", "moderator", "admin"]))
    def set_role(username: str, role: str):
        """Make USERNAME a user, moderator or admin."""
        from app.modules.reports.service import SYSTEM_USERNAME, get_system_user, log_action
        from app.modules.users.models import User

        user = db.session.execute(select(User).where(User.username == username.lower())).scalar_one_or_none()
        if user is None or user.status == "deleted":
            raise click.ClickException(f"No user named '{username}'.")
        if user.username == SYSTEM_USERNAME:
            raise click.ClickException("The system user cannot be changed.")
        previous = user.role
        user.role = role
        system = get_system_user()
        if system is not None:
            log_action(system.id, "set_role", "user", user.id, "cli", {"previous_role": previous, "role": role})
        db.session.commit()
        click.echo(f"{username}: {previous} -> {role}")

    @users.command("verify-email")
    @click.argument("username")
    def verify_email(username: str):
        """Mark USERNAME's email as verified (handy in local development)."""
        from app.modules.users.models import User

        user = db.session.execute(select(User).where(User.username == username.lower())).scalar_one_or_none()
        if user is None:
            raise click.ClickException(f"No user named '{username}'.")
        user.email_verified_at = user.email_verified_at or func.now()
        db.session.commit()
        click.echo(f"{username}: email verified")

    app.cli.add_command(users)

    @app.cli.command("db-upgrade-locked")
    def db_upgrade_locked():
        """Run `flask db upgrade` under a Postgres advisory lock so instances don't race."""
        from flask_migrate import upgrade

        key = zlib.crc32(b"devcommons:migrations")
        with db.engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": key})
            conn.commit()
            try:
                upgrade()
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
                conn.commit()
        click.echo("Migrations applied.")

    jobs = AppGroup("jobs", help="Run scheduled jobs locally.")

    @jobs.command("run")
    @click.argument("name", type=click.Choice(["link-check", "refresh-repos", "cleanup", "rebuild-counters"]))
    def run_job(name: str):
        """Run a scheduled job once."""
        from app.modules.jobs import service

        fn = {
            "link-check": service.link_check,
            "refresh-repos": service.refresh_repos,
            "cleanup": service.cleanup,
            "rebuild-counters": service.rebuild_counters,
        }[name]
        with service.advisory_lock(name) as acquired:
            if not acquired:
                raise click.ClickException("Job is already running.")
            click.echo(json.dumps(fn(), default=str))

    app.cli.add_command(jobs)
