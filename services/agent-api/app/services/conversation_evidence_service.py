"""Safe, message-scoped evidence projection for Single-Companion Conversations."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.db.models import Conversation, Memory, Message, RelationshipExplanationEvent, ToolRun, TraceRun, TraceStep
from app.services import conversation_service


CONTRACT_VERSION = "conversation-message-evidence.v1"

_CONTEXT_SECTION_LABELS = {
    "safety": "安全与用户边界",
    "identity": "伙伴身份",
    "persona": "伙伴人格与性格",
    "relationship_contract": "关系约定",
    "recent_conversation": "最近对话",
    "tool_operation": "工具结果",
    "task_operation": "任务进展",
    "relationship": "关系理解",
    "continuity": "长期延续",
    "context_documents": "上下文文档",
    "memories": "相关记忆",
    "growth": "已确认成长",
    "affect": "回应状态",
    "room": "多人场景上下文",
}


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object, *, limit: int = 240) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()[:limit]


def _step(steps: dict[str, TraceStep], name: str) -> TraceStep | None:
    return steps.get(name)


def _safe_observation(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    blocked_markers = {
        "reasoning_content", "credential", "access_token", "refresh_token",
        "api_key", "secret", "raw_html", "system_prompt", "prompt",
    }
    for key, item in list(value.items())[:30]:
        normalized_key = str(key)
        if any(marker in normalized_key.lower() for marker in blocked_markers):
            continue
        if isinstance(item, str):
            safe[normalized_key] = item[:2000]
        elif isinstance(item, (int, float, bool)) or item is None:
            safe[normalized_key] = item
        elif isinstance(item, list):
            projected: list[Any] = []
            for part in item[:12]:
                if isinstance(part, str):
                    projected.append(part[:500])
                elif isinstance(part, (int, float, bool)) or part is None:
                    projected.append(part)
                elif isinstance(part, dict):
                    projected.append(_safe_observation(part))
            safe[normalized_key] = projected
        elif isinstance(item, dict):
            safe[normalized_key] = _safe_observation(item)
    return safe


def _context_pack_projection(steps: dict[str, TraceStep], trace: TraceRun) -> dict[str, Any]:
    row = _step(steps, "context_pack")
    manifest = _mapping(_mapping(row.output_json).get("manifest")) if row else {}
    section_rows = manifest.get("sections")
    if not isinstance(section_rows, list):
        return {"status": "unavailable", "input_summary": _text(trace.input_summary, limit=500), "recent_message_count": None, "sections": [], "included_count": 0, "excluded_count": 0}
    sections: list[dict[str, Any]] = []
    for raw in section_rows:
        item = _mapping(raw)
        name = _text(item.get("name"), limit=80) or _text(item.get("section"), limit=80)
        if not name or name not in _CONTEXT_SECTION_LABELS:
            continue
        selected = bool(item.get("selected"))
        availability = _text(item.get("availability"), limit=80)
        exclusion = _text(item.get("exclusion_reason"), limit=120)
        if selected:
            explanation = "已纳入这条回复的本轮上下文"
        elif availability in {"empty", "unavailable", "not_available"} or (exclusion or "").startswith("source_"):
            explanation = "本轮没有可用内容"
        elif exclusion == "scope_mismatch_or_not_llm_allowed":
            explanation = "未通过当前对话与伙伴边界"
        elif exclusion in {"total_budget_exhausted", "included_truncated_by_total_budget"}:
            explanation = "受本轮信息容量限制"
        else:
            explanation = "本轮未纳入"
        freshness = _mapping(item.get("freshness"))
        sections.append({
            "key": name,
            "label": _CONTEXT_SECTION_LABELS[name],
            "included": selected,
            "status": "included" if selected else "excluded",
            "explanation": explanation,
            "freshness": _text(freshness.get("status"), limit=80),
        })
    included_count = sum(1 for item in sections if item["included"])
    recent = _mapping(manifest.get("recent_conversation"))
    return {
        "status": "available",
        "input_summary": _text(trace.input_summary, limit=500),
        "recent_message_count": recent.get("message_count") if isinstance(recent.get("message_count"), int) else None,
        "sections": sections,
        "included_count": included_count,
        "excluded_count": len(sections) - included_count,
    }


def _tool_run_projection(row: ToolRun) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "companion_id": str(row.companion_id),
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
        "tool_definition_id": str(row.tool_definition_id) if row.tool_definition_id else None,
        "parent_tool_run_id": str(row.parent_tool_run_id) if row.parent_tool_run_id else None,
        "requested_by": row.requested_by,
        "trace_run_id": str(row.trace_run_id) if row.trace_run_id else None,
        "capability": row.capability,
        "status": row.status,
        "risk_level": row.risk_level,
        "permission_required": row.permission_required,
        "permission_granted": row.permission_granted,
        "confirmation_required": row.confirmation_required,
        "confirmation_summary": _text(row.confirmation_summary, limit=500),
        "input_json": _safe_observation(row.input_json),
        "output_json": _safe_observation(row.output_json),
        "error_json": _safe_observation(row.error_json),
        "evidence_refs": [
            _safe_observation(item) for item in (row.evidence_refs or [])[:20]
            if isinstance(item, dict)
        ],
        "attempt_count": row.attempt_count,
        "max_attempts": row.max_attempts,
        "timeout_seconds": row.timeout_seconds,
        "terminal_reason": _text(row.terminal_reason, limit=300),
        "request_message_id": str(row.request_message_id) if row.request_message_id else None,
        "result_message_id": str(row.result_message_id) if row.result_message_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "elapsed_ms": row.elapsed_ms,
    }


def _safe_source_statuses(snapshot: dict[str, Any]) -> list[dict[str, str | None]]:
    sources = snapshot.get("sources")
    if not isinstance(sources, dict):
        return []
    result: list[dict[str, str | None]] = []
    for key, value in sources.items():
        payload = _mapping(value)
        result.append({
            "source": str(key)[:80],
            "status": _text(payload.get("status"), limit=80) or _text(payload.get("availability"), limit=80),
            "reason": _text(payload.get("reason")),
        })
    return result


def _boundary_items(steps: dict[str, TraceStep]) -> list[dict[str, str | bool | None]]:
    definitions = (
        ("boundary_check", "会话边界"),
        ("companion_memory_scope", "伙伴私有记忆范围"),
        ("persona_guard", "身份与人格边界"),
        ("cross_companion_memory", "跨伙伴内容"),
        ("shared_memory", "共享内容"),
    )
    items: list[dict[str, str | bool | None]] = []
    for step_name, label in definitions:
        row = _step(steps, step_name)
        if row is None or row.status == "skipped":
            continue
        output = _mapping(row.output_json)
        allowed = output.get("allowed")
        outcome = "blocked" if allowed is False or row.status in {"blocked", "failed"} else "applied"
        items.append({
            "key": step_name,
            "label": label,
            "status": row.status,
            "outcome": outcome,
            "allowed": allowed if isinstance(allowed, bool) else None,
            "scope": _text(output.get("scope"), limit=120) or _text(output.get("memory_scope"), limit=120),
            "reason": None,
        })
    return items


def _user_visible_workflow(
    *,
    steps: dict[str, TraceStep],
    context_pack: dict[str, Any],
    retrieval: dict[str, Any],
    boundaries: list[dict[str, str | bool | None]],
    tool_runs: list[dict[str, Any]],
    task_run_id: str | None,
    generation_status: object,
    memory_candidate_count: int,
    growth_candidate_count: int,
    post_turn: dict[str, Any],
) -> dict[str, Any]:
    """Group internal Trace nodes into a bounded, user-readable process."""

    stages: list[dict[str, str]] = [{
        "key": "understand",
        "title": "理解你的消息",
        "summary": "读取你本轮的消息，并将它与当前对话和伙伴身份关联。",
        "status": "completed",
    }]

    included_sections = [
        item["label"] for item in context_pack.get("sections", [])
        if isinstance(item, dict) and item.get("included") and isinstance(item.get("label"), str)
    ]
    blocked_count = sum(1 for item in boundaries if item.get("outcome") == "blocked")
    if context_pack.get("status") == "available":
        if included_sections:
            visible = "、".join(included_sections[:4])
            suffix = f"等 {len(included_sections)} 类信息" if len(included_sections) > 4 else ""
            context_summary = f"采用了{visible}{suffix}，并应用了你的边界与伙伴隔离设置。"
        else:
            context_summary = "使用了当前对话中可用的背景，并应用了你的边界与伙伴隔离设置。"
    else:
        context_summary = "恢复了当前对话中可用的背景；这条历史回复没有保存更详细的上下文分区记录。"
    if blocked_count:
        context_summary += f"有 {blocked_count} 项内容因安全或伙伴边界未进入回应。"
    stages.append({
        "key": "context",
        "title": "准备相关背景",
        "summary": context_summary,
        "status": "completed",
    })

    memory_step = _step(steps, "memory_retrieval")
    if memory_step is not None and memory_step.status != "skipped":
        retrieved = retrieval.get("candidates_retrieved")
        selected = retrieval.get("selected_count")
        if not isinstance(selected, int):
            selected = 0
        if isinstance(retrieved, int):
            memory_summary = f"找到 {retrieved} 条可能相关的伙伴私有记忆，其中 {selected} 条用于本轮回应。"
        elif selected:
            memory_summary = f"采用了 {selected} 条与本轮相关的伙伴私有记忆。"
        else:
            memory_summary = "没有采用长期记忆，本轮主要依据当前对话内容。"
        stages.append({
            "key": "memory",
            "title": "回忆相关内容",
            "summary": memory_summary,
            "status": "attention" if memory_step.status in {"failed", "blocked"} else "completed",
        })

    if tool_runs or task_run_id:
        failed_statuses = {"failed", "cancelled", "timed_out"}
        pending_statuses = {"pending", "running", "awaiting_input", "awaiting_confirmation", "retry_scheduled"}
        statuses = {str(item.get("status")) for item in tool_runs}
        if statuses & failed_statuses:
            action_status = "attention"
        elif statuses & pending_statuses:
            action_status = "in_progress"
        else:
            action_status = "completed"
        parts: list[str] = []
        if tool_runs:
            succeeded = sum(1 for item in tool_runs if item.get("status") == "succeeded")
            parts.append(f"本轮关联 {len(tool_runs)} 次工具活动，其中 {succeeded} 次已完成")
        if task_run_id:
            parts.append("创建或推进了一个有界任务")
        stages.append({
            "key": "action",
            "title": "完成必要行动",
            "summary": "；".join(parts) + "。具体结果可在“本轮活动”中查看。",
            "status": action_status,
        })

    interrupted = generation_status == "interrupted"
    stages.append({
        "key": "respond",
        "title": "形成这次回应",
        "summary": "你停止了本轮生成，系统保留了停止前已完成的部分。" if interrupted else "根据本轮消息、相关背景和已确认信息生成并保存这次回应。",
        "status": "attention" if interrupted else "completed",
    })

    post_errors = post_turn.get("errors")
    post_error_count = len(post_errors) if isinstance(post_errors, list) else 0
    if memory_candidate_count or growth_candidate_count:
        candidate_parts = []
        if memory_candidate_count:
            candidate_parts.append(f"{memory_candidate_count} 条记忆候选")
        if growth_candidate_count:
            candidate_parts.append(f"{growth_candidate_count} 条成长候选")
        post_summary = f"形成了{'和'.join(candidate_parts)}，确认前不会影响伙伴。"
    else:
        post_summary = "没有形成需要你确认的新记忆或成长变化。"
    if post_error_count:
        post_summary += f"回复后的整理有 {post_error_count} 项未完成，不影响已经保存的回应。"
    stages.append({
        "key": "after_response",
        "title": "整理互动结果",
        "summary": post_summary,
        "status": "attention" if post_error_count else "completed",
    })

    return {
        "version": "conversation-response-process.v1",
        "stages": stages,
    }


def get_message_evidence(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    companion_id: uuid.UUID,
) -> dict[str, Any]:
    """Return only explicitly projected evidence after strict Single-Companion scope checks."""
    with conversation_service.get_session() as session:
        conversation = session.get(Conversation, conversation_id)
        message = session.get(Message, message_id)
        if (
            conversation is None
            or conversation.deleted_at is not None
            or conversation.companion_id != companion_id
            or conversation_service.is_temporary_conversation_expired(conversation)
            or conversation_service.is_companion_room_conversation(conversation)
            or message is None
            or message.deleted_at is not None
            or message.role != "assistant"
            or message.conversation_id != conversation_id
            or message.companion_id != companion_id
        ):
            raise conversation_service.ConversationTurnError(
                "CONVERSATION_MESSAGE_EVIDENCE_NOT_FOUND",
                "No scoped evidence exists for this assistant message.",
            )

        trace_value = _mapping(message.metadata_).get("trace_run_id")
        try:
            trace_id = uuid.UUID(str(trace_value))
        except (TypeError, ValueError):
            raise conversation_service.ConversationTurnError(
                "CONVERSATION_MESSAGE_EVIDENCE_NOT_FOUND",
                "This assistant message has no recoverable trace evidence.",
            ) from None

        trace = session.get(TraceRun, trace_id)
        if (
            trace is None
            or trace.conversation_id != conversation_id
            or trace.companion_id != companion_id
            or trace.agent_graph_name != "conversation_graph"
        ):
            raise conversation_service.ConversationTurnError(
                "CONVERSATION_MESSAGE_EVIDENCE_SCOPE_MISMATCH",
                "Trace evidence does not match the requested Conversation and Companion.",
            )

        step_rows = list(session.execute(
            select(TraceStep).where(TraceStep.trace_run_id == trace.id).order_by(TraceStep.step_order.asc())
        ).scalars().all())
        steps = {row.step_name: row for row in step_rows}
        retrieval = _mapping(_step(steps, "memory_retrieval").output_json) if _step(steps, "memory_retrieval") else {}
        snapshot = _mapping(_step(steps, "companion_context_snapshot").output_json) if _step(steps, "companion_context_snapshot") else {}
        response_step = _step(steps, "response_generation")
        provider = _mapping(response_step.provider_json) if response_step else {}
        provider_output = _mapping(response_step.output_json) if response_step else {}
        provider_mode = _text(provider.get("provider_mode"), limit=80)
        simulation_flag = provider_output.get("is_simulation")
        if simulation_flag is None:
            simulation_flag = provider_output.get("is_mock")
        if provider_mode is None and isinstance(simulation_flag, bool):
            provider_mode = "simulation" if simulation_flag else "live"
        provider_timing = _mapping(_mapping(trace.metadata_).get("provider_timing"))
        tool_step = _step(steps, "tool_runtime") or _step(steps, "tool_selection")
        tool_output = _mapping(tool_step.output_json) if tool_step else {}
        post_turn = _mapping(_mapping(trace.metadata_).get("post_turn_effects"))
        task_step = _step(steps, "conversation_task_runtime")
        task_output = _mapping(task_step.output_json) if task_step else {}
        task_run_id = _text(task_output.get("task_run_id"), limit=80)

        tool_ids = list(trace.tool_run_ids or [])
        tool_rows: list[ToolRun] = []
        if tool_ids:
            tool_rows = list(session.execute(select(ToolRun).where(
                ToolRun.id.in_(tool_ids),
                ToolRun.companion_id == companion_id,
                ToolRun.conversation_id == conversation_id,
                ToolRun.deleted_at.is_(None),
            )).scalars().all())
        tool_by_id = {row.id: row for row in tool_rows}
        projected_tool_runs = [
            _tool_run_projection(tool_by_id[tool_id])
            for tool_id in tool_ids if tool_id in tool_by_id
        ]

        selected_ids = list(trace.selected_memory_ids or [])
        selected_memories: list[Memory] = []
        if selected_ids:
            selected_memories = list(session.execute(select(Memory).where(
                Memory.id.in_(selected_ids),
                Memory.companion_id == companion_id,
                Memory.owner_companion_id == companion_id,
                Memory.deleted_at.is_(None),
            )).scalars().all())
        memory_by_id = {row.id: row for row in selected_memories}

        explanations = list(session.execute(select(RelationshipExplanationEvent).where(
            RelationshipExplanationEvent.trace_run_id == trace.id,
            RelationshipExplanationEvent.conversation_id == conversation_id,
            RelationshipExplanationEvent.companion_id == companion_id,
            RelationshipExplanationEvent.user_visible.is_(True),
            RelationshipExplanationEvent.deleted_at.is_(None),
        ).order_by(RelationshipExplanationEvent.created_at.asc())).scalars().all())

        context_pack = _context_pack_projection(steps, trace)
        boundaries = _boundary_items(steps)
        memory_candidate_count = len(trace.generated_memory_candidate_ids or [])
        growth_candidate_count = len(trace.generated_growth_candidate_ids or [])
        generation_status = _mapping(message.metadata_).get("generation_status")
        workflow = _user_visible_workflow(
            steps=steps,
            context_pack=context_pack,
            retrieval=retrieval,
            boundaries=boundaries,
            tool_runs=projected_tool_runs,
            task_run_id=task_run_id,
            generation_status=generation_status,
            memory_candidate_count=memory_candidate_count,
            growth_candidate_count=growth_candidate_count,
            post_turn=post_turn,
        )

        return {
            "contract_version": CONTRACT_VERSION,
            "conversation_id": str(conversation.id),
            "companion_id": str(companion_id),
            "assistant_message_id": str(message.id),
            "trace_run_id": str(trace.id),
            "response": {
                "status": trace.status,
                "generation_status": generation_status,
                "provider_mode": provider_mode,
                "provider_name": _text(provider.get("provider_name"), limit=120) or trace.model_provider,
                "model_name": _text(provider.get("model_name"), limit=160) or trace.model_name,
                "elapsed_ms": trace.elapsed_ms,
                "provider_timing": {
                    key: provider_timing.get(key)
                    for key in ("total_ms", "time_to_first_token_ms", "first_token_measurement_status")
                    if key in provider_timing
                },
            },
            "context": {
                "conversation": {
                    "title": conversation.title,
                    "mode_key": conversation.mode_key,
                    "current_topic": conversation.current_topic,
                    "current_goal": conversation.current_goal,
                },
                "memories": {
                    "retrieved_count": retrieval.get("candidates_retrieved"),
                    "selected_count": retrieval.get("selected_count", len(selected_ids)),
                    "excluded_count": retrieval.get("excluded_count"),
                    "boundary_exclusion_counts": _mapping(retrieval.get("boundary_exclusion_counts")),
                    "policy_mode": "shadow",
                    "selected": [
                        {
                            "id": str(memory_id),
                            "summary": _text(memory_by_id[memory_id].summary) or "已纳入一条伙伴私有记忆",
                            "updated_at": memory_by_id[memory_id].updated_at.isoformat() if memory_by_id[memory_id].updated_at else None,
                        }
                        for memory_id in selected_ids if memory_id in memory_by_id
                    ],
                },
                "snapshot": {
                    "contract_version": _text(snapshot.get("contract_version"), limit=120),
                    "availability": _text(snapshot.get("availability"), limit=80),
                    "scope": _text(snapshot.get("scope"), limit=120),
                    "sources": _safe_source_statuses(snapshot),
                },
                "pack": context_pack,
            },
            "boundaries": boundaries,
            "tools": {
                "status": tool_step.status if tool_step else "not_used",
                "reason": _text(tool_output.get("reason")),
                "run_count": len(projected_tool_runs),
                "runs": projected_tool_runs,
            },
            "activity": {
                "tool_run_ids": [item["id"] for item in projected_tool_runs],
                "task_run_id": task_run_id,
            },
            "decisions": {
                "memory_candidates": memory_candidate_count,
                "growth_candidates": growth_candidate_count,
                "presence_opportunities": len(trace.generated_presence_opportunity_ids or []),
                "review_status": _step(steps, "review_commit").status if _step(steps, "review_commit") else "not_recorded",
            },
            "relationship_explanations": [
                {
                    "id": str(item.id),
                    "dimension": item.dimension,
                    "title": item.title,
                    "explanation": item.explanation,
                }
                for item in explanations
            ],
            "post_turn": {
                "status": _text(post_turn.get("status"), limit=80) or "not_recorded",
                "contract_version": _text(post_turn.get("contract_version"), limit=120),
                "error_count": len(post_turn.get("errors") or []) if isinstance(post_turn.get("errors"), list) else 0,
                "effects": [
                    {
                        "effect": _text(item.get("effect"), limit=80),
                        "status": _text(item.get("status"), limit=80),
                        "elapsed_ms": item.get("elapsed_ms"),
                    }
                    for item in (post_turn.get("receipts") or []) if isinstance(item, dict)
                ],
            },
            "workflow": workflow,
        }
