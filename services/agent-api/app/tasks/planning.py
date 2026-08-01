"""Provider-backed, fail-closed planning for explicit multi-step user tasks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider
from app.tools.capabilities import CAPABILITIES, requires_confirmation


MAX_TASK_STEPS = 6
_EXPLICIT_PLAN_PATTERNS = (
    r"计划并执行|规划并执行|分(?:成|为)?\s*\d*\s*步|逐步完成|依次完成|"
    r"先.+(?:再|然后|最后).+|执行并验证|完成并检查|"
    r"\bplan\s+and\s+(?:execute|verify)\b|\bstep[- ]by[- ]step\b|"
    r"\bfirst\b.+\bthen\b|\bdo .+ and then .+",
)
_MULTI_ACTION_TERMS = (
    "查询", "搜索", "阅读", "总结", "比较", "翻译", "换算", "创建",
    "记录", "提醒", "安排", "验证", "检查", "整理", "研究",
    "search", "read", "summarize", "compare", "translate", "create",
    "record", "remind", "schedule", "verify", "check", "research",
)


@dataclass(frozen=True)
class PlannedStep:
    order: int
    title: str
    executor_type: str
    capability: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    dependencies: list[int] = field(default_factory=list)
    risk_level: str = "low"
    acceptance_criteria: list[str] = field(default_factory=list)
    confirmation_required: bool = False


@dataclass(frozen=True)
class TaskPlan:
    should_plan: bool
    goal: str = ""
    steps: list[PlannedStep] = field(default_factory=list)
    rationale: str = ""
    provider_name: str | None = None
    model_name: str | None = None
    token_usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReplanDecision:
    action: str
    rationale: str
    arguments: dict[str, Any] = field(default_factory=dict)
    goal: str | None = None
    acceptance_criteria: list[str] = field(default_factory=list)
    provider_name: str | None = None
    model_name: str | None = None
    token_usage: dict[str, Any] = field(default_factory=dict)


def may_plan_task(text: str) -> bool:
    """Gate Provider planning away from ordinary chat and single-tool requests."""
    compact = " ".join(text.strip().split())
    if len(compact) < 12:
        return False
    if any(re.search(pattern, compact, re.I | re.S) for pattern in _EXPLICIT_PLAN_PATTERNS):
        return True
    action_count = sum(
        1 for term in _MULTI_ACTION_TERMS if re.search(re.escape(term), compact, re.I)
    )
    connector = bool(re.search(r"并且|并|以及|然后|再|最后|\band\b|\bthen\b", compact, re.I))
    return action_count >= 2 and connector


def plan_task(
    text: str,
    *,
    recent_messages: list[dict[str, Any]] | None = None,
) -> TaskPlan:
    if not may_plan_task(text):
        return TaskPlan(False, rationale="no_explicit_multistep_signal")
    catalog = {
        name: {
            "description": spec.description,
            "input_schema": spec.input_schema,
            "side_effect": spec.side_effect,
            "risk_level": spec.risk_level,
        }
        for name, spec in CAPABILITIES.items()
    }
    context = [
        {
            "role": str(item.get("role") or ""),
            "content": str(item.get("content") or "")[:600],
        }
        for item in (recent_messages or [])[-4:]
        if item.get("role") in {"user", "assistant"}
    ]
    system = """You are Echora's bounded task planner, not an executor.
