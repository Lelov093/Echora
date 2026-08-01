"""Durable Post-turn Effects journal backed by the existing TraceRun metadata."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import TraceRun
from app.services.trace_service import get_session


CONTRACT_VERSION = "post-turn-effects.v1"
JOB_CONTRACT_VERSION = "conversation-post-turn-job.v1"
JOB_TERMINAL_STATUSES = {"completed", "failed"}
JOB_CLAIMABLE_STATUSES = {
    "queued",
    "running",
    "retry_scheduled",
    "effects_completed",
}


@dataclass(frozen=True)
class PostTurnJobClaim:
    trace_run_id: uuid.UUID
    attempt_count: int
    resume_from: str


def persist_checkpoint(
    trace_run_id: str,
    state: dict[str, Any],
    contract: dict[str, Any],
) -> None:
    """Persist a JSON-safe recovery checkpoint before or during effect execution."""
    with get_session() as session:
        trace = session.get(TraceRun, uuid.UUID(trace_run_id))
        if trace is None:
            raise ValueError("TraceRun not found for Post-turn Effects journal")
        metadata = dict(trace.metadata_ or {})
        metadata["post_turn_effects"] = _json_safe(contract)
        metadata["post_turn_recovery_state"] = _recovery_state(state)
        metadata["post_turn_journal_updated_at"] = datetime.now(timezone.utc).isoformat()
        trace.metadata_ = metadata
        session.commit()


def enqueue_job(
    trace_run_id: uuid.UUID,
    state: dict[str, Any],
    *,
    planned_effects: list[str],
) -> dict[str, Any]:
    """Durably queue Post-turn work after the canonical response exists."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        trace = session.execute(
            select(TraceRun).where(TraceRun.id == trace_run_id).with_for_update()
        ).scalar_one_or_none()
        if trace is None:
            raise ValueError("TraceRun not found for Post-turn job")
        metadata = dict(trace.metadata_ or {})
        existing = dict(metadata.get("post_turn_job") or {})
        if existing.get("contract_version") == JOB_CONTRACT_VERSION:
            return _public_job(existing)

        transport = dict(metadata.get("turn_transport") or {})
        if (
            transport.get("mode") != "async_web"
            or transport.get("lifecycle_status") != "response_persisted"
        ):
            raise ValueError("Post-turn job requires one persisted async Web response")

        contract = {
            "contract_version": CONTRACT_VERSION,
            "trace_run_id": str(trace_run_id),
            "idempotency_key": state.get("turn_idempotency_key"),
            "transaction_mode": "domain_local_with_durable_trace_journal",
            "version_guard": {"policy": "snapshot_versions_recorded_no_direct_profile_overwrite"},
            "receipts": [],
            "status": "queued",
        }
        job = {
            "contract_version": JOB_CONTRACT_VERSION,
            "status": "queued",
            "queued_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "attempt_count": 0,
            "max_attempts": None,
            "next_attempt_at": now.isoformat(),
            "lease": {},
            "planned_effects": list(planned_effects),
            "failure_history": [],
        }
        metadata["post_turn_effects"] = _json_safe(contract)
        metadata["post_turn_recovery_state"] = _recovery_state(state)
        metadata["post_turn_job"] = job
        transport["stage_timings"] = _json_safe(
            state.get("turn_stage_timings") or []
        )
        transport["provider_timing"] = _json_safe(
            state.get("provider_timing") or {}
        )
        metadata["turn_transport"] = transport
        trace.metadata_ = metadata
        session.commit()
        return _public_job(job)


