"""FastAPI dependency injection helpers."""

from app.core.config import settings


def get_default_user_id() -> str:
    """Placeholder: return a default user ID from seed data.

    Core conversation uses a single local user; this will be replaced with auth later.
    """
    return ""  # populated at runtime by routes


def get_default_companion_id() -> str:
    """Placeholder: return a default companion ID from seed data."""
    return ""
