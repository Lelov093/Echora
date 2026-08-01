"""Build the Companion conversation prompt from bounded product context."""

from __future__ import annotations

import json
from typing import Any

from app.agents.state import ConversationAgentState
from app.services.conversation_context_assembler import ConversationContextAssembler


def build_prompt(state: ConversationAgentState) -> tuple[str, str]:
    """Build a bounded system/user prompt from the unified context snapshot."""
    snapshot = state.get("companion_context_snapshot") or {}
    companion = state.get("companion_profile", {})
    identity = _data(snapshot, "identity")
    persona = _data(snapshot, "persona")
    contract = _data(snapshot, "relationship_contract")
    boundary = _data(snapshot, "boundary")
    relationship = _data(snapshot, "relationship")
    affect = _data(snapshot, "affect")
    continuity = _data(snapshot, "continuity")
    presence = _data(snapshot, "presence")
    memories = _items(snapshot, "memories") or state.get("selected_memories", [])[:5]
    growth = _items(snapshot, "growth")
    context_documents = _items(snapshot, "context_documents")
    tool_context = state.get("tool_context") or {}
    task_context = state.get("task_context") or {}
    recent_context_block, recent_context_manifest = _recent_conversation_context(state)

    name = identity.get("display_name") or companion.get("name") or "Echora"
    mode = state.get("current_mode", "project")
    strategy = state.get("response_strategy", {}).get("strategy", "gentle_check_in")

    identity_context = _lines(
        "Identity and core continuity",
        (
            ("Identity", identity.get("identity_summary")),
            ("Origin", identity.get("origin_story")),
            ("Self-continuity", identity.get("self_continuity_summary")),
            ("Core traits", _join(identity.get("core_traits_json"))),
            ("Identity labels", _join(identity.get("identity_labels_json"))),
        ),
    )
    response_preferences = persona.get("response_preferences_json") or {}
    persona_context = _lines(
        "Persona and communication",
        (
            ("Persona", persona.get("persona_summary") or companion.get("base_personality")),
            ("Communication style", persona.get("communication_style_summary")),
            ("Tone", _join(persona.get("tone_descriptors_json"))),
            ("Core values", _join(persona.get("core_values_json"))),
            ("Preferred response length", _preference_label("response_length", response_preferences.get("response_length"))),
            ("Guidance approach", _preference_label("guidance_style", response_preferences.get("guidance_style"))),
            ("Correction approach", _preference_label("correction_style", response_preferences.get("correction_style"))),
            ("Humor approach", _preference_label("humor_style", response_preferences.get("humor_style"))),
            ("Conflict approach", _preference_label("conflict_style", response_preferences.get("conflict_style"))),
            ("Presence style", persona.get("presence_style")),
        ),
    )
    contract_context = _lines(
        "Relationship contract",
        (
            ("Role", contract.get("relationship_role")),
            ("Contract", contract.get("contract_summary")),
            ("Collaboration style", contract.get("collaboration_style_summary")),
            ("Support scope", _join(contract.get("support_scope_json"))),
            ("User preferred name", (contract.get("contract_json") or {}).get("user_preferred_name")),
        ),
    )
    relationship_context = _lines(
        "Current relationship",
        (
            ("Summary", relationship.get("summary")),
            ("Reviewed revision", relationship.get("revision")),
            ("Evidence confidence", _relationship_confidence(relationship.get("uncertainty"))),
            ("Familiarity", relationship.get("familiarity")),
            ("Understanding", relationship.get("understanding")),
            ("Trust", relationship.get("trust")),
            ("Emotional closeness", relationship.get("emotional_closeness")),
            ("Continuity", relationship.get("continuity")),
        ),
    )
    continuity_context = _lines(
        "Conversation continuity",
        (
            ("Current topic", continuity.get("current_topic")),
            ("Current goal", continuity.get("current_goal")),
            ("Current phase", continuity.get("current_phase")),
            ("Previous assistant summary", continuity.get("last_assistant_summary")),
            ("Suggested next steps", _join(continuity.get("suggested_next_steps"))),
        ),
    )
    affect_context = _lines(
        "Bounded Companion expression state",
        (
            ("Qualitative state", (affect.get("expression") or {}).get("label")),
            ("Tone tendency", (affect.get("expression") or {}).get("tone")),
            ("Attention tendency", (affect.get("expression") or {}).get("focus")),
            ("Expression preference", affect.get("expression_intensity")),
        ),
    ) if affect.get("expression_enabled", True) else ""
    memory_context = _item_lines("Relevant approved memories", memories, "content")
    growth_context = _item_lines("Reviewed growth already in effect", growth, "content")
    document_context = _item_lines("Evidence-grounded context documents", context_documents, "content")
    boundary_context = _lines(
        "Presence and boundaries",
        (
            ("Presence style", presence.get("presence_style")),
            ("Presence interrupt policy", presence.get("presence_interrupt_policy")),
            ("Proactive level", presence.get("proactive_level")),
            ("Proactive presence allowed", presence.get("allow_proactive_presence")),
            ("Current proactive suppression", presence.get("proactive_suppression_reason")),
            ("Quiet hours", _join(presence.get("quiet_hours"))),
            ("Meaningful silence enabled", presence.get("meaningful_silence_enabled")),
            ("Cross-companion read policy", boundary.get("cross_companion_read_policy")),
            ("Private-to-shared review required", boundary.get("review_required_private_to_shared")),
        ),
    )
    tool_context_block = _tool_context(tool_context)
    task_context_block = _task_context(task_context)
    room_context_block = ""
    if state.get("room_turn_id"):
        capsule = (state.get("conversation") or {}).get("room_continuation_capsule") or {}
        capsule_text = capsule.get("summary") if capsule.get("review_status") == "user_confirmed" else None
        room_context_block = """Room turn contract
- This is a user-authored multi-Companion Room turn.
- Reply only as your own Companion identity; never speak for or delegate to another Companion.
- Other Companion replies are independent. Do not trigger another response or create a reply loop.
- Shared and cross-Companion memory remains review-gated; use only context explicitly supplied here."""
        if capsule_text:
            room_context_block += f"\n- User-reviewed continuation from the previous Room: {capsule_text}"

    sections = [
        ("safety", boundary_context),
        ("identity", identity_context),
        ("persona", persona_context),
        ("relationship_contract", contract_context),
        ("recent_conversation", recent_context_block),
        ("tool_operation", tool_context_block),
        ("task_operation", task_context_block),
        ("continuity", continuity_context),
        ("context_documents", document_context),
        ("memories", memory_context),
        ("growth", growth_context),
        ("relationship", relationship_context),
        ("affect", affect_context),
        ("room", room_context_block),
    ]
    context_blocks, manifest = ConversationContextAssembler().assemble(
        state,
        sections,
        recent_manifest=recent_context_manifest,
    )
    manifest.update({
        "selected_memory_count": len(memories),
        "context_document_count": len(context_documents),
        "tool_run_id": tool_context.get("id"),
        "tool_intent": state.get("tool_intent") or {},
        "task_run_id": task_context.get("task_run_id"),
        "task_status": task_context.get("status"),
    })
    state["context_pack_manifest"] = manifest
    system = f"""You are {name}, an AI cyber companion with long-term continuity.

Current mode: {mode}.
Response strategy: {strategy}.

You are not a generic chatbot. Respond as this specific Companion while remaining
truthful that you are AI. Use remembered context naturally when it is relevant;
do not recite the context inventory or claim memories that are not provided.

Context priority:
1. Non-bypassable safety and explicit user boundaries.
2. Core identity and guarded persona.
3. User-owned relationship configuration.
4. Reviewed growth that is already committed.
5. Bounded simulated expression state; it may shape tone only within all higher-priority rules.
6. Versioned evidence-grounded summaries and long-term profile.
7. Current relationship, continuity, and retrieved turn context.

Core rules:
- Be warm and natural without encouraging unhealthy dependence.
- Preserve the Companion's identity; do not perform major personality drift.
- Respect quiet, focus, hard-stop, revoke, sharing, and review boundaries.
- Treat affect as an internal simulated expression controller, never as consciousness, real feeling,
  attachment, a demand for reciprocity, or permission to override meaningful silence.
- Never treat another Companion's private context as available.
- If context is absent or uncertain, acknowledge uncertainty instead of inventing it.

{context_blocks}
"""
    user = (
        f"User says: {state.get('user_input', '')}\n\n"
        "Respond naturally as the Companion, using only relevant context above."
    )
    return system, user


