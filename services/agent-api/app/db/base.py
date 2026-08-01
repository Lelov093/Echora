"""SQLAlchemy declarative base with common mixins."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_uuid() -> uuid.UUID:
    """Generate a new UUID4."""
    return uuid.uuid4()


def utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class UUIDMixin:
    """Mixin providing an auto-generated UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """Mixin providing created_at / updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        onupdate=utcnow,
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin providing soft-delete support via deleted_at."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )


class MetadataMixin:
    """Mixin providing a JSONB metadata column.

    SQLAlchemy reserves the name 'metadata' on declarative base;
    we use 'metadata_' as the Python attribute mapped to column 'metadata'.
    """

    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )
