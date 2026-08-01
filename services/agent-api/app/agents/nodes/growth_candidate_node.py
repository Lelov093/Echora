"""GrowthCandidateNode — generates growth candidates based on triggers.

Evidence-based: only creates candidates when correction/understanding signals
are detected. Uses growth/scoring for trigger evaluation.
"""

import uuid

from app.agents.state import ConversationAgentState
from app.growth.scoring import score_growth_trigger
from app.services.evidence_service import (
    create_evidence_event,
    score_growth_confidence,
    score_growth_evidence,
)
from app.services.growth_consistency_service import (
    persist_growth_consistency_check,
    score_growth_consistency,
)
from app.services.growth_service import get_session
from app.services import growth_candidate_extraction_service
from app.services import growth_control_service
from app.db.models.growth import GrowthCandidate


def growth_candidate_node(state: ConversationAgentState) -> ConversationAgentState:
    user_input = state.get("user_input", "")
    selected_memories = state.get("selected_memories", [])
    conv_id_str = state.get("conversation_id")
    companion_id = uuid.UUID(state["companion_id"])

    if not growth_control_service.suggestions_allowed(companion_id):
        state["growth_candidates"] = []
        state.setdefault("trace_steps", []).append({
            "step": "growth_trigger",
            "order": 7,
            "status": "skipped",
            "decision": "paused_by_user",
            "reason": "Growth suggestions are paused for this Companion.",
            "candidate_created": False,
            "growth_candidate_ids": [],
        })
        return state

    trigger = score_growth_trigger(
        user_input=user_input,
        selected_memories=selected_memories,
    )
    extraction = (
        growth_candidate_extraction_service.extract_growth_candidate(
            user_input, state.get("assistant_response", "")
        )
        if trigger["create_candidate"] or trigger["score"] >= 0.45
        else {"version": growth_candidate_extraction_service.VERSION, "status": "not_requested"}
    )
    policy_allows_type = growth_control_service.suggestions_allowed(
        companion_id,
        str(extraction.get("type") or "understanding_update"),
    )

    candidates = []
    evidence_mem_ids = [
        uuid.UUID(memory["id"])
        for memory in selected_memories
        if memory.get("id")
    ]
    evidence = score_growth_evidence(
        companion_id,
        evidence_mem_ids,
        correction_strength=trigger["factors"]["correction_signal"],
        recurrence=trigger["factors"]["topic_recurrence"],
        additional_evidence_count=1 if extraction.get("status") == "validated" else 0,
        additional_confidences=[extraction["confidence"]] if extraction.get("status") == "validated" else [],
    )
    profile_patch_preview: dict = {}
    consistency = score_growth_consistency(
        companion_id,
        profile_patch_preview,
    )
    growth_confidence = score_growth_confidence(
        evidence_strength=evidence["evidence_score"],
        user_confirmation_rate=0.5,
        recurrence=trigger["factors"]["topic_recurrence"],
        consistency_with_profile=consistency["consistency_score"],
    )
    if trigger["create_candidate"] and extraction.get("status") == "validated" and policy_allows_type:
        uid = uuid.UUID(state["user_id"])
        cid_uuid = companion_id
        conv_id = uuid.UUID(conv_id_str) if conv_id_str else None

        if evidence["is_sufficient"] and not consistency["blocks_commit"]:
            evidence_msg_ids = (
                [uuid.UUID(state["user_message_id"])]
                if state.get("user_message_id")
                else []
            )
            with get_session() as session:
                candidate = GrowthCandidate(
                    user_id=uid,
                    companion_id=cid_uuid,
                    conversation_id=conv_id,
                    type=extraction["type"],
                    content=extraction["content"] or _build_content(user_input, trigger),
                    reason=extraction["reason"] or trigger["reason"],
                    evidence_memory_ids=[
                        uuid.UUID(memory_id)
                        for memory_id in evidence["memory_ids"]
                    ],
                    evidence_message_ids=evidence_msg_ids,
                    confidence=growth_confidence["growth_confidence"],
                    evidence_score=evidence["evidence_score"],
                    impact_scope=[
                        "companion_understanding",
                        "response_strategy",
                    ],
                    risk_level=max(extraction["risk_level"], consistency["risk_level"], key={"low": 0, "medium": 1, "high": 2}.get),
                    requires_user_review=True,
                    status="candidate",
                    profile_patch_preview=profile_patch_preview,
                    score_json={
                        "trigger": trigger,
                        "evidence": evidence,
                        "growth_confidence": growth_confidence,
                        "consistency": consistency,
                        "provider_extraction": extraction,
                    },
                    calibration_json={
                        "algorithm_version": "core-growth-r5-v1",
                        "evidence_tier": evidence["tier"],
                        "provider_extraction_version": extraction["version"],
                    },
                )
                session.add(candidate)
                session.commit()
                session.refresh(candidate)
                candidate_id = candidate.id
                candidates.append(
                    {
                        "id": str(candidate.id),
                        "type": candidate.type,
                        "content": candidate.content,
                        "confidence": candidate.confidence,
                        "evidence_score": candidate.evidence_score,
                        "risk_level": candidate.risk_level,
                        "status": candidate.status,
                    }
                )
            persist_growth_consistency_check(
                user_id=uid,
                companion_id=cid_uuid,
                growth_candidate_id=candidate_id,
                trace_run_id=(
                    uuid.UUID(state["trace_run_id"])
                    if state.get("trace_run_id")
                    else None
                ),
                result=consistency,
            )

        create_evidence_event(
            {
                "user_id": uid,
                "companion_id": cid_uuid,
                "conversation_id": conv_id,
                "trace_run_id": state.get("trace_run_id"),
                "target_type": "growth_candidate",
                "target_id": candidates[0]["id"] if candidates else None,
                "sufficiency_score": evidence["evidence_score"],
                "status": evidence["status"],
                "missing_evidence_json": (
                    []
                    if evidence["is_sufficient"]
                    else ["additional_companion_scoped_memory_evidence"]
                ),
                "evidence_refs": evidence["memory_ids"],
                "explanation": (
                    "Growth evidence scored independently from trigger score."
                ),
            }
        )

    state["growth_candidates"] = candidates
    state.setdefault("trace_steps", []).append({
        "step": "growth_trigger",
        "order": 7,
        "status": "completed",
        "score": trigger["score"],
        "decision": trigger["decision"],
        "reason": trigger["reason"],
        "factors": trigger["factors"],
        "algorithm": trigger["algorithm"],
        "score_json": {
            "trigger": trigger,
            "evidence": evidence,
            "growth_confidence": growth_confidence,
            "consistency": consistency,
        },
        "evidence_score": evidence["evidence_score"],
        "evidence_tier": evidence["tier"],
        "candidate_created": bool(candidates),
        "candidate_blocked_reason": (
            None
            if candidates or not trigger["create_candidate"]
            else (
                "provider_evidence_not_validated"
                if extraction.get("status") != "validated"
                else "paused_growth_type"
                if not policy_allows_type
                else
                "insufficient_evidence"
                if not evidence["is_sufficient"]
                else "profile_consistency_blocked"
            )
        ),
        "growth_candidate_ids": [c["id"] for c in candidates],
        "provider_extraction_status": extraction.get("status"),
    })
    return state


def _build_content(user_input: str, trigger: dict) -> str:
    """Build human-readable growth candidate content."""
    if trigger["factors"]["correction_signal"] >= 0.80:
        return f"User corrected Echora's understanding: {user_input[:300]}"
    elif trigger["factors"]["understanding_gap"] >= 0.50:
        return f"Potential understanding gap detected: {user_input[:300]}"
    else:
        return f"Growth signal detected: {user_input[:300]}"