def _data(snapshot: dict[str, Any], key: str) -> dict[str, Any]:
    section = snapshot.get(key) or {}
    return section.get("data") or {}


def _items(snapshot: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return list(_data(snapshot, key).get("items") or [])


def _lines(title: str, pairs: tuple[tuple[str, Any], ...]) -> str:
    lines = [f"{label}: {_text(value)}" for label, value in pairs if _present(value)]
    return f"{title}:\n" + "\n".join(f"- {line}" for line in lines) if lines else ""


def _item_lines(title: str, items: list[dict[str, Any]], field: str) -> str:
    lines = []
    for item in items[:5]:
        value = _text(item.get(field))
        if value:
            lines.append(f"- [{item.get('type', 'context')}] {value[:300]}")
    return f"{title}:\n" + "\n".join(lines) if lines else ""


def _recent_conversation_context(
    state: ConversationAgentState,
) -> tuple[str, dict[str, Any]]:
    current_message_id = str(state.get("user_message_id") or "")
    current_input = str(state.get("user_input") or "").strip()
    candidates = []
    skipped_matching_current = False
    for message in reversed(state.get("recent_messages", [])):
        message_id = str(message.get("id") or "")
        role = str(message.get("role") or "")
        content = str(message.get("content") or "").strip()
        if not content or role not in {"user", "assistant", "tool"}:
            continue
        if current_message_id and message_id == current_message_id:
            continue
        if (
            not current_message_id
            and not skipped_matching_current
            and role == "user"
            and content == current_input
        ):
            skipped_matching_current = True
            continue
        candidates.append(message)
        if len(candidates) >= 8:
            break
    messages = list(reversed(candidates))
    labels = {"user": "User", "assistant": "Companion", "tool": "Tool observation"}
    lines = []
    message_ids = []
    total_chars = 0
    for message in messages:
        role = str(message.get("role") or "")
        content = _safe_recent_message_content(role, str(message.get("content") or ""))
        if not content:
            continue
        remaining = 6000 - total_chars
        if remaining <= 0:
            break
        content = content[: min(900, remaining)]
        lines.append(f"- {labels[role]}: {content}")
        total_chars += len(content)
        if message.get("id"):
            message_ids.append(str(message["id"]))
    visible_head = next(
        (
            message
            for message in reversed(state.get("recent_messages", []))
            if message.get("id") and message.get("role") in {"user", "assistant", "tool"}
        ),
        {},
    )
    manifest = {
        "message_ids": message_ids,
        "message_count": len(lines),
        "character_count": total_chars,
        "source": "latest_durable_same_conversation_messages",
        "current_user_message_excluded": True,
        "message_head_id": str(visible_head.get("id")) if visible_head else None,
        "message_head_created_at": (
            str(visible_head.get("created_at"))
            if visible_head.get("created_at")
            else None
        ),
    }
    if not lines:
        return "", manifest
    return (
        "Recent same-Conversation messages "
        "(authoritative short-term context, oldest to newest):\n"
        + "\n".join(lines),
        manifest,
    )


def _safe_recent_message_content(role: str, content: str) -> str:
    if role != "tool":
        return content.strip()
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return content.strip()
    if not isinstance(payload, dict):
        return content.strip()
    capability = payload.get("capability") or "tool"
    status = payload.get("status") or "recorded"
    output = payload.get("output")
    return f"{capability} {status}: {_text(output)}"


def _join(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, list):
        rendered = []
        for item in value[:6]:
            if isinstance(item, dict):
                rendered.append(str(item.get("label") or item.get("name") or item.get("value") or item))
            else:
                rendered.append(str(item))
        return ", ".join(rendered)
    return str(value)


def _text(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value).strip() if value is not None else ""


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != [] and value != {}


def _relationship_confidence(value: Any) -> str:
    if not isinstance(value, dict) or not value:
        return ""
    labels = []
    for dimension, stats in value.items():
        if not isinstance(stats, dict):
            continue
        width = float(stats.get("interval_high", 1.0)) - float(stats.get("interval_low", 0.0))
        label = "limited" if width >= 0.55 else ("moderate" if width >= 0.3 else "strong")
        labels.append(f"{dimension}={label}")
    return ", ".join(labels)


def _preference_label(key: str, value: Any) -> str:
    labels = {
        "response_length": {
            "concise": "concise unless the task needs detail",
            "balanced": "balanced detail",
            "detailed": "thorough and structured",
        },
        "guidance_style": {
            "listen_first": "listen and understand before advising",
            "ask_then_advise": "ask clarifying questions before advising",
            "direct_help": "offer direct, actionable help",
        },
        "correction_style": {
            "gentle": "correct gently and preserve dignity",
            "direct": "correct clearly and directly",
            "collaborative": "work through corrections together",
        },
        "humor_style": {
            "restrained": "use humor sparingly",
            "natural": "use light humor when natural",
            "playful": "allow a more playful tone within boundaries",
        },
        "conflict_style": {
            "calm_clarify": "slow down and clarify misunderstandings",
            "direct_discuss": "discuss disagreement directly and respectfully",
            "give_space": "avoid pressing and allow space before revisiting",
        },
    }
    return labels.get(key, {}).get(str(value), "")


def _tool_context(tool: dict[str, Any]) -> str:
    if not tool:
        return ""
    status = tool.get("status")
    lines = [
        f"Capability: {tool.get('capability')}",
        f"Run status: {status}",
        f"ToolRun ID: {tool.get('id')}",
    ]
    if status == "awaiting_input":
        lines.append(f"Missing required fields: {', '.join(tool.get('missing_fields') or [])}")
        lines.append("Ask naturally for only the missing information. Do not claim execution.")
    elif status == "awaiting_confirmation":
        lines.append(f"Confirmation summary: {tool.get('confirmation_summary')}")
        lines.append("Ask for explicit confirmation. Do not claim the side effect already happened.")
    elif status == "succeeded":
        lines.append(
            f"Verified result observation: {_safe_tool_output(tool.get('output_json'))}"
        )
        lines.append("Answer from the verified result, preserve uncertainty, and mention useful source provenance naturally.")
    elif status == "retry_scheduled":
        lines.append(f"Structured failure: {_safe_tool_error(tool.get('error_json'))}")
        lines.append(f"Next retry: {tool.get('next_attempt_at')}")
        lines.append("Explain that execution failed and a durable retry is scheduled; do not invent a result.")
    elif status in {"failed", "timed_out", "blocked", "cancelled"}:
        lines.append(
            f"Structured outcome: {_safe_tool_error(tool.get('error_json') or tool.get('terminal_reason'))}"
        )
        lines.append(
            "Report only the observed outcome and valid next actions. Do not speculate "
            "that a provider database is outdated or broken unless the observation says so."
        )
    return "Current bounded tool operation:\n- " + "\n- ".join(lines)


def _task_context(task: dict[str, Any]) -> str:
    if not task:
        return ""
    steps = task.get("steps") if isinstance(task.get("steps"), list) else []
    lines = [
        f"TaskRun: {_text(task.get('task_run_id'))}",
        f"Goal: {_text(task.get('goal'))[:1200]}",
        f"Status: {_text(task.get('status'))}",
        f"Acceptance: {_text(task.get('acceptance_state'))}",
    ]
    for item in steps[:6]:
        if not isinstance(item, dict):
            continue
        lines.append(
            "Step "
            f"{_text(item.get('order'))}: {_text(item.get('title'))[:300]} "
            f"[{_text(item.get('status'))}; {_text(item.get('executor_type'))}]"
        )
        observation = item.get("observation")
        if isinstance(observation, dict) and observation:
            lines.append(
                f"Step {_text(item.get('order'))} observation: "
                f"{_safe_tool_output(observation)[:1200]}"
            )
    if task.get("stop_reason"):
        lines.append(f"Stop reason: {_text(task.get('stop_reason'))}")
    status = _text(task.get("status"))
    if status in {"completed", "blocked", "failed", "cancelled"}:
        lines.append(
            "This is the terminal task state for the current reply. Summarize "
            "what succeeded, what did not, and which evidence is available."
        )
    if status in {"blocked", "failed"}:
        lines.append(
            "Offer concise next choices: correct or add missing information, "
            "retry the failed goal in a new repair turn, or stop. Never say the "
            "task is still running when the durable state is terminal."
        )
    lines.append(
        "Report only this durable task state. Do not claim blocked, pending, "
        "unverified, or confirmation-gated work is complete. Tool cards remain "
        "the execution evidence; do not duplicate their raw payload."
    )
    return "Current durable task operation:\n- " + "\n- ".join(lines)


def _safe_tool_output(value: Any) -> str:
    """Render bounded scalar observations instead of injecting raw tool JSON."""
    if not isinstance(value, dict):
        return _text(value)[:1200]
    lines = []
    for key, item in list(value.items())[:20]:
        if isinstance(item, (str, int, float, bool)) or item is None:
            rendered = _text(item)[:500]
        elif isinstance(item, list):
            rendered = ", ".join(_text(part)[:120] for part in item[:8])
        elif isinstance(item, dict):
            rendered = ", ".join(
                f"{nested_key}={_text(nested_value)[:120]}"
                for nested_key, nested_value in list(item.items())[:8]
                if isinstance(nested_value, (str, int, float, bool))
                or nested_value is None
            )
        else:
            continue
        lines.append(f"{key}={rendered}")
    return "; ".join(lines)[:6000]


def _safe_tool_error(value: Any) -> str:
    if not isinstance(value, dict):
        return _text(value)[:1200]
    details = value.get("details") if isinstance(value.get("details"), dict) else {}
    attempts = details.get("attempts") if isinstance(details.get("attempts"), list) else []
    attempted_queries = [
        str(item.get("query"))
        for item in attempts[:6]
        if isinstance(item, dict) and item.get("query")
    ]
    fields = [
        ("code", value.get("code")),
        ("message", value.get("message")),
        ("resolution_status", details.get("resolution_status")),
        ("attempted_queries", attempted_queries),
        ("requested_date", details.get("requested_date")),
        ("supported_history_start", details.get("supported_history_start")),
        ("supported_forecast_end", details.get("supported_forecast_end")),
        ("data_route", details.get("data_route")),
    ]
    return "; ".join(
        f"{key}={_text(item)}"
        for key, item in fields
        if _present(item)
    )[:2000]
