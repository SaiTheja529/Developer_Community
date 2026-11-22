"""Profiles, username rules and public stats (spec §8.2)."""

from __future__ import annotations

import re

from sqlalchemy import func, select

from app.common import enums
from app.extensions import db
from app.modules.users.models import User

_USERNAME_RE = re.compile(enums.USERNAME_PATTERN)


def username_problem(username: str, exclude_user_id=None) -> str | None:
    """Returns 'invalid' | 'reserved' | 'taken' | None."""
    if not username or not _USERNAME_RE.match(username):
        return "invalid"
    if username in enums.RESERVED_USERNAMES or username.startswith("deleted_"):
        return "reserved"
    stmt = select(User.id).where(User.username == username)
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    if db.session.execute(stmt).first():
        return "taken"
    return None


def me_profile(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "skills": user.skills or [],
        "interests": user.interests or [],
        "website_url": user.website_url,
        "github_username": user.github_username,
        "contact_links": user.contact_links or [],
        "contact_visibility": user.contact_visibility,
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "has_password": user.password_hash is not None,
        "role": user.role,
        "status": user.status,
        "joined_at": user.created_at,
        "created_at": user.created_at,
    }


def user_stats(user_id) -> dict:
    from app.modules.collections.models import Collection
    from app.modules.comments.models import Comment
    from app.modules.harnesses.models import Harness, HarnessReview
    from app.modules.ideas.models import Idea
    from app.modules.resources.models import Resource

    def count(model, owner_col, extra=None):
        stmt = select(func.count()).select_from(model).where(
            owner_col == user_id, model.deleted_at.is_(None), model.status == "published"
        )
        if extra is not None:
            stmt = stmt.where(extra)
        return db.session.execute(stmt).scalar_one()

    return {
        "harnesses": count(Harness, Harness.author_id),
        "ideas": count(Idea, Idea.author_id),
        "resources": count(Resource, Resource.submitter_id),
        "collections": count(Collection, Collection.owner_id, Collection.visibility == "public"),
        "reviews": count(HarnessReview, HarnessReview.author_id),
        "comments": count(Comment, Comment.author_id),
    }


def public_profile(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "bio": user.bio,
        "skills": user.skills or [],
        "interests": user.interests or [],
        "website_url": user.website_url,
        "github_username": user.github_username,
        "contact_links": (user.contact_links or []) if user.contact_visibility == "public" else [],
        "is_deleted": user.status == "deleted",
        "joined_at": user.created_at,
        "stats": user_stats(user.id),
    }


def update_me(user: User, body) -> User:
    from app.common.errors import ApiError, validation_error

    data = body.model_dump(exclude_unset=True)
    if "username" in data:
        new = data["username"].strip().lower()
        if new != user.username:
            problem = username_problem(new, exclude_user_id=user.id)
            if problem == "taken":
                raise ApiError("username_taken", "This username is taken.", 409)
            if problem:
                raise validation_error({"username": f"Username is {problem}."})
            user.username = new
        data.pop("username")
    if "contact_links" in data:
        data["contact_links"] = [dict(link) for link in data["contact_links"]]
    for key, value in data.items():
        setattr(user, key, value)
    db.session.commit()
    return user
