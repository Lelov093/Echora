"""Bounded hybrid tool selection and parameter completion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider
from app.tools.capabilities import CAPABILITIES


_GATE_PATTERNS = (
    r"https?://", r"搜索|查一下|查找|网页|链接|提醒|闹钟|日程|安排|天气|温度|下雨",
    r"翻译|译成|汇率|换算|币|记一笔|记下来|笔记|文件|文档",
    r"\b(search|find|read this|remind|calendar|schedule|weather|translate|exchange|currency|note|file)\b",
)
_CONFIRM = re.compile(r"^(确认|同意|执行|可以|好的|yes|confirm|go ahead)[。.!！ ]*$", re.I)
_CANCEL = re.compile(r"^(取消|不要|算了|拒绝|no|cancel|stop)[。.!！ ]*$", re.I)


@dataclass
class SelectionResult:
    capability: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    confidence: float = 0.0
    rationale: str = ""
    provider_name: str | None = None
    model_name: str | None = None
    action: str = "select"
    continues_tool_run: bool = False
    changed_fields: list[str] = field(default_factory=list)


def confirmation_action(text: str) -> str | None:
    compact = text.strip()
    if _CONFIRM.fullmatch(compact):
        return "confirm"
    if _CANCEL.fullmatch(compact):
        return "cancel"
    return None


def may_request_tool(text: str) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in _GATE_PATTERNS)


def select_tool(
    text: str,
    *,
    pending: dict[str, Any] | None = None,
    prior_terminal: dict[str, Any] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
) -> SelectionResult:
    conversation_context = _selection_context(text, recent_messages or [])
    if (
        pending is None
        and prior_terminal is None
        and not may_request_tool(text)
        and not conversation_context
    ):
        return SelectionResult(rationale="no_explicit_tool_signal")
    if pending:
        action = confirmation_action(text)
        if action and pending.get("status") == "awaiting_confirmation":
            return SelectionResult(capability=pending.get("capability"), action=action, confidence=1.0, rationale="explicit_confirmation_action")
    provider = OpenAICompatibleProvider()
    catalog = {
        key: {
            "description": spec.description,
            "input_schema": spec.input_schema,
            "side_effect": spec.side_effect,
        }
        for key, spec in CAPABILITIES.items()
    }
    pending_text = json.dumps(pending or {}, ensure_ascii=False, default=str)
    prior_terminal_text = json.dumps(
        prior_terminal or {}, ensure_ascii=False, default=str
    )
    context_text = json.dumps(conversation_context, ensure_ascii=False, default=str)
    system = """你是 Echora 的受限工具路由器，不是执行器。只输出一个 JSON 对象，不使用 Markdown。
只能选择目录中的一个 capability。普通聊天、建议、虚构请求或不明确意图必须返回 capability=null。
arguments 必须只含 schema 声明字段。日期时间必须是带时区的 ISO-8601；不猜测地点、币种、目标语言、时间或文件 ID。
missing_fields 列出执行所必需但用户没有提供的字段。side_effect 不代表用户已确认。
输出格式：{"capability":string|null,"arguments":object,"missing_fields":string[],"confidence":0..1,"rationale":string,"continues_tool_run":boolean,"changed_fields":string[]}。"""
    prompt = (
        f"当前时间：{datetime.now().astimezone().isoformat()}\n"
        f"工具目录：{json.dumps(catalog, ensure_ascii=False)}\n"
        f"待补全的既有请求：{pending_text}\n"
        f"最近一个只读终态工具执行：{prior_terminal_text}\n"
        f"用户本轮输入：{text}"
    )
    prompt += (
        f"\nRecent same-Conversation context: {context_text}\n"
        "Use this context only when the current input directly continues, corrects, "
        "or completes parameters for an earlier request. For an unrelated new message, "
        "return capability=null. Set continues_tool_run=true only when the turn repairs "
        "or follows up the supplied terminal run, and list the changed argument fields."
    )
    try:
        raw = provider.generate(system, prompt)
        payload = _parse_object(raw["content"])
    except (LLMProviderError, ValueError, KeyError, TypeError):
        return _deterministic_fallback(
            text, pending=pending, prior_terminal=prior_terminal
        )
    capability = payload.get("capability")
    if capability not in CAPABILITIES:
        capability = None
    confidence = max(0.0, min(1.0, float(payload.get("confidence") or 0.0)))
    if confidence < 0.72:
        capability = None
    return SelectionResult(
        capability=capability,
        arguments=payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {},
        missing_fields=[str(item) for item in payload.get("missing_fields", []) if isinstance(item, str)],
        confidence=confidence,
        rationale=str(payload.get("rationale") or "provider_selection"),
        provider_name=raw.get("provider"),
        model_name=raw.get("model"),
        continues_tool_run=bool(
            prior_terminal
            and capability
            and capability == prior_terminal.get("capability")
            and payload.get("continues_tool_run")
        ),
        changed_fields=[
            str(item)
            for item in payload.get("changed_fields", [])
            if isinstance(item, str)
        ],
    )


def _selection_context(
    current_text: str,
    recent_messages: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Return a bounded window only for a potentially elliptical current turn."""
    compact = current_text.strip()
    if not compact or len(compact) > 120:
        return []
    selected: list[dict[str, str]] = []
    skipped_current = False
    for message in reversed(recent_messages):
        content = str(message.get("content") or "").strip()
        role = str(message.get("role") or "")
        if not content or role not in {"user", "assistant", "tool"}:
            continue
        if not skipped_current and role == "user" and content == compact:
            skipped_current = True
            continue
        selected.append({"role": role, "content": content[:800]})
        if len(selected) >= 4:
            break
    ordered = list(reversed(selected))
    if not any(
        item["role"] == "tool" or may_request_tool(item["content"])
        for item in ordered
    ):
        return []
    return ordered


def _parse_object(content: str) -> dict[str, Any]:
    compact = content.strip()
    if compact.startswith("```"):
        compact = re.sub(r"^```(?:json)?\s*|\s*```$", "", compact, flags=re.I)
    decoder = json.JSONDecoder()
    start = compact.find("{")
    if start < 0:
        raise ValueError("missing JSON object")
    payload, _ = decoder.raw_decode(compact[start:])
    if not isinstance(payload, dict):
        raise ValueError("selection is not an object")
    return payload


def _deterministic_fallback(
    text: str,
    *,
    pending: dict[str, Any] | None,
    prior_terminal: dict[str, Any] | None = None,
) -> SelectionResult:
    if pending:
        return SelectionResult(
            capability=pending.get("capability"),
            arguments={**(pending.get("input_json") or {}), "followup_text": text},
            missing_fields=list(pending.get("missing_fields") or []),
            confidence=0.4,
            rationale="provider_unavailable_pending_input_not_guessed",
        )
    url = re.search(r"https?://\S+", text)
    if url and re.search(r"读|看|总结|网页|链接|read|summar", text, re.I):
        return SelectionResult(capability="web_read", arguments={"url": url.group(0).rstrip("，。,.!！")}, confidence=0.9, rationale="explicit_url_read_fallback")
    return SelectionResult(rationale="selection_provider_unavailable_no_safe_fallback")
