"""Outdated memory review service with explicit lifecycle effects."""

import hashlib
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.memory.embedding import embed_text
from app.db.models import Memory, OutdatedMemoryFlag, OutdatedMemoryReview
from app.services.memory_lifecycle_service import record_memory_change
from app.services.persistence_helpers import (
    default_ids,
    get_session,
    list_rows,
    row_to_dict,
    update_row,
)


def _snapshot(memory: Memory) -> dict:
    return {
        "state": memory.state,
        "memory_strength": round(float(memory.memory_strength or 0.0), 6),
        "confidence": round(float(memory.confidence or 0.0), 6),
        "half_life_days": memory.half_life_days,
        "outdated_count": int(memory.outdated_count or 0),
        "deleted_at": memory.deleted_at.isoformat() if memory.deleted_at else None,
        "content_fingerprint": hashlib.sha256(
            (memory.content or "").encode("utf-8")
        ).hexdigest()[:16],
    }


def create_flag(data: dict) -> dict:
    with get_session() as session:
        memory_id = uuid.UUID(str(data["memory_id"]))
        memory = session.get(Memory, memory_id)
        if memory is None:
            raise ValueError("Memory not found")

        reason = str(data.get("reason") or "Potentially outdated memory")
        existing = session.execute(
            select(OutdatedMemoryFlag).where(
                OutdatedMemoryFlag.memory_id == memory_id,
                OutdatedMemoryFlag.companion_id == memory.companion_id,
                OutdatedMemoryFlag.reason == reason,
                OutdatedMemoryFlag.status == "open",
                OutdatedMemoryFlag.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if existing is not None:
            return row_to_dict(existing)

        uid, _ = default_ids(session)
        flag = OutdatedMemoryFlag(
            user_id=memory.user_id or uid,
            companion_id=memory.companion_id,
            memory_id=memory.id,
            trace_run_id=(
                uuid.UUID(str(data["trace_run_id"]))
                if data.get("trace_run_id")
                else None
            ),
            reason=reason,
            confidence=max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
            status="open",
            evidence_refs=data.get("evidence_refs", []),
            suggested_action=data.get("suggested_action", "review"),
            metadata_=data.get("metadata", {}),
        )
        session.add(flag)
        session.commit()
        session.refresh(flag)
        return row_to_dict(flag)


def list_flags(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, OutdatedMemoryFlag, filters, page, page_size)


def update_flag(flag_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        return update_row(session, OutdatedMemoryFlag, flag_id, data)


def create_review(flag_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        flag = session.get(OutdatedMemoryFlag, flag_id)
        if flag is None:
            return None
        memory = session.get(Memory, flag.memory_id)
        decision = data.get("decision", "keep")
        if decision not in {
            "keep",
            "edit",
            "fade",
            "suppress",
            "archive",
            "delete",
            "reject_flag",
        }:
            raise ValueError(f"Unsupported outdated memory decision: {decision}")

        before = _snapshot(memory) if memory is not None else {}
        review = OutdatedMemoryReview(
            outdated_memory_flag_id=flag.id,
            user_id=flag.user_id,
            memory_id=flag.memory_id,
            decision=decision,
            edited_content=data.get("edited_content"),
            feedback_event_id=data.get("feedback_event_id"),
            reason=data.get("reason"),
            metadata_=data.get("metadata", {}),
        )
        session.add(review)
        flag.status = "dismissed" if decision == "reject_flag" else "resolved"

        lifecycle_event = None
        if memory is not None and decision not in {"keep", "reject_flag"}:
            now = datetime.now(timezone.utc)
            if decision == "edit":
                edited_content = str(data.get("edited_content") or "").strip()
                if not edited_content:
                    raise ValueError("edited_content is required for edit decision")
                memory.content = edited_content
                memory.embedding = embed_text(edited_content)
                memory.outdated_count = max(0, int(memory.outdated_count or 0) - 1)
                memory.feedback_score = min(
                    1.0, float(memory.feedback_score or 0.0) + 0.05
                )
            elif decision == "fade":
                memory.memory_strength = max(
                    0.0, float(memory.memory_strength or 0.5) - 0.2
                )
                if memory.state == "active":
                    memory.state = "dormant"
            elif decision == "suppress":
                memory.state = "suppressed"
            elif decision == "archive":
                memory.state = "archived"
            elif decision == "delete":
                memory.state = "deleted"
                memory.deleted_at = now
            memory.updated_at = now
            after = _snapshot(memory)
            lifecycle_event_type = {
                "edit": "candidate_edited",
                "fade": "faded",
                "suppress": "suppressed",
                "archive": "archived",
                "delete": "deleted",
            }[decision]
            lifecycle_event = record_memory_change(
                session,
                memory,
                event_type=lifecycle_event_type,
                reason=data.get("reason") or f"Outdated memory review: {decision}",
                before=before,
                after=after,
                score_json={
                    "flag_id": str(flag.id),
                    "flag_confidence": flag.confidence,
                    "suggested_action": flag.suggested_action,
                    "review_decision": decision,
                },
                feedback_event_id=review.feedback_event_id,
                trace_run_id=flag.trace_run_id,
            )
            review.lifecycle_event_id = lifecycle_event.id
        elif data.get("lifecycle_event_id"):
            review.lifecycle_event_id = uuid.UUID(str(data["lifecycle_event_id"]))

        session.commit()
        session.refresh(review)
        return row_to_dict(review)


def list_reviews(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, OutdatedMemoryReview, filters, page, page_size)
