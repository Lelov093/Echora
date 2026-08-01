"""Agent execution provider, prompt, call, and fallback models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Double, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class LlmProviderConfig(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "llm_provider_configs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"))
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    provider_type: Mapped[str] = mapped_column(Text, default="llm")
    status: Mapped[str] = mapped_column(Text, default="enabled")
    base_url: Mapped[str | None] = mapped_column(Text)
    env_key_name: Mapped[str | None] = mapped_column(Text)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LlmModelConfig(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "llm_model_configs"

    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_provider_configs.id"))
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_role: Mapped[str] = mapped_column(Text, default="response_generation")
    status: Mapped[str] = mapped_column(Text, default="enabled")
    temperature: Mapped[float | None] = mapped_column(Double)
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PromptVersion(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "prompt_versions"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"))
    prompt_key: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="draft")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_note: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LlmCallRecord(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "llm_call_records"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    trace_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_steps.id"))
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_provider_configs.id"))
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_model_configs.id"))
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("prompt_versions.id"))
    status: Mapped[str] = mapped_column(Text, default="queued")
    purpose: Mapped[str] = mapped_column(Text, default="response_generation")
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    token_input: Mapped[int | None] = mapped_column(Integer)
    token_output: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    fallback_used: Mapped[bool] = mapped_column(Boolean, default=False)
    error_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FallbackEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "fallback_events"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    llm_call_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_call_records.id"))
    from_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_provider_configs.id"))
    to_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("llm_provider_configs.id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="recorded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
