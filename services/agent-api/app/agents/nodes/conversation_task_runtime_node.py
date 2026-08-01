"""Conversation Graph nodes for durable bounded TaskRun orchestration."""

from app.agents.state import ConversationAgentState
from app.services.conversation_task_runtime_service import (
    process_conversation_task_turn,
    reconcile_conversation_task_turn,
)


def conversation_task_runtime_node(
    state: ConversationAgentState,
) -> ConversationAgentState:
    return process_conversation_task_turn(state)


def conversation_task_reconcile_node(
    state: ConversationAgentState,
) -> ConversationAgentState:
    return reconcile_conversation_task_turn(state)
