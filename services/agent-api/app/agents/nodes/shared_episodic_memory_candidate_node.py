"""Companion Reoriented node: lift co-presence experiences into shared memory candidates."""

import uuid

from sqlalchemy import select

from app.agents.state import ConversationAgentState
from app.db.models import SharedMemoryCandidate
from app.schemas.companion_memory import SharedMemoryCandidateRead
from app.services.shared_memory_service import create_shared_memory_candidate, get_session


def shared_episodic_memory_candidate_node(state: ConversationAgentState) -> ConversationAgentState:
    user_id = uuid.UUID(state["user_id"])
    shared_scene = state.get("shared_scene") or {}
    co_presence_session = state.get("co_presence_session") or {}
    if not shared_scene and not co_presence_session:
        state["shared_memory_candidates"] = []
        state.setdefault("trace_steps", []).append({
            "step": "shared_episodic_memory_candidate",
            "order": 108,
            "status": "skipped",
            "reason": "no_companion_context",
        })
        return state

    candidate_policy = _candidate_policy(state)
    created_or_resolved: list[dict] = []

    for experience in shared_scene.get("shared_experiences", []):
        if experience.get("experience_status") != "candidate_pending_review":
            continue
        candidate = _find_existing_candidate(source_shared_experience_record_id=experience.get("id"))
        if candidate is None:
            candidate = create_shared_memory_candidate(
                user_id,
                {
                    "source_shared_experience_record_id": experience.get("id"),
                    "title": experience.get("experience_title"),
                    "summary": experience.get("experience_summary") or experience.get("experience_title") or "",
                    "content": experience.get("experience_detail") or experience.get("experience_summary") or "",
                    "candidate_status": "pending_review",
                    "requires_user_review": True,
                    "candidate_policy_json": candidate_policy,
                    "metadata": {"source": "shared_scene_experience", "implementation_origin": "shared_memory_candidate"},
                },
            )
            candidate = SharedMemoryCandidateRead.model_validate(candidate).model_dump(mode="json")
        created_or_resolved.append(_normalize_candidate(candidate, source_type="shared_scene_experience"))

    allow_shared_candidate = bool(
        ((state.get("companion_memory_scope") or {}).get("participant_memory_permission") or {}).get(
            "allow_shared_candidate", True
        )
    )
    if allow_shared_candidate:
        for memory_candidate in state.get("memory_candidates", []):
            if not memory_candidate.get("id"):
                continue
            candidate = _find_existing_candidate(source_memory_candidate_id=memory_candidate.get("id"))
            if candidate is None:
                candidate = create_shared_memory_candidate(
                    user_id,
                    {
                        "source_memory_candidate_id": memory_candidate.get("id"),
                        "title": memory_candidate.get("suggested_type") or "shared memory candidate",
                        "summary": memory_candidate.get("content", "")[:200],
                        "content": memory_candidate.get("content", ""),
                        "candidate_status": "pending_review",
                        "requires_user_review": True,
                        "candidate_policy_json": candidate_policy,
                        "metadata": {"source": "conversation_memory_candidate", "implementation_origin": "shared_memory_candidate"},
                    },
                )
                candidate = SharedMemoryCandidateRead.model_validate(candidate).model_dump(mode="json")
            created_or_resolved.append(_normalize_candidate(candidate, source_type="conversation_memory_candidate"))

    state["shared_memory_candidates"] = created_or_resolved
    state.setdefault("trace_steps", []).append({
        "step": "shared_episodic_memory_candidate",
        "order": 108,
        "status": "completed",
        "shared_memory_candidate_count": len(created_or_resolved),
        "from_shared_scene_count": len(
            [item for item in created_or_resolved if item.get("source_type") == "shared_scene_experience"]
        ),
        "from_memory_candidate_count": len(
            [item for item in created_or_resolved if item.get("source_type") == "conversation_memory_candidate"]
        ),
    })
    return state


def _candidate_policy(state: ConversationAgentState) -> dict:
    scope = state.get("companion_memory_scope") or {}
    session = state.get("co_presence_session") or {}
    policy = session.get("policy") or {}
    return {
        "user_global_memory_scope": scope.get("global_memory_read_scope"),
        "cross_companion_private_read_policy": scope.get("cross_companion_private_read_policy"),
        "private_to_shared_policy": policy.get("private_to_shared_policy", "review_required"),
        "shared_to_private_policy": policy.get("shared_to_private_policy", "review_required"),
        "review_required": True,
    }


def _find_existing_candidate(
    *,
    source_memory_candidate_id: str | None = None,
    source_shared_experience_record_id: str | None = None,
) -> dict | None:
    with get_session() as s:
        stmt = select(SharedMemoryCandidate)
        if source_memory_candidate_id:
            stmt = stmt.where(
                SharedMemoryCandidate.source_memory_candidate_id == uuid.UUID(source_memory_candidate_id)
            )
        if source_shared_experience_record_id:
            stmt = stmt.where(
                SharedMemoryCandidate.source_shared_experience_record_id == uuid.UUID(source_shared_experience_record_id)
            )
        row = s.execute(stmt.order_by(SharedMemoryCandidate.created_at.desc())).scalar_one_or_none()
        if row is None:
            return None
        return SharedMemoryCandidateRead.model_validate(row).model_dump(mode="json")


def _normalize_candidate(candidate: dict, *, source_type: str) -> dict:
    return {
        **candidate,
        "source_type": source_type,
        "source_memory_candidate_id": str(candidate.get("source_memory_candidate_id"))
        if candidate.get("source_memory_candidate_id")
        else None,
        "source_shared_experience_record_id": str(candidate.get("source_shared_experience_record_id"))
        if candidate.get("source_shared_experience_record_id")
        else None,
    }
