"""MemoryRetrievalNode — uses memory/retrieval subsystem with pgvector or deterministic fallback vectors."""

import uuid

from sqlalchemy import select

from app.agents.state import ConversationAgentState
from app.db.models import Conversation, ToolRun
from app.memory.retrieval import retrieve_memories
from app.services.memory_service import get_session


def memory_retrieval_node(state: ConversationAgentState) -> ConversationAgentState:
    policy = state.get("conversation") or {}
    if policy.get("retention_mode") == "temporary" or not policy.get("cross_session_memory_enabled", True):
        state["retrieved_memories"] = []
        state["selected_memories"] = []
        state.setdefault("trace_steps", []).append({
            "step": "memory_retrieval",
            "order": 3,
            "status": "skipped",
            "reason": "conversation_retention_policy",
            "selected_memory_ids": [],
            "learned_shadow": {"policy_mode": "shadow", "executed": False},
        })
        return state
    cid = uuid.UUID(state["companion_id"])
    mode = state.get("current_mode", "project")
    conversation = state.get("conversation") or {}
    shared_scene = state.get("shared_scene") or {}
    co_presence_session = state.get("co_presence_session") or {}
    with get_session() as session:
        db_conversation = session.get(
            Conversation,
            uuid.UUID(state["conversation_id"]),
        )
        conversation_metadata = (
            dict(db_conversation.metadata_ or {}) if db_conversation else {}
        )
        latest_tool = session.execute(
            select(ToolRun)
            .where(
                ToolRun.user_id == uuid.UUID(state["user_id"]),
                ToolRun.companion_id == cid,
                ToolRun.conversation_id == uuid.UUID(state["conversation_id"]),
                ToolRun.deleted_at.is_(None),
            )
            .order_by(ToolRun.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        state["retrieval_tool_context"] = (
            {
                "tool_run_id": str(latest_tool.id),
                "capability": latest_tool.capability,
                "status": latest_tool.status,
                "confirmed_arguments": latest_tool.input_json or {},
                "missing_fields": (latest_tool.error_json or {}).get(
                    "missing_fields", []
                ),
            }
            if latest_tool
            else {}
        )
    query, query_mode = build_retrieval_query(state)

    result = retrieve_memories(
        companion_id=cid,
        query_text=query,
        current_mode=mode,
        context={
            "conversation_id": state.get("conversation_id"),
            "message_id": state.get("user_message_id"),
            "trace_run_id": state.get("trace_run_id"),
            "project_id": conversation_metadata.get("project_id"),
            "shared_scene_id": shared_scene.get("id")
            or conversation.get("shared_scene_id"),
            "co_presence_session_id": co_presence_session.get("id")
            or conversation.get("co_presence_session_id"),
            "current_goal": conversation.get("current_goal"),
        },
    )

    state["retrieved_memories"] = result["retrieved"]
    state["selected_memories"] = result["selected"]
    state["memory_usage_event_ids"] = [
        *state.get("memory_usage_event_ids", []),
        *result["trace"].get("usage_event_ids", []),
    ]

    state.setdefault("trace_steps", []).append({
        "step": "memory_retrieval",
        "order": 3,
        "status": "completed",
        "candidates_retrieved": result["trace"]["candidate_count"],
        "selected_count": result["trace"]["selected_count"],
        "method": result["trace"]["method"],
        "query_mode": query_mode,
        "embedding_provider": result["trace"]["embedding_provider"],
        "safe_candidate_count": result["trace"]["safe_candidate_count"],
        "excluded_count": result["trace"]["excluded_count"],
        "boundary_exclusion_counts": result["trace"]["boundary_exclusion_counts"],
        "context_summary": result["trace"]["context_summary"],
        "selected_memory_ids": result["trace"]["selected_memory_ids"],
        "excluded": result["trace"]["excluded"],
        "algorithm": result["trace"]["algorithm"],
        "learned_shadow": result["trace"]["learned_shadow"],
        "score_json": result["trace"]["algorithm"],
    })
    return state


def build_retrieval_query(
    state: ConversationAgentState,
) -> tuple[str, str]:
    """Augment elliptical turns with bounded, same-Conversation user context."""
    current = state.get("user_input", "").strip()
    if not _needs_conversation_context(current):
        return current, "current_turn_only"

    current_message_id = str(state.get("user_message_id") or "")
    prior_user_turns = [
        str(message.get("content") or "").strip()[:500]
        for message in state.get("recent_messages", [])
        if message.get("role") == "user"
        and str(message.get("id") or "") != current_message_id
        and str(message.get("content") or "").strip()
    ][-2:]
    if not prior_user_turns:
        return current, "current_turn_only"
    conversation = state.get("conversation") or {}
    tool_context = state.get("retrieval_tool_context") or {}
    context = "\n".join(f"- {turn}" for turn in prior_user_turns)
    topic = conversation.get("current_topic")
    goal = conversation.get("current_goal")
    structured = [
        f"Recent same-Conversation user context:\n{context}",
        f"Current topic: {topic}" if topic else "",
        f"Current goal: {goal}" if goal else "",
        (
            "Recent scoped tool intent: "
            f"{tool_context.get('capability')} "
            f"{tool_context.get('confirmed_arguments')}"
            if tool_context
            else ""
        ),
        f"Current request:\n{current}",
    ]
    return (
        "\n".join(item for item in structured if item),
        "conversation_aware_query_v1",
    )


def _needs_conversation_context(text: str) -> bool:
    compact = text.strip()
    if len(compact) <= 80:
        return True
    markers = (
        "这", "那", "它", "他", "她", "继续", "刚才", "上面", "前面",
        "今天", "明天", "后天", "再试", "重试",
        "this", "that", "it", "continue", "earlier", "today", "tomorrow",
    )
    lowered = compact.lower()
    return any(marker in lowered for marker in markers)
