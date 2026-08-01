"""TraceRun and TraceStep models."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, MetadataMixin, Base


class TraceRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "trace_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )

    agent_graph_name: Mapped[str] = mapped_column(String(100), default="conversation_graph")
    model_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="completed")
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    retrieved_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    selected_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    generated_memory_candidate_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    generated_growth_candidate_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    generated_presence_opportunity_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )

    # Agent execution: trace-level signal references
    tool_run_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    file_context_usage_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    evidence_sufficiency_event_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    memory_reranker_run_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    presence_policy_run_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    bad_case_signal_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    evaluation_signal_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    llm_call_record_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    execution_signal_summary: Mapped[dict] = mapped_column(
        "trace_v3_summary", JSONB, default=dict, server_default="{}"
    )

    # Realtime compatibility: realtime co-presence trace binding
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    realtime_trace_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_trace_sessions.id"), nullable=True
    )


class TraceStep(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "trace_steps"

    trace_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id", ondelete="CASCADE"), nullable=False
    )

    step_name: Mapped[str] = mapped_column(String(200), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="completed")

    input_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    score_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Continuity: calibration / impact ───────────────────────────────
    calibration_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    feedback_event_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    memory_usage_event_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    lifecycle_event_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    impact_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    user_visible_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Agent execution: step-level signal payloads
    tool_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    file_context_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    reranker_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    presence_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    bad_case_signal_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    evaluation_signal_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    provider_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    outdated_memory_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    growth_consistency_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # Realtime compatibility: realtime co-presence trace payloads
    realtime_copresence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    participant_permission_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    realtime_memory_gate_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