Return exactly one JSON object without Markdown.
Create a task only for an explicit multi-step goal with dependencies, an artifact, or verification.
Ordinary companionship, discussion, advice, or a single tool request must return should_plan=false.
Use at most 6 steps. executor_type must be tool, research, or verify.
A tool step must use exactly one capability from the supplied typed catalog and schema-valid arguments; never invent a capability or missing value.
research is read-only evidence synthesis and cannot call write tools.
verify checks prior structured observations and cannot repair or write.
Dependencies may reference only earlier 1-based step numbers.
Side-effect tools remain confirmation-gated. Do not treat planning as confirmation.
Never include reasoning_content, another Companion's context, private memory, credentials, arbitrary URLs, shell, or filesystem access.
Output: {"should_plan":boolean,"goal":string,"rationale":string,"steps":[{"title":string,"executor_type":"tool|research|verify","capability":string|null,"arguments":object,"dependencies":integer[],"risk_level":"low|medium|high|critical","acceptance_criteria":string[]}]}."""
    prompt = (
        f"Current local time: {datetime.now().astimezone().isoformat()}\n"
        "Resolve user-supplied relative dates against that time; do not drop them.\n"
        f"Typed capability catalog: {json.dumps(catalog, ensure_ascii=False)}\n"
        f"Recent same-Conversation context: {json.dumps(context, ensure_ascii=False)}\n"
        f"Current user request: {text}"
    )
    provider = OpenAICompatibleProvider()
    try:
        raw = provider.generate(
            system,
            prompt,
            context={"temperature": 0.0, "max_tokens": 1800},
        )
        payload = _parse_object(raw["content"])
    except (LLMProviderError, ValueError, KeyError, TypeError):
        return TaskPlan(False, rationale="planner_provider_unavailable_fail_closed")
    if not payload.get("should_plan"):
        return TaskPlan(False, rationale=str(payload.get("rationale") or "provider_declined"))
    steps = _normalize_steps(payload.get("steps"))
    if len(steps) < 2:
        return TaskPlan(False, rationale="plan_requires_multiple_valid_steps")
    goal = str(payload.get("goal") or text).strip()[:1200]
    return TaskPlan(
        True,
        goal=goal,
        steps=steps,
        rationale=str(payload.get("rationale") or "provider_multistep_plan")[:1000],
        provider_name=raw.get("provider"),
        model_name=raw.get("model"),
        token_usage=raw.get("usage") if isinstance(raw.get("usage"), dict) else {},
    )


def replan_step(
    *,
    goal: str,
    step: dict[str, Any],
    completed_steps: list[dict[str, Any]],
    trigger: str,
    user_input: str | None = None,
) -> ReplanDecision:
    """Return a bounded repair decision without silently widening the task."""
    capability = str(step.get("capability") or "") or None
    catalog = (
        {
            "description": CAPABILITIES[capability].description,
            "input_schema": CAPABILITIES[capability].input_schema,
            "side_effect": CAPABILITIES[capability].side_effect,
        }
        if capability in CAPABILITIES
        else None
    )
    system = """You are Echora's bounded TaskStep replanner, not an executor.
