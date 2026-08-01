"""Realtime compatibility realtime shared memory candidate service."""

import uuid
from typing import Any

from app.db.models import RealtimeMemoryBuffer, RealtimeMemoryBufferItem, RealtimeSharedMemoryCandidate, SalientMoment
from app.services.realtime_copresence_service import get_session


def create_realtime_memory_candidate(salient_moment_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        moment = s.get(SalientMoment, salient_moment_id)
        if moment is None or moment.buffer_id is None:
            return None
        buffer = s.get(RealtimeMemoryBuffer, moment.buffer_id)
        item = s.get(RealtimeMemoryBufferItem, moment.buffer_item_id) if moment.buffer_item_id else None
        if buffer is None:
            return None
        candidate = RealtimeSharedMemoryCandidate(
            user_id=moment.user_id,
            realtime_session_id=moment.realtime_session_id,
            salient_moment_id=moment.id,
            source_buffer_id=buffer.id,
            source_buffer_item_id=item.id if item else None,
            proposed_shared_memory_candidate_id=None,
            candidate_status="pending_review",
            candidate_summary=payload.get("candidate_summary") or moment.moment_summary,
            requires_user_review=True,
            auto_commit_shared_memory=False,
            shared_to_private_policy="review_required",
            private_to_shared_policy="review_required",
            candidate_payload_json={
                "source": "realtime_salient_moment",
                "shared_episodic_memory_auto_write": False,
                "review_required": True,
            },
            metadata_={"implementation_origin": "realtime_memory"},
        )
        s.add(candidate)
        s.commit()
        s.refresh(candidate)
        return candidate_to_dict(candidate)


def create_shared_episodic_memory_candidate(
    salient_moment_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return create_realtime_memory_candidate(salient_moment_id, payload)


def get_realtime_memory_candidate(candidate_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        candidate = s.get(RealtimeSharedMemoryCandidate, candidate_id)
        return candidate_to_dict(candidate) if candidate else None


def decide_realtime_memory_candidate(candidate_id: uuid.UUID, decision: str) -> dict[str, Any] | None:
    if decision not in {"approved", "rejected"}:
        return None
    with get_session() as s:
        candidate = s.get(RealtimeSharedMemoryCandidate, candidate_id)
        if candidate is None or candidate.candidate_status != "pending_review" or not candidate.requires_user_review:
            return None
        candidate.candidate_status = decision
        # ponytail: approval records review only; shared-memory creation stays separately review-gated.
        s.commit()
        s.refresh(candidate)
        return candidate_to_dict(candidate)


def candidate_to_dict(candidate: RealtimeSharedMemoryCandidate) -> dict[str, Any]:
    return {
        "id": str(candidate.id),
        "user_id": str(candidate.user_id),
        "realtime_session_id": str(candidate.realtime_session_id) if candidate.realtime_session_id else None,
        "salient_moment_id": str(candidate.salient_moment_id) if candidate.salient_moment_id else None,
        "source_buffer_id": str(candidate.source_buffer_id) if candidate.source_buffer_id else None,
        "source_buffer_item_id": str(candidate.source_buffer_item_id) if candidate.source_buffer_item_id else None,
        "proposed_shared_memory_candidate_id": str(candidate.proposed_shared_memory_candidate_id)
        if candidate.proposed_shared_memory_candidate_id
        else None,
        "candidate_status": candidate.candidate_status,
        "candidate_summary": candidate.candidate_summary,
        "requires_user_review": candidate.requires_user_review,
        "auto_commit_shared_memory": candidate.auto_commit_shared_memory,
        "shared_to_private_policy": candidate.shared_to_private_policy,
        "private_to_shared_policy": candidate.private_to_shared_policy,
        "candidate_payload_json": candidate.candidate_payload_json or {},
    }
