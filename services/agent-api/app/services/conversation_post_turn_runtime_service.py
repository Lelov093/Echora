"""Independent durable worker for deferred async Web Post-turn Effects."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from time import perf_counter

from app.agents.nodes.post_turn_effects_node import (
    EFFECT_DEFINITIONS,
    run_post_turn_effects,
)
from app.agents.nodes.trace_logging_node import trace_logging_node
from app.db.models import TraceRun
from app.services import (
    conversation_application_service,
    conversation_turn_event_service,
    conversation_turn_journal_service,
    post_turn_effects_service,
)
from app.services.conversation_service import get_session


def run_scheduler_tick(
    *,
    worker_id: str,
    max_items: int = 1,
    lease_seconds: int = 300,
    max_attempts: int = 3,
) -> int:
    """Claim and execute a bounded number of isolated Post-turn jobs."""
    processed = 0
    for _ in range(max(1, max_items)):
        claim = post_turn_effects_service.claim_next_job(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            max_attempts=max_attempts,
        )
        if claim is None:
            break
        try:
            _execute_claimed_job(claim)
        except Exception as exc:
            post_turn_effects_service.fail_job(
                claim.trace_run_id,
                exc,
                max_attempts=max_attempts,
            )
        processed += 1
    return processed


def _execute_claimed_job(
    claim: post_turn_effects_service.PostTurnJobClaim,
) -> dict:
    journal = post_turn_effects_service.load_journal(claim.trace_run_id)
    if journal is None:
        raise ValueError("Post-turn job journal not found")
    state = dict(journal.get("recovery_state") or {})
    contract = dict(journal.get("contract") or {})
    if not state or state.get("trace_run_id") != str(claim.trace_run_id):
        raise ValueError("Post-turn job recovery state is unavailable or mismatched")
    state["post_turn_effects"] = contract

    effects_already_completed = (
        claim.resume_from == "effects_completed"
        or (
            contract.get("status") in {"completed", "partial_failed"}
            and len(contract.get("receipts") or []) >= len(EFFECT_DEFINITIONS)
        )
    )
    if not effects_already_completed:
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        failed = False
        try:
            state = run_post_turn_effects(state)
            return_state = state
        except Exception:
            failed = True
            raise
        finally:
            if not failed:
                return_state.setdefault("turn_stage_timings", []).append({
                    "stage": "post_turn_effects",
                    "started_at": started_at.isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "elapsed_ms": round((perf_counter() - started) * 1000),
                    "status": "completed",
                })
        post_turn_effects_service.mark_effects_completed(
            claim.trace_run_id,
            state,
        )

    if not _trace_is_terminal(claim.trace_run_id):
        state = trace_logging_node(state)

    result = conversation_application_service.project_conversation_turn(
        state,
        str(state.get("user_input") or ""),
    )
    result["turn"]["idempotency_key"] = state.get("turn_idempotency_key")
    result["turn"]["idempotent_replay"] = False
    result["turn"]["provider_retry"] = False
    conversation_turn_journal_service.store_turn_response(
        claim.trace_run_id,
        result,
    )
    conversation_turn_journal_service.finalize_turn_runtime(
        claim.trace_run_id,
        result=result,
        stage_timings=state.get("turn_stage_timings", []),
        provider_timing=state.get("provider_timing", {}),
    )
    post_turn_effects_service.complete_job(claim.trace_run_id)
    conversation_turn_event_service.publish(
        claim.trace_run_id,
        "completed",
        {
            "status": "completed",
            "post_turn_status": (
                state.get("post_turn_effects") or {}
            ).get("status"),
        },
    )
    return result


def _trace_is_terminal(trace_run_id: uuid.UUID) -> bool:
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        return bool(trace and trace.status in {"completed", "failed", "cancelled"})
