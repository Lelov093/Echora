"""Durable idempotency claims and replay snapshots for Conversation turns."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select, text

from app.db.models import Message, TraceRun
from app.services.conversation_service import ConversationTurnError, get_session


@dataclass(frozen=True)
class ConversationTurnClaim:
    idempotency_key: str
    user_message_id: uuid.UUID
    trace_run_id: uuid.UUID
    replay_response: dict[str, Any] | None = None
    existing_claim: bool = False
    transport_mode: str = "sync"
    reasoning_mode: str = "auto"


TURN_RUNTIME_CONTRACT_VERSION = "conversation-turn-runtime.v1"
TURN_RUNTIME_STATUSES = {
    "accepted",
    "context_preparing",
    "provider_waiting",
    "streaming",
    "response_persisted",
    "effects_processing",
    "completed",
    "failed",
    "cancellation_requested",
    "cancelled",
}
TURN_RUNTIME_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
TURN_RUNTIME_TRANSITIONS = {
    "accepted": {"context_preparing", "cancellation_requested", "failed", "cancelled"},
    "context_preparing": {"provider_waiting", "cancellation_requested", "failed", "cancelled"},
    "provider_waiting": {"streaming", "response_persisted", "cancellation_requested", "failed", "cancelled"},
    "streaming": {"response_persisted", "cancellation_requested", "failed", "cancelled"},
    "response_persisted": {"effects_processing", "completed", "failed"},
    "effects_processing": {"completed", "failed"},
    "cancellation_requested": {"cancelled", "response_persisted", "completed", "failed"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def claim_turn(
    *,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    mode_key: str,
    content: str,
    requested_key: str | None,
    turn_contract_version: str,
    transport_mode: str = "sync",
    allow_incomplete_replay: bool = False,
    continuation_of_trace_run_id: uuid.UUID | None = None,
    reasoning_mode: str = "auto",
) -> ConversationTurnClaim:
    key = normalize_idempotency_key(requested_key)
    request_hash = _turn_request_hash(
        conversation_id,
        companion_id,
        mode_key,
        reasoning_mode,
        content,
        continuation_of_trace_run_id,
    )
    lock_id = int.from_bytes(
        hashlib.sha256(f"{conversation_id}:{key}".encode("utf-8")).digest()[:8],
        "big",
        signed=True,
    )
    with get_session() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        existing_message = session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.role == "user",
                Message.metadata_["turn_idempotency_key"].astext == key,
            ).limit(1)
        ).scalar_one_or_none()
        if existing_message is not None:
            trace = session.execute(
                select(TraceRun).where(TraceRun.message_id == existing_message.id).limit(1)
            ).scalar_one_or_none()
            if trace is None:
                raise ConversationTurnError(
                    "CONVERSATION_TURN_RECOVERY_REQUIRED",
                    "The previous turn claim has no Trace and requires recovery.",
                    {"idempotency_key": key},
                )
            metadata = dict(trace.metadata_ or {})
            if metadata.get("turn_request_hash") != request_hash:
                raise ConversationTurnError(
                    "CONVERSATION_IDEMPOTENCY_CONFLICT",
                    "The idempotency key was already used for different turn content.",
                    {"idempotency_key": key, "trace_run_id": str(trace.id)},
                )
            response = metadata.get("turn_response_json")
            if response:
                existing_transport = str(((metadata.get("turn_transport") or {}).get("mode")) or "sync")
                return ConversationTurnClaim(
                    key,
                    existing_message.id,
                    trace.id,
                    response,
                    True,
                    existing_transport,
                    str(metadata.get("turn_reasoning_mode") or "auto"),
                )
            if allow_incomplete_replay:
                existing_transport = str(((metadata.get("turn_transport") or {}).get("mode")) or "sync")
                return ConversationTurnClaim(
                    key,
                    existing_message.id,
                    trace.id,
                    None,
                    True,
                    existing_transport,
                    str(metadata.get("turn_reasoning_mode") or "auto"),
                )
            raise ConversationTurnError(
                "CONVERSATION_TURN_RECOVERY_REQUIRED",
                "The previous turn did not reach a replayable response and requires recovery.",
                {
                    "idempotency_key": key,
                    "trace_run_id": str(trace.id),
                    "trace_status": trace.status,
                },
            )

        if continuation_of_trace_run_id is not None:
            interrupted_trace = session.get(TraceRun, continuation_of_trace_run_id)
            interrupted_transport = dict(((interrupted_trace.metadata_ or {}).get("turn_transport") or {})) if interrupted_trace else {}
            if (
                interrupted_trace is None
                or interrupted_trace.conversation_id != conversation_id
                or interrupted_trace.companion_id != companion_id
                or interrupted_transport.get("lifecycle_status") != "cancelled"
            ):
                raise ConversationTurnError(
                    "CONVERSATION_CONTINUATION_SOURCE_INVALID",
                    "A continuation must reference a cancelled turn in the same Conversation and Companion scope.",
                    {"continuation_of_trace_run_id": str(continuation_of_trace_run_id)},
                )

        user_message = Message(
            user_id=user_id,
            companion_id=companion_id,
            conversation_id=conversation_id,
            role="user",
            content=content,
            metadata_={
                "turn_idempotency_key": key,
                "turn_request_hash": request_hash,
                "created_by": "conversation_application_service",
                "continuation_of_trace_run_id": str(continuation_of_trace_run_id) if continuation_of_trace_run_id else None,
                "reasoning_mode": reasoning_mode,
            },
        )
        session.add(user_message)
        session.flush()
        now = datetime.now(timezone.utc)
        trace_metadata = {
            "turn_idempotency_key": key,
            "turn_request_hash": request_hash,
            "turn_contract_version": turn_contract_version,
            "turn_mode_key": mode_key,
            "turn_reasoning_mode": reasoning_mode,
            "continuation_of_trace_run_id": str(continuation_of_trace_run_id) if continuation_of_trace_run_id else None,
        }
        if transport_mode == "async_web":
            trace_metadata["turn_transport"] = {
                "contract_version": TURN_RUNTIME_CONTRACT_VERSION,
                "mode": transport_mode,
                "lifecycle_status": "accepted",
                "accepted_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "attempt_count": 0,
                "lease": {},
                "stage_timings": [],
                "provider_timing": {},
            }
        trace = TraceRun(
            user_id=user_id,
            companion_id=companion_id,
            conversation_id=conversation_id,
            message_id=user_message.id,
            agent_graph_name="conversation_graph",
            status="started",
            input_summary=content[:200],
            metadata_=trace_metadata,
        )
        session.add(trace)
        session.commit()
        return ConversationTurnClaim(
            key,
            user_message.id,
            trace.id,
            transport_mode=transport_mode,
            reasoning_mode=reasoning_mode,
        )


def prepare_provider_retry(
    *,
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
    trace_run_id: uuid.UUID,
) -> tuple[ConversationTurnClaim, str]:
    """Claim a failed Provider attempt without creating a second user message."""
    lock_id = int.from_bytes(
        hashlib.sha256(f"provider-retry:{trace_run_id}".encode("utf-8")).digest()[:8],
        "big",
        signed=True,
    )
    with get_session() as session:
        session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        trace = session.get(TraceRun, trace_run_id)
        if (
            trace is None
            or trace.conversation_id != conversation_id
            or trace.companion_id != companion_id
        ):
            raise ConversationTurnError(
                "CONVERSATION_TURN_NOT_FOUND",
                "The failed Conversation turn was not found in this Companion scope.",
            )
        if trace.status != "failed":
            raise ConversationTurnError(
                "CONVERSATION_TURN_NOT_RETRYABLE",
                "Only a failed Provider turn can be retried.",
                {"trace_status": trace.status},
            )
        message = session.get(Message, trace.message_id) if trace.message_id else None
        if (
            message is None
            or message.deleted_at is not None
            or message.role != "user"
            or message.conversation_id != conversation_id
            or message.companion_id != companion_id
        ):
            raise ConversationTurnError(
                "CONVERSATION_TURN_NOT_RETRYABLE",
                "The failed turn no longer has an active source message.",
            )
        metadata = dict(trace.metadata_ or {})
        response = metadata.get("turn_response_json") or {}
        response_status = (((response.get("turn") or {}).get("response") or {}).get("status"))
        run_errors = response.get("_run_errors") or []
        provider_failed = response_status == "provider_failed" or any(
            item.get("step") == "response_generation" for item in run_errors
        )
        if not provider_failed:
            raise ConversationTurnError(
                "CONVERSATION_TURN_NOT_RETRYABLE",
                "The failed turn was not caused by Provider response generation.",
            )
        key = str(metadata.get("turn_idempotency_key") or (message.metadata_ or {}).get("turn_idempotency_key") or "")
        if not key:
            raise ConversationTurnError(
                "CONVERSATION_TURN_RECOVERY_REQUIRED",
                "The failed turn has no durable idempotency key.",
                {"trace_run_id": str(trace_run_id)},
            )
        assistant = session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.role == "assistant",
                Message.deleted_at.is_(None),
                Message.metadata_["trace_run_id"].astext == str(trace_run_id),
            ).limit(1)
        ).scalar_one_or_none()
        if assistant is not None:
            raise ConversationTurnError(
                "CONVERSATION_TURN_NOT_RETRYABLE",
                "This turn already has an assistant response.",
            )
        retry = dict(metadata.get("provider_retry") or {})
        retry["attempt_count"] = int(retry.get("attempt_count") or 0) + 1
        retry["last_attempt_at"] = datetime.now(timezone.utc).isoformat()
        metadata["provider_retry"] = retry
        metadata.pop("turn_response_json", None)
        metadata.pop("turn_failure", None)
        trace.metadata_ = metadata
        trace.status = "retrying"
        session.commit()
        return ConversationTurnClaim(
            key,
            message.id,
            trace.id,
            reasoning_mode=str(metadata.get("turn_reasoning_mode") or "auto"),
        ), message.content


def normalize_idempotency_key(value: str | None) -> str:
    key = value.strip() if isinstance(value, str) else ""
    if not key:
        return str(uuid.uuid4())
    if len(key) > 200:
        raise ConversationTurnError(
            "CONVERSATION_IDEMPOTENCY_KEY_INVALID",
            "The idempotency key must not exceed 200 characters.",
        )
    return key


def _turn_request_hash(
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
    mode_key: str,
    reasoning_mode: str,
    content: str,
    continuation_of_trace_run_id: uuid.UUID | None,
) -> str:
    return hashlib.sha256(
        (
            f"{conversation_id}:{companion_id}:{mode_key}:{reasoning_mode}:"
            f"{content}:{continuation_of_trace_run_id or ''}"
        ).encode("utf-8")
    ).hexdigest()


def store_turn_response(trace_run_id: uuid.UUID, result: dict[str, Any]) -> None:
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if trace is None:
            return
        metadata = dict(trace.metadata_ or {})
        metadata["turn_response_json"] = json.loads(json.dumps(result, default=str))
        trace.metadata_ = metadata
        session.commit()


def get_turn_status(
    *,
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
    trace_run_id: uuid.UUID,
) -> dict[str, Any] | None:
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if (
            trace is None
            or trace.conversation_id != conversation_id
            or trace.companion_id != companion_id
        ):
            return None
        message = session.get(Message, trace.message_id) if trace.message_id else None
        if message is None or message.conversation_id != conversation_id:
            return None
        assistant = session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.companion_id == companion_id,
                Message.role == "assistant",
                Message.deleted_at.is_(None),
                Message.metadata_["trace_run_id"].astext == str(trace_run_id),
            ).limit(1)
        ).scalar_one_or_none()
        metadata = dict(trace.metadata_ or {})
        transport = dict(metadata.get("turn_transport") or {})
        if transport.get("mode") != "async_web":
            return None
        return _status_projection(trace, message, assistant, metadata, transport)


def get_latest_turn_status(
    *,
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Return the latest async Web turn so a refreshed client can reconnect."""
    with get_session() as session:
        trace = session.execute(
            select(TraceRun)
            .where(
                TraceRun.conversation_id == conversation_id,
                TraceRun.companion_id == companion_id,
                TraceRun.agent_graph_name == "conversation_graph",
                TraceRun.metadata_["turn_transport"]["mode"].astext == "async_web",
            )
            .order_by(TraceRun.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if trace is None:
            return None
        message = session.get(Message, trace.message_id) if trace.message_id else None
        if message is None or message.conversation_id != conversation_id:
            return None
        assistant = session.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.companion_id == companion_id,
                Message.role == "assistant",
                Message.deleted_at.is_(None),
                Message.metadata_["trace_run_id"].astext == str(trace.id),
            ).limit(1)
        ).scalar_one_or_none()
        metadata = dict(trace.metadata_ or {})
        transport = dict(metadata.get("turn_transport") or {})
        return _status_projection(trace, message, assistant, metadata, transport)


