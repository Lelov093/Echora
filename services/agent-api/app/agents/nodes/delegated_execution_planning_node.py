"""Companion Reoriented node: plan delegated execution as a companion-side assist layer."""

import uuid

from app.agents.state import ConversationAgentState
from app.services import delegated_execution_service

_TOOL_KEYWORDS = ("实现", "修改", "修复", "调试", "测试", "检查", "运行", "验证", "review", "fix", "debug")
_PROJECT_KEYWORDS = ("计划", "拆解", "安排", "任务", "阶段", "执行方案", "roadmap", "plan", "task")


def delegated_execution_planning_node(state: ConversationAgentState) -> ConversationAgentState:
    user_input = state.get("user_input", "")
    if state.get("task_run"):
        state["delegation_intent"] = {}
        state.setdefault("trace_steps", []).append({
            "step": "delegated_execution_planning",
            "order": 110,
            "status": "skipped",
            "reason": "durable_task_run_is_authoritative",
            "task_run_id": (state.get("task_run") or {}).get("id"),
        })
        return state
    if state.get("tool_runs"):
        state["delegation_intent"] = {}
        state.setdefault("trace_steps", []).append({
            "step": "delegated_execution_planning",
            "order": 110,
            "status": "skipped",
            "reason": "handled_by_p4_b2_tool_runtime",
        })
        return state
    has_companion_context = bool(state.get("co_presence_session") or state.get("shared_scene"))
    should_delegate = has_companion_context and _looks_like_delegation_request(user_input)
    if not should_delegate:
        state["delegation_intent"] = {}
        state.setdefault("trace_steps", []).append({
            "step": "delegated_execution_planning",
            "order": 110,
            "status": "skipped",
            "reason": "no_delegation_signal",
        })
        return state

    intent = delegated_execution_service.create_delegation_intent(
        {
            "user_id": state["user_id"],
            "companion_id": state["companion_id"],
            "requested_by_companion_id": state["companion_id"],
            "conversation_id": state["conversation_id"],
            "co_presence_session_id": (state.get("co_presence_session") or {}).get("id"),
            "shared_scene_id": (state.get("shared_scene") or {}).get("id"),
            "task_title": _task_title_from_input(user_input),
            "task_summary": user_input[:300],
            "preferred_executor_type": _preferred_executor_type(user_input),
            "execution_scope": "delegated_assist",
            "memory_boundary_json": state.get("companion_memory_scope") or {},
        }
    ) or {}
    state["delegation_intent"] = intent
    boundary_check = (
        ((intent.get("metadata") or {}).get("delegation") or {}).get("boundary_check") if intent else {}
    ) or {}
    if boundary_check.get("permission_required"):
        state.setdefault("warnings", []).append("Delegated execution intent requires Agent execution tool permission.")

    state.setdefault("trace_steps", []).append({
        "step": "delegated_execution_planning",
        "order": 110,
        "status": "completed" if intent else "failed",
        "delegation_trace_run_id": intent.get("id"),
        "executor_type": ((intent.get("metadata") or {}).get("delegation") or {}).get("executor_type"),
        "boundary_check": boundary_check,
    })
    return state


def _looks_like_delegation_request(user_input: str) -> bool:
    lowered = user_input.lower()
    return any(keyword in lowered for keyword in _TOOL_KEYWORDS) or any(
        keyword in lowered for keyword in _PROJECT_KEYWORDS
    )


def _preferred_executor_type(user_input: str) -> str:
    lowered = user_input.lower()
    if any(keyword in lowered for keyword in _TOOL_KEYWORDS):
        return "tool"
    if any(keyword in lowered for keyword in _PROJECT_KEYWORDS):
        return "project"
    return "tool"


def _task_title_from_input(user_input: str) -> str:
    compact = " ".join(user_input.strip().split())
    if not compact:
        return "Delegated execution intent"
    return compact[:80]