def claim_next_job(
    *,
    worker_id: str,
    lease_seconds: int,
    max_attempts: int,
) -> PostTurnJobClaim | None:
    """Atomically claim one queued or expired Post-turn job."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        traces = list(
            session.execute(
                select(TraceRun)
                .where(
                    TraceRun.agent_graph_name == "conversation_graph",
                    TraceRun.metadata_["post_turn_job"]["contract_version"].astext
                    == JOB_CONTRACT_VERSION,
                    TraceRun.metadata_["post_turn_job"]["status"].astext.in_(
                        tuple(JOB_CLAIMABLE_STATUSES)
                    ),
                )
                .order_by(TraceRun.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(20)
            ).scalars()
        )
        for trace in traces:
            metadata = dict(trace.metadata_ or {})
            job = dict(metadata.get("post_turn_job") or {})
            status = str(job.get("status") or "")
            if status not in JOB_CLAIMABLE_STATUSES:
                continue
            next_attempt_at = _parse_datetime(job.get("next_attempt_at"))
            if status == "retry_scheduled" and next_attempt_at and next_attempt_at > now:
                continue
            lease = dict(job.get("lease") or {})
            expires_at = _parse_datetime(lease.get("expires_at"))
            if status == "running" and expires_at and expires_at > now:
                continue
            attempts = int(job.get("attempt_count") or 0)
            if attempts >= max(1, max_attempts) and status != "effects_completed":
                _set_terminal_job_failure(
                    trace,
                    metadata,
                    job,
                    code="POST_TURN_MAX_ATTEMPTS_EXHAUSTED",
                    now=now,
                )
                metadata["post_turn_job"] = job
                trace.metadata_ = metadata
                session.commit()
                continue

            resume_from = status
            attempts += 1 if status != "effects_completed" else 0
            job["status"] = "running"
            job["resume_from"] = resume_from
            job["attempt_count"] = attempts
            job["max_attempts"] = max(1, max_attempts)
            job["started_at"] = job.get("started_at") or now.isoformat()
            job["updated_at"] = now.isoformat()
            job["lease"] = {
                "worker_id": worker_id,
                "claimed_at": now.isoformat(),
                "expires_at": (
                    now + timedelta(seconds=max(lease_seconds, 30))
                ).isoformat(),
            }
            transport = dict(metadata.get("turn_transport") or {})
            if transport.get("lifecycle_status") == "response_persisted":
                transport["lifecycle_status"] = "effects_processing"
                transport["updated_at"] = now.isoformat()
                metadata["turn_transport"] = transport
            metadata["post_turn_job"] = job
            trace.metadata_ = metadata
            session.commit()
            return PostTurnJobClaim(trace.id, attempts, resume_from)
    return None


def mark_effects_completed(
    trace_run_id: uuid.UUID,
    state: dict[str, Any],
) -> None:
    """Checkpoint the completed effect receipts before Trace finalization."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        trace = session.execute(
            select(TraceRun).where(TraceRun.id == trace_run_id).with_for_update()
        ).scalar_one_or_none()
        if trace is None:
            raise ValueError("TraceRun not found for Post-turn job")
        metadata = dict(trace.metadata_ or {})
        job = dict(metadata.get("post_turn_job") or {})
        if job.get("status") in JOB_TERMINAL_STATUSES:
            return
        job["status"] = "effects_completed"
        job["updated_at"] = now.isoformat()
        job["effects_completed_at"] = now.isoformat()
        job["lease"] = {}
        metadata["post_turn_job"] = job
        metadata["post_turn_effects"] = _json_safe(state.get("post_turn_effects") or {})
        metadata["post_turn_recovery_state"] = _recovery_state(state)
        trace.metadata_ = metadata
        session.commit()


