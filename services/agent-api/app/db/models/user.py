"""User model."""

import uuid

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin, Base


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin):
    __tablename__ = "users"

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), default="America/Los_Angeles")
    locale: Mapped[str] = mapped_column(String(10), default="zh-CN")