Return exactly one JSON object without Markdown.
The only actions are retry, await_input, or stop.
Do not widen the supplied goal, invent missing facts, add capabilities, repeat completed steps, or treat planning as confirmation.
For retry, arguments must satisfy the supplied capability schema. For await_input or stop, preserve the previous arguments.
Only change the goal when the user explicitly corrected it, and keep it inside the original authorized outcome.
Never include reasoning_content, credentials, private memory, or another Companion's context.
Output: {"action":"retry|await_input|stop","rationale":string,"arguments":object,"goal":string|null,"acceptance_criteria":string[]}."""
    prompt = json.dumps(
        {
            "goal": goal[:1200],
            "trigger": trigger,
            "user_input": (user_input or "")[:1200],
            "failed_or_waiting_step": step,
            "completed_steps": completed_steps[:6],
            "capability_contract": catalog,
        },
        ensure_ascii=False,
        default=str,
    )
    provider = OpenAICompatibleProvider()
    try:
        raw = provider.generate(
            system,
            prompt,
            context={"temperature": 0.0, "max_tokens": 1000},
        )
        payload = _parse_object(raw["content"])
    except (LLMProviderError, ValueError, KeyError, TypeError):
        return ReplanDecision("stop", "replanner_provider_unavailable_fail_closed")
    action = str(payload.get("action") or "stop")
    if action not in {"retry", "await_input", "stop"}:
        action = "stop"
    arguments = payload.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    if action == "retry" and capability:
        try:
            validated = CAPABILITIES[capability].input_model.model_validate(arguments)
            arguments = validated.model_dump(mode="json", exclude_none=True)
        except (ValueError, TypeError):
            action = "await_input"
            arguments = dict(step.get("arguments") or {})
    elif action != "retry":
        arguments = dict(step.get("arguments") or {})
    requested_goal = str(payload.get("goal") or "").strip()
    next_goal = requested_goal[:1200] if requested_goal and user_input else None
    criteria = [
        str(item)[:300]
        for item in payload.get("acceptance_criteria", [])
        if isinstance(item, str) and item.strip()
    ][:5]
    return ReplanDecision(
        action=action,
        rationale=str(payload.get("rationale") or "bounded_replan")[:1000],
        arguments=arguments,
        goal=next_goal,
        acceptance_criteria=criteria,
        provider_name=raw.get("provider"),
        model_name=raw.get("model"),
        token_usage=raw.get("usage") if isinstance(raw.get("usage"), dict) else {},
    )


def _normalize_steps(value: Any) -> list[PlannedStep]:
    if not isinstance(value, list):
        return []
    normalized: list[PlannedStep] = []
    for raw in value[:MAX_TASK_STEPS]:
        if not isinstance(raw, dict):
            continue
        executor_type = str(raw.get("executor_type") or "")
        capability = str(raw.get("capability") or "") or None
        if executor_type not in {"tool", "research", "verify"}:
            continue
        if executor_type == "tool" and capability not in CAPABILITIES:
            continue
        if executor_type != "tool":
            capability = None
        order = len(normalized) + 1
        dependencies = sorted({
            int(item)
            for item in raw.get("dependencies", [])
            if isinstance(item, int) and 1 <= item < order
        })
        criteria = [
            str(item)[:300]
            for item in raw.get("acceptance_criteria", [])
            if isinstance(item, str) and item.strip()
        ][:5]
        if not criteria:
            criteria = ["A structured, non-empty observation is recorded."]
        arguments = raw.get("arguments") if isinstance(raw.get("arguments"), dict) else {}
        if executor_type == "tool" and capability:
            try:
                validated = CAPABILITIES[capability].input_model.model_validate(arguments)
                arguments = validated.model_dump(mode="json", exclude_none=True)
            except (ValueError, TypeError):
                continue
        risk = str(raw.get("risk_level") or "low")
        if risk not in {"low", "medium", "high", "critical"}:
            risk = "low"
        normalized.append(PlannedStep(
            order=order,
            title=str(raw.get("title") or f"Step {order}")[:300],
            executor_type=executor_type,
            capability=capability,
            arguments=arguments,
            dependencies=dependencies,
            risk_level=risk,
            acceptance_criteria=criteria,
            confirmation_required=bool(
                capability and requires_confirmation(capability, arguments)
            ),
        ))
    if normalized and all(step.executor_type != "verify" for step in normalized):
        if len(normalized) < MAX_TASK_STEPS:
            normalized.append(PlannedStep(
                order=len(normalized) + 1,
                title="Verify the task result against its acceptance criteria",
                executor_type="verify",
                dependencies=[step.order for step in normalized],
                acceptance_criteria=["Every required dependency has verified evidence."],
            ))
    return normalized


def _parse_object(content: str) -> dict[str, Any]:
    compact = str(content or "").strip()
    if compact.startswith("```"):
        compact = re.sub(r"^```(?:json)?\s*|\s*```$", "", compact, flags=re.I)
    start = compact.find("{")
    if start < 0:
        raise ValueError("missing JSON object")
    payload, _ = json.JSONDecoder().raw_decode(compact[start:])
    if not isinstance(payload, dict):
        raise ValueError("planner output is not an object")
    return payload
