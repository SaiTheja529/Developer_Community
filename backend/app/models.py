"""Import every model so Alembic autogenerate and `db.create_all()` see the full schema."""

from app.auth.models import AuthSession, EmailToken  # noqa: F401
from app.integrations.models import GithubRepoCache  # noqa: F401
from app.modules.ai.models import AIConversation, AIDraft, AIMessage, AIUsage  # noqa: F401
from app.modules.collaborations.models import CollaborationRequest  # noqa: F401
from app.modules.collections.models import Collection, CollectionItem  # noqa: F401
from app.modules.comments.models import Comment  # noqa: F401
from app.modules.harnesses.models import Harness, HarnessReview  # noqa: F401
from app.modules.ideas.models import Idea  # noqa: F401
from app.modules.meta.models import Category, TrustedDomain  # noqa: F401
from app.modules.notifications.models import Notification  # noqa: F401
from app.modules.reports.models import ModerationAction, Report  # noqa: F401
from app.modules.resources.models import Resource  # noqa: F401
from app.modules.suggestions.models import Suggestion  # noqa: F401
from app.modules.users.models import User  # noqa: F401
from app.modules.votes.models import Bookmark, Vote  # noqa: F401