def complete_job(trace_run_id: uuid.UUID) -> dict[str, Any] | None:
    """Complete the separate effects job without overwriting response success."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        trace = session.execute(
            select(TraceRun).where(TraceRun.id == trace_run_id).with_for_update()
        ).scalar_one_or_none()
        if trace is None:
            return None
        metadata = dict(trace.metadata_ or {})
        job = dict(metadata.get("post_turn_job") or {})
        if job.get("status") == "completed":
            return _public_job(job)
        job["status"] = "completed"
        job["updated_at"] = now.isoformat()
        job["completed_at"] = now.isoformat()
        job["lease"] = {}
        metadata["post_turn_job"] = job
        if (metadata.get("post_turn_effects") or {}).get("status") == "completed":
            metadata.pop("post_turn_recovery_state", None)
        transport = dict(metadata.get("turn_transport") or {})
        if transport.get("lifecycle_status") not in {"failed", "cancelled"}:
            transport["lifecycle_status"] = "completed"
            transport["updated_at"] = now.isoformat()
            transport["completed_at"] = now.isoformat()
            transport["lease"] = {}
            metadata["turn_transport"] = transport
        trace.metadata_ = metadata
        trace.status = "completed"
        session.commit()
        return _public_job(job)


def fail_job(
    trace_run_id: uuid.UUID,
    exc: Exception,
    *,
    max_attempts: int,
) -> dict[str, Any] | None:
    """Retry isolated effects failure, then terminate without failing the response."""
    now = datetime.now(timezone.utc)
    with get_session() as session:
        trace = session.execute(
            select(TraceRun).where(TraceRun.id == trace_run_id).with_for_update()
        ).scalar_one_or_none()
        if trace is None:
            return None
        metadata = dict(trace.metadata_ or {})
        job = dict(metadata.get("post_turn_job") or {})
        if job.get("status") in JOB_TERMINAL_STATUSES:
            return _public_job(job)
        history = list(job.get("failure_history") or [])
        history.append({
            "attempt": int(job.get("attempt_count") or 0),
            "at": now.isoformat(),
            "error_type": type(exc).__name__,
        })
        job["failure_history"] = history[-10:]
        job["lease"] = {}
        attempts = int(job.get("attempt_count") or 0)
        if attempts < max(1, max_attempts):
            retry_at = now + timedelta(seconds=min(30, 2 ** max(1, attempts)))
            job["status"] = "retry_scheduled"
            job["next_attempt_at"] = retry_at.isoformat()
            job["updated_at"] = now.isoformat()
        else:
            _set_terminal_job_failure(
                trace,
                metadata,
                job,
                code="POST_TURN_RUNTIME_FAILED",
                now=now,
            )
        metadata["post_turn_job"] = job
        trace.metadata_ = metadata
        session.commit()
        return _public_job(job)


def load_journal(trace_run_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if trace is None:
            return None
        metadata = dict(trace.metadata_ or {})
        return {
            "trace_run_id": str(trace.id),
            "status": trace.status,
            "contract": metadata.get("post_turn_effects") or {},
            "recovery_state": metadata.get("post_turn_recovery_state") or {},
            "turn_idempotency_key": metadata.get("turn_idempotency_key"),
            "job": _public_job(metadata.get("post_turn_job") or {}),
        }


def clear_recovery_state(trace_run_id: str) -> None:
    with get_session() as session:
        trace = session.get(TraceRun, uuid.UUID(trace_run_id))
        if trace is None:
            return
        metadata = dict(trace.metadata_ or {})
        metadata.pop("post_turn_recovery_state", None)
        trace.metadata_ = metadata
        session.commit()


def _recovery_state(state: dict[str, Any]) -> dict[str, Any]:
    excluded = {
        "post_turn_effects",
        "post_turn_effect_errors",
    }
    return _json_safe({key: value for key, value in state.items() if key not in excluded})


def _set_terminal_job_failure(
    trace: TraceRun,
    metadata: dict[str, Any],
    job: dict[str, Any],
    *,
    code: str,
    now: datetime,
) -> None:
    job["status"] = "failed"
    job["updated_at"] = now.isoformat()
    job["completed_at"] = now.isoformat()
    job["lease"] = {}
    job["terminal_failure"] = {"code": code}
    transport = dict(metadata.get("turn_transport") or {})
    if transport.get("lifecycle_status") not in {"failed", "cancelled"}:
        transport["lifecycle_status"] = "completed"
        transport["updated_at"] = now.isoformat()
        transport["completed_at"] = now.isoformat()
        transport["lease"] = {}
        transport["post_turn_failure"] = {"code": code}
        metadata["turn_transport"] = transport
    response = dict(metadata.get("turn_response_json") or {})
    response["post_turn_effects"] = metadata.get("post_turn_effects") or {
        "contract_version": CONTRACT_VERSION,
        "status": "failed",
        "receipts": [],
    }
    response["post_turn_job"] = _public_job(job)
    metadata["turn_response_json"] = response
    trace.status = "completed"


def _public_job(job: dict[str, Any]) -> dict[str, Any]:
    if not job:
        return {}
    return {
        key: value
        for key, value in job.items()
        if key not in {"lease", "failure_history"}
    }


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
