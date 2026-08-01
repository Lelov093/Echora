"""Durable worker for accepted Web Conversation turns."""

from __future__ import annotations

import uuid

from app.db.models import Message, TraceRun
from app.services import conversation_application_service, conversation_turn_journal_service
from app.services.conversation_application_service import ConversationTurnContext
from app.services.conversation_service import ConversationTurnError, get_session


def run_scheduler_tick(
    *,
    worker_id: str,
    max_items: int = 1,
    lease_seconds: int = 300,
) -> int:
    """Claim and execute a bounded number of durable async turns."""
    completed = 0
    for _ in range(max(1, max_items)):
        claim = conversation_turn_journal_service.claim_next_async_turn(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
        )
        if claim is None:
            break
        try:
            context, content = _load_claim_context(claim.trace_run_id)
            conversation_application_service._execute_claimed_turn(
                context,
                content,
                claim,
            )
        except Exception as exc:
            try:
                conversation_turn_journal_service.mark_claim_failed(claim.trace_run_id, exc)
            except Exception:
                pass
        completed += 1
    return completed


def _load_claim_context(trace_run_id: uuid.UUID) -> tuple[ConversationTurnContext, str]:
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        message = session.get(Message, trace.message_id) if trace and trace.message_id else None
        if trace is None or message is None or message.deleted_at is not None:
            raise ConversationTurnError(
                "CONVERSATION_TURN_RECOVERY_REQUIRED",
                "The accepted turn no longer has a runnable source claim.",
                {"trace_run_id": str(trace_run_id)},
            )
        metadata = dict(trace.metadata_ or {})
        mode_key = str(metadata.get("turn_mode_key") or "")
        if not mode_key:
            raise ConversationTurnError(
                "CONVERSATION_TURN_RECOVERY_REQUIRED",
                "The accepted turn has no durable mode evidence.",
                {"trace_run_id": str(trace_run_id)},
            )
        return (
            ConversationTurnContext(
                conversation_id=trace.conversation_id,
                user_id=trace.user_id,
                companion_id=trace.companion_id,
                mode_key=mode_key,
            ),
            message.content,
        )