def claim_next_async_turn(
    *,
    worker_id: str,
    lease_seconds: int,
) -> ConversationTurnClaim | None:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        rows = list(
            session.execute(
                select(TraceRun)
                .where(
                    TraceRun.agent_graph_name == "conversation_graph",
                    TraceRun.status == "started",
                    TraceRun.metadata_["turn_transport"]["mode"].astext == "async_web",
                )
                .order_by(TraceRun.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(20)
            ).scalars().all()
        )
        for trace in rows:
            metadata = dict(trace.metadata_ or {})
            transport = dict(metadata.get("turn_transport") or {})
            status = str(transport.get("lifecycle_status") or "accepted")
            if status in TURN_RUNTIME_TERMINAL_STATUSES:
                continue
            if status == "cancellation_requested":
                transport["lifecycle_status"] = "cancelled"
                transport["updated_at"] = now.isoformat()
                transport["completed_at"] = now.isoformat()
                transport["lease"] = {}
                metadata["turn_transport"] = transport
                trace.metadata_ = metadata
                trace.status = "cancelled"
                trace.completed_at = now
                session.commit()
                continue
            lease = dict(transport.get("lease") or {})
            expires_at = _parse_datetime(lease.get("expires_at"))
            if lease.get("worker_id") and expires_at and expires_at > now:
                continue
            message = session.get(Message, trace.message_id) if trace.message_id else None
            if message is None or message.deleted_at is not None or message.role != "user":
                _set_failed_transport(
                    trace,
                    metadata,
                    transport,
                    code="TURN_SOURCE_MESSAGE_MISSING",
                    now=now,
                )
                session.commit()
                continue
            assistant = session.execute(
                select(Message).where(
                    Message.conversation_id == trace.conversation_id,
                    Message.role == "assistant",
                    Message.deleted_at.is_(None),
                    Message.metadata_["trace_run_id"].astext == str(trace.id),
                ).limit(1)
            ).scalar_one_or_none()
            if assistant is not None:
                _set_failed_transport(
                    trace,
                    metadata,
                    transport,
                    code="TURN_RECOVERY_REQUIRES_RECONCILIATION",
                    now=now,
                )
                session.commit()
                continue
            transport["lifecycle_status"] = "context_preparing"
            transport["updated_at"] = now.isoformat()
            transport["started_at"] = transport.get("started_at") or now.isoformat()
            transport["attempt_count"] = int(transport.get("attempt_count") or 0) + 1
            transport["lease"] = {
                "worker_id": worker_id,
                "claimed_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=max(lease_seconds, 30))).isoformat(),
            }
            metadata["turn_transport"] = transport
            trace.metadata_ = metadata
            session.commit()
            return ConversationTurnClaim(
                str(metadata.get("turn_idempotency_key") or ""),
                message.id,
                trace.id,
                transport_mode="async_web",
                reasoning_mode=str(metadata.get("turn_reasoning_mode") or "auto"),
            )
    return None


def update_turn_lifecycle(
    trace_run_id: uuid.UUID,
    status: str,
    *,
    lease_seconds: int = 300,
) -> bool:
    if status not in TURN_RUNTIME_STATUSES:
        raise ValueError(f"Unsupported turn lifecycle status: {status}")
    now = datetime.now(timezone.utc)
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if trace is None:
            return False
        metadata = dict(trace.metadata_ or {})
        transport = dict(metadata.get("turn_transport") or {})
        if transport.get("mode") != "async_web":
            return False
        current = str(transport.get("lifecycle_status") or "accepted")
        if current in TURN_RUNTIME_TERMINAL_STATUSES:
            return False
        if status == current:
            return False
        if status != current and status not in TURN_RUNTIME_TRANSITIONS.get(current, set()):
            return False
        transport["lifecycle_status"] = status
        transport["updated_at"] = now.isoformat()
        lease = dict(transport.get("lease") or {})
        if lease.get("worker_id") and status not in TURN_RUNTIME_TERMINAL_STATUSES:
            lease["expires_at"] = (now + timedelta(seconds=max(lease_seconds, 30))).isoformat()
            transport["lease"] = lease
        metadata["turn_transport"] = transport
        trace.metadata_ = metadata
        session.commit()
        return True


def request_turn_cancellation(
    *,
    conversation_id: uuid.UUID,
    companion_id: uuid.UUID,
    trace_run_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Persist a user cancellation request without overwriting a completed response."""
    accepted = False
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if (
            trace is None
            or trace.conversation_id != conversation_id
            or trace.companion_id != companion_id
        ):
            return None
        metadata = dict(trace.metadata_ or {})
        transport = dict(metadata.get("turn_transport") or {})
        if transport.get("mode") != "async_web":
            return None
        current = str(transport.get("lifecycle_status") or "accepted")
        if current not in TURN_RUNTIME_TERMINAL_STATUSES and current not in {
            "response_persisted", "effects_processing",
        }:
            now = datetime.now(timezone.utc)
            transport["lifecycle_status"] = "cancellation_requested"
            transport["cancellation_requested_at"] = now.isoformat()
            transport["updated_at"] = now.isoformat()
            metadata["turn_transport"] = transport
            trace.metadata_ = metadata
            session.commit()
            accepted = True
    status = get_turn_status(
        conversation_id=conversation_id,
        companion_id=companion_id,
        trace_run_id=trace_run_id,
    )
    if status is not None:
        status["cancellation_accepted"] = accepted
    return status


def is_cancellation_requested(trace_run_id: uuid.UUID) -> bool:
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if trace is None:
            return False
        transport = dict((trace.metadata_ or {}).get("turn_transport") or {})
        return transport.get("lifecycle_status") == "cancellation_requested"


def finalize_turn_runtime(
    trace_run_id: uuid.UUID,
    *,
    result: dict[str, Any],
    stage_timings: list[dict[str, Any]],
    provider_timing: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc)
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if trace is None:
            return
        metadata = dict(trace.metadata_ or {})
        transport = dict(metadata.get("turn_transport") or {})
        if transport.get("mode") != "async_web":
            return
        cancelled = trace.status == "cancelled" or ((result.get("turn") or {}).get("outcome") == "cancelled")
        failed = not cancelled and (bool(result.get("_run_errors")) or trace.status == "failed")
        status = "cancelled" if cancelled else "failed" if failed else "completed"
        current = str(transport.get("lifecycle_status") or "accepted")
        if current == "completed" or (current in TURN_RUNTIME_TERMINAL_STATUSES and current != status):
            return
        transport["lifecycle_status"] = status
        transport["updated_at"] = now.isoformat()
        transport["completed_at"] = now.isoformat()
        transport["lease"] = {}
        transport["stage_timings"] = _json_safe(stage_timings)
        transport["provider_timing"] = _json_safe(provider_timing)
        if failed:
            first_error = (result.get("_run_errors") or [{}])[0]
            transport["failure"] = {
                "code": first_error.get("code") or "CONVERSATION_TURN_FAILED",
                "step": first_error.get("step"),
            }
        metadata["turn_transport"] = transport
        trace.metadata_ = metadata
        session.commit()


def mark_claim_failed(trace_run_id: uuid.UUID, exc: Exception) -> None:
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if trace is None:
            return
        if trace.status in {"completed", "cancelled"}:
            return
        trace.status = "failed"
        metadata = dict(trace.metadata_ or {})
        metadata["turn_failure"] = {"error_type": type(exc).__name__}
        transport = dict(metadata.get("turn_transport") or {})
        if (
            transport.get("mode") == "async_web"
            and transport.get("lifecycle_status") in {
                "response_persisted",
                "effects_processing",
            }
        ):
            now = datetime.now(timezone.utc)
            transport["lifecycle_status"] = "completed"
            transport["updated_at"] = now.isoformat()
            transport["completed_at"] = now.isoformat()
            transport["lease"] = {}
            transport["post_response_failure"] = {
                "code": "POST_RESPONSE_RUNTIME_FAILED",
                "error_type": type(exc).__name__,
            }
            metadata["turn_transport"] = transport
            trace.metadata_ = metadata
            trace.status = "completed"
            session.commit()
            return
        if transport.get("mode") == "async_web" and transport.get("lifecycle_status") != "completed":
            now = datetime.now(timezone.utc)
            transport["lifecycle_status"] = "failed"
            transport["updated_at"] = now.isoformat()
            transport["completed_at"] = now.isoformat()
            transport["lease"] = {}
            transport["failure"] = {"code": "CONVERSATION_TURN_RUNTIME_FAILED", "error_type": type(exc).__name__}
            metadata["turn_transport"] = transport
        trace.metadata_ = metadata
        session.commit()
    try:
        from app.services import quality_feedback_service

        quality_feedback_service.enqueue_trace_feedback(trace_run_id)
    except Exception:
        # Recent-terminal reconciliation recovers this optional enqueue without
        # obscuring the original Conversation failure.
        return


def _status_projection(
    trace: TraceRun,
    user_message: Message,
    assistant_message: Message | None,
    metadata: dict[str, Any],
    transport: dict[str, Any],
) -> dict[str, Any]:
    response = metadata.get("turn_response_json")
    return {
        "contract_version": TURN_RUNTIME_CONTRACT_VERSION,
        "trace_run_id": str(trace.id),
        "conversation_id": str(trace.conversation_id),
        "companion_id": str(trace.companion_id),
        "idempotency_key": metadata.get("turn_idempotency_key"),
        "reasoning_mode": metadata.get("turn_reasoning_mode") or "auto",
        "status": transport.get("lifecycle_status") or "accepted",
        "accepted_at": transport.get("accepted_at"),
        "started_at": transport.get("started_at"),
        "updated_at": transport.get("updated_at"),
        "completed_at": transport.get("completed_at"),
        "attempt_count": int(transport.get("attempt_count") or 0),
        "stage_timings": transport.get("stage_timings") or [],
        "provider_timing": transport.get("provider_timing") or {},
        "post_turn_job": _safe_post_turn_job(metadata.get("post_turn_job") or {}),
        "failure": transport.get("failure"),
        "user_message": _message_projection(user_message),
        "assistant_message": _message_projection(assistant_message) if assistant_message else None,
        "result": response if transport.get("lifecycle_status") in TURN_RUNTIME_TERMINAL_STATUSES else None,
    }


def _safe_post_turn_job(job: dict[str, Any]) -> dict[str, Any]:
    if not job:
        return {}
    return {
        key: value
        for key, value in job.items()
        if key not in {"lease", "failure_history"}
    }


def _message_projection(message: Message) -> dict[str, Any]:
    metadata = getattr(message, "metadata_", {}) or {}
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "content_format": message.content_format,
        "model_provider": message.model_provider,
        "model_name": message.model_name,
        "generation_status": metadata.get("generation_status"),
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _set_failed_transport(
    trace: TraceRun,
    metadata: dict[str, Any],
    transport: dict[str, Any],
    *,
    code: str,
    now: datetime,
) -> None:
    transport["lifecycle_status"] = "failed"
    transport["updated_at"] = now.isoformat()
    transport["completed_at"] = now.isoformat()
    transport["lease"] = {}
    transport["failure"] = {"code": code}
    metadata["turn_transport"] = transport
    trace.metadata_ = metadata
    trace.status = "failed"


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))
