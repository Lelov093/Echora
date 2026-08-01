"""Apply safe automation and batch remaining review candidates."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import governance_policy_service, review_batch_service


def review_resolution_node(state: ConversationAgentState) -> ConversationAgentState:
    mc_list = state.get("memory_candidates", [])
    gc_list = state.get("growth_candidates", [])
    rc_list = state.get("relationship_candidates", [])
    po_list = state.get("presence_opportunities", [])
    governance_decisions = []
    companion_id = uuid.UUID(state["companion_id"])
    for candidate in mc_list:
        candidate_id = candidate.get("id")
        if not candidate_id:
            continue
        try:
            decision = governance_policy_service.auto_commit_memory_candidate(
                uuid.UUID(candidate_id), companion_id
            )
        except Exception as exc:
            decision = {
                "status": "manual_review",
                "reason": "governance_evaluation_failed",
                "error_type": type(exc).__name__,
            }
        governance_decisions.append({"candidate_id": candidate_id, **decision})
        if decision.get("status") == "auto_committed":
            candidate["status"] = "committed"

    pending_mc_list = [item for item in mc_list if item.get("status") != "committed"]
    mc_generated_count = len(mc_list)
    mc_count = len(pending_mc_list)
    gc_count = len(gc_list)
    rc_count = len(rc_list)
    po_count = len(po_list)
    total_candidates = mc_count + gc_count + rc_count

    batch_id = None
    batch_error = None
    review_summary: dict = {
        "memory_candidates_count": mc_count,
        "memory_candidates_generated_count": mc_generated_count,
        "growth_candidates_count": gc_count,
        "relationship_candidates_count": rc_count,
        "presence_opportunities_count": po_count,
        "total_candidates": total_candidates,
        "auto_committed": False,
        "auto_committed_count": sum(
            1 for item in governance_decisions if item.get("status") == "auto_committed"
        ),
        "governance_decisions": governance_decisions,
        "batch_created": False,
    }

    # Create review batch if there are multiple candidates
    if total_candidates > 0:
        # Collect item refs for the batch
        item_refs = []
        for mc in pending_mc_list:
            if mc.get("id"):
                item_refs.append({
                    "candidate_type": "memory",
                    "candidate_id": mc["id"],
                    "suggested_type": mc.get("suggested_type", ""),
                    "content_preview": (mc.get("content", "") or "")[:100],
                })
        for gc in gc_list:
            if gc.get("id"):
                item_refs.append({
                    "candidate_type": "growth",
                    "candidate_id": gc["id"],
                    "type": gc.get("type", ""),
                    "content_preview": (gc.get("content", "") or "")[:100],
                })
        for rc in rc_list:
            if rc.get("id"):
                item_refs.append({
                    "candidate_type": "relationship",
                    "candidate_id": rc["id"],
                    "expected_revision": rc.get("expected_state_revision", 0),
                    "content_preview": (rc.get("summary", "") or "")[:100],
                    "risk_level": rc.get("risk_level", "medium"),
                })

        if item_refs:
            batch_data = {
                "user_id": state["user_id"],
                "companion_id": state["companion_id"],
                "conversation_id": state.get("conversation_id"),
                "batch_type": "mixed_review",
                "title": f"Review batch: {mc_count} memory + {gc_count} growth + {rc_count} relationship candidate(s)",
                "description": (
                    f"Auto-generated review batch from agent run. "
                    f"{mc_count} memory, {gc_count} growth, and {rc_count} relationship candidate(s)."
                ),
                "item_refs": item_refs,
            }
            try:
                result = review_batch_service.create_batch(batch_data)
                batch_id = result["id"]
                review_summary["batch_created"] = True
                review_summary["batch_id"] = batch_id
                review_summary["item_count"] = len(item_refs)
            except Exception as exc:
                batch_error = type(exc).__name__

    state["review_batch_id"] = batch_id
    state["review_summary"] = review_summary
    review_summary["auto_committed"] = review_summary["auto_committed_count"] > 0

    state.setdefault("trace_steps", []).append({
        "step": "review_commit",
        "order": 12,
        "status": "warning" if batch_error else "completed",
        "message": (
            "Eligible low-risk private memory auto-committed; remaining candidates await review"
            if review_summary["auto_committed"]
            else "Candidates held pending — awaiting user review"
        ),
        "memory_candidates_count": mc_count,
        "growth_candidates_count": gc_count,
        "relationship_candidates_count": rc_count,
        "presence_opportunities_count": po_count,
        "auto_committed": review_summary["auto_committed"],
        "auto_committed_count": review_summary["auto_committed_count"],
        "governance_decisions": governance_decisions,
        "batch_created": review_summary.get("batch_created", False),
        "batch_id": batch_id,
        "batch_item_count": review_summary.get("item_count", 0),
        "batch_error": batch_error,
    })
    return state
