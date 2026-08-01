"""bounded Tool Conversation node for bounded daily tool selection and execution."""

from app.agents.state import ConversationAgentState
from app.services.tool_runtime_service import process_conversation_tool_turn


def tool_runtime_node(state: ConversationAgentState) -> ConversationAgentState:
    if state.get("task_runtime_handled"):
        state.setdefault("trace_steps", []).append({
            "step": "tool_selection",
            "order": 45,
            "status": "skipped",
            "reason": "handled_by_conversation_task_runtime",
        })
        return state
    return process_conversation_tool_turn(state)
