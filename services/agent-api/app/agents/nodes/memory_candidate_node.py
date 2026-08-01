"""MemoryCandidateNode — uses memory/scoring for real weighted scoring.

Core conversation: weighted heuristic scoring formula. Does NOT write to memories table.
"""

import uuid

from app.agents.state import ConversationAgentState
from app.memory.scoring import score_memory_candidate
from app.services import memory_candidate_extraction_service
from app.services.memory_service import get_session
from app.db.models.memory import MemoryCandidate


def memory_candidate_node(state: ConversationAgentState) -> ConversationAgentState:
    user_input = state.get("user_input", "")
    candidates = []
    extraction = None

    scoring_result = score_memory_candidate(user_input=user_input)

    candidate_signal = (
        scoring_result["create_candidate"]
        or scoring_result["factors"]["user_explicitness"] >= 0.7
    )
    if candidate_signal and state.get("boundary_check", {}).get(
        "allow_memory_candidates", True
    ):
        extraction = memory_candidate_extraction_service.extract_memory_candidate(user_input)
        validation = memory_candidate_extraction_service.build_independent_validation(
            user_input,
            extraction,
            scoring_result,
        )
        uid = uuid.UUID(state["user_id"])
        cid = uuid.UUID(state["companion_id"])
        conv_id_str = state.get("conversation_id")
        conv_id = uuid.UUID(conv_id_str) if conv_id_str else None

        grounded_content = extraction.get("source_quote") if extraction.get("status") == "validated" else None
        extracted_type = extraction.get("memory_type") if extraction.get("status") == "validated" else None
        source_message_id = state.get("user_message_id")
        s = get_session()
        cand = MemoryCandidate(
            user_id=uid, companion_id=cid, conversation_id=conv_id,
            proposed_owner_companion_id=cid,
            content=(grounded_content or user_input)[:500],
            suggested_summary=(grounded_content or user_input)[:200],
            suggested_type=extracted_type or scoring_result["suggested_type"],
            source_message_ids=[uuid.UUID(source_message_id)] if source_message_id else [],
            importance=scoring_result["factors"]["goal_relevance"],
            confidence=validation["confidence"], score=scoring_result["score"],
            reason=scoring_result["reason"], needs_user_confirmation=True,
            status="pending",
            score_json={
                "score": scoring_result["score"],
                "factors": scoring_result["factors"],
                "decision": scoring_result["decision"],
                "llm_candidate": extraction,
                "independent_validation": validation,
            },
            emotional_intensity=scoring_result["factors"]["emotional_intensity"],
            goal_relevance=scoring_result["factors"]["goal_relevance"],
            relationship_impact=validation["relationship_impact"],
            correction_value=scoring_result["factors"]["correction_value"],
            novelty=scoring_result["factors"]["novelty"],
            recurrence=scoring_result["factors"]["recurrence"],
            triviality=scoring_result["factors"]["triviality"],
            sensitivity_risk=validation["sensitivity_risk"],
        )
        s.add(cand); s.commit()
        candidates.append({
            "id": str(cand.id), "content": cand.content,
            "suggested_type": cand.suggested_type,
            "score": cand.score, "status": cand.status,
        })
        s.close()

    state["memory_candidates"] = candidates
    state.setdefault("trace_steps", []).append({
        "step": "memory_candidate_scoring", "order": 6, "status": "completed",
        "candidates_generated": len(candidates),
        "score": scoring_result["score"],
        "decision": scoring_result["decision"],
        "reason": scoring_result["reason"],
        "factors": scoring_result["factors"],
        "algorithm": scoring_result["algorithm"],
        "adjustments": scoring_result["adjustments"],
        "score_json": {
            "score": scoring_result["score"],
            "factors": scoring_result["factors"],
            **scoring_result["algorithm"],
        },
        "method": "weighted_heuristic",
        "llm_candidate_status": (
            extraction.get("status") if extraction is not None else "not_requested"
        ),
    })
    return state
