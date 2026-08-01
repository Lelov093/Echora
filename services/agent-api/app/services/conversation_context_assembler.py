"""Explicit, bounded Context Pack assembly for one Companion conversation turn."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any

from app.agents.state import ConversationAgentState


CONTRACT_VERSION = "conversation_context_pack_v3"
TOTAL_CHARACTER_BUDGET = 24_000


@dataclass(frozen=True)
class SectionPolicy:
    budget: int
    required: bool = False
    allow_llm: bool = True


SECTION_POLICIES: dict[str, SectionPolicy] = {
    "safety": SectionPolicy(3_000, required=True),
    "identity": SectionPolicy(2_500, required=True),
    "persona": SectionPolicy(2_500, required=True),
    "relationship_contract": SectionPolicy(2_000, required=True),
    "recent_conversation": SectionPolicy(6_500, required=True),
    "tool_operation": SectionPolicy(6_500, required=True),
    "task_operation": SectionPolicy(4_000, required=True),
    "relationship": SectionPolicy(2_000),
    "continuity": SectionPolicy(2_500),
    "context_documents": SectionPolicy(2_000),
    "memories": SectionPolicy(2_000),
    "growth": SectionPolicy(1_500),
    "affect": SectionPolicy(1_200),
    "room": SectionPolicy(1_500),
}


class ConversationContextAssembler:
    """Select and budget already-rendered sections under an auditable contract."""

    def assemble(
        self,
        state: ConversationAgentState,
        rendered_sections: list[tuple[str, str]],
        *,
        recent_manifest: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        snapshot = state.get("companion_context_snapshot") or {}
        selected_blocks: list[str] = []
        section_manifest: list[dict[str, Any]] = []
        total_chars = 0

        for name, original_block in rendered_sections:
            policy = SECTION_POLICIES.get(name, SectionPolicy(1_500))
            source_section = self._source_section(snapshot, name)
            source = source_section.get("source") or self._runtime_source(name)
            scope = source_section.get("scope") or self._scope(state)
            availability = source_section.get("availability") or (
                "available" if original_block else "empty"
            )
            allowed = policy.allow_llm and self._scope_matches(state, scope)
            exclusion_reason: str | None = None
            block = original_block.strip()

            if not allowed:
                block = ""
                exclusion_reason = "scope_mismatch_or_not_llm_allowed"
            elif not block:
                exclusion_reason = f"source_{availability}"
            else:
                block = block[: policy.budget]
                remaining = TOTAL_CHARACTER_BUDGET - total_chars
                if remaining <= 0 and not policy.required:
                    block = ""
                    exclusion_reason = "total_budget_exhausted"
                elif remaining < len(block) and not policy.required:
                    block = block[:remaining]
                    exclusion_reason = "included_truncated_by_total_budget"

            if block:
                selected_blocks.append(block)
                total_chars += len(block)

            entry = {
                "section": name,
                "name": name,
                "priority": self._priority(name),
                "source": source,
                "source_version": source.get("version"),
                "scope": scope,
                "availability": availability,
                "freshness": self._freshness(state, name, source, recent_manifest),
                "budget": {
                    "character_limit": policy.budget,
                    "character_used": len(block),
                    "token_estimate": (len(block) + 3) // 4,
                },
                "required": policy.required,
                "llm_allowed": allowed,
                "selection": "included" if block else "excluded",
                "reason": (
                    "required_context"
                    if block and policy.required
                    else (
                        "relevant_available_context"
                        if block
                        else exclusion_reason
                    )
                ),
                "selected": bool(block),
                "selection_reason": (
                    "required_context"
                    if block and policy.required
                    else ("relevant_available_context" if block else None)
                ),
                "exclusion_reason": exclusion_reason,
            }
            section_manifest.append(entry)

        manifest = {
            "contract_version": CONTRACT_VERSION,
            "generated_at": datetime.now().astimezone().isoformat(),
            "companion_id": state.get("companion_id"),
            "conversation_id": state.get("conversation_id"),
            "scope": self._scope(state),
            "character_budget": TOTAL_CHARACTER_BUDGET,
            "character_count": total_chars,
            "sections": section_manifest,
            "included_sections": [
                item["name"] for item in section_manifest if item["selected"]
            ],
            "excluded_sections": [
                {
                    "name": item["name"],
                    "reason": item["exclusion_reason"],
                }
                for item in section_manifest
                if not item["selected"]
            ],
            "recent_conversation": recent_manifest,
            "continuity_watermark": self._continuity_watermark(
                state, snapshot, recent_manifest
            ),
            "post_turn_effects_behind_message_head": bool(
                state.get("defer_post_turn_effects")
            ),
            "safety_gates": {
                "boundary_check": state.get("boundary_check") or {},
                "quiet_hours_configured": bool(
                    (state.get("boundary_settings") or {}).get("quiet_hours")
                ),
                "meaningful_silence_enabled": (
                    (state.get("boundary_settings") or {}).get(
                        "meaningful_silence_enabled", True
                    )
                ),
                "tool_hard_stop_rechecked_before_execution": True,
                "tool_revoked_permission_rechecked_before_execution": True,
            },
            "cross_companion_content_included": False,
        }
        manifest["fingerprint"] = hashlib.sha256(
            json.dumps(
                manifest,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        return "\n\n".join(selected_blocks), manifest

    @staticmethod
    def _source_section(snapshot: dict[str, Any], name: str) -> dict[str, Any]:
        aliases = {
            "safety": "boundary",
            "tool_operation": "tool_operation",
            "task_operation": "task_operation",
            "recent_conversation": "recent_conversation",
            "room": "room",
        }
        return snapshot.get(aliases.get(name, name)) or {}

    @staticmethod
    def _runtime_source(name: str) -> dict[str, Any]:
        source_types = {
            "recent_conversation": "latest_durable_same_conversation_messages",
            "tool_operation": "bounded_tool_observation",
            "task_operation": "durable_conversation_task_projection",
            "room": "review_gated_room_context",
        }
        return {
            "type": source_types.get(name, "conversation_runtime"),
            "id": None,
            "version": CONTRACT_VERSION,
        }

    @staticmethod
    def _priority(name: str) -> str:
        if name == "safety":
            return "non_bypassable_safety"
        if name in {"identity", "persona", "relationship_contract"}:
            return "companion_core"
        if name in {"recent_conversation"}:
            return "working_context"
        if name in {"tool_operation", "task_operation"}:
            return "execution_evidence"
        if name == "room":
            return "optional_scoped_context"
        return "long_term_context"

    @staticmethod
    def _scope(state: ConversationAgentState) -> dict[str, Any]:
        return {
            "user_id": state.get("user_id"),
            "companion_id": state.get("companion_id"),
            "conversation_id": state.get("conversation_id"),
            "visibility": "companion_private",
        }

    @classmethod
    def _scope_matches(
        cls, state: ConversationAgentState, scope: dict[str, Any]
    ) -> bool:
        expected = cls._scope(state)
        for key in ("user_id", "companion_id", "conversation_id"):
            actual = scope.get(key)
            if actual is not None and str(actual) != str(expected.get(key)):
                return False
        return not bool(scope.get("cross_companion_content_included"))

    @staticmethod
    def _freshness(
        state: ConversationAgentState,
        name: str,
        source: dict[str, Any],
        recent_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        if name == "recent_conversation":
            return {
                "status": "current",
                "message_head_id": recent_manifest.get("message_head_id"),
            }
        if name == "tool_operation":
            return {
                "status": "current_turn",
                "tool_run_id": (state.get("tool_context") or {}).get("id"),
            }
        if name == "task_operation":
            return {
                "status": "current_turn",
                "task_run_id": (state.get("task_context") or {}).get("task_run_id"),
                "plan_version": (state.get("task_run") or {}).get("plan_version"),
            }
        return {
            "status": "versioned" if source.get("version") else "unknown",
            "version": source.get("version"),
        }

    @staticmethod
    def _continuity_watermark(
        state: ConversationAgentState,
        snapshot: dict[str, Any],
        recent_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        continuity = snapshot.get("continuity") or {}
        source = continuity.get("source") or {}
        data = continuity.get("data") or {}
        snapshot_json = data.get("snapshot_json") or {}
        message_head_id = recent_manifest.get("message_head_id")
        version = source.get("version")
        latest_created_at = recent_manifest.get("message_head_created_at")
        stale: bool | None = None
        summary_through_message_id = snapshot_json.get(
            "summary_through_message_id"
        )
        if summary_through_message_id and message_head_id:
            stale = str(summary_through_message_id) != str(message_head_id)
        elif version and latest_created_at:
            try:
                stale = datetime.fromisoformat(str(version)) < datetime.fromisoformat(
                    str(latest_created_at)
                )
            except (TypeError, ValueError):
                stale = None
        return {
            "continuity_snapshot_id": source.get("id"),
            "continuity_version": version,
            "summary_through_message_id": summary_through_message_id,
            "source_trace_run_id": data.get("trace_run_id")
            or snapshot_json.get("source_trace_run_id"),
            "message_head_id": message_head_id,
            "message_head_created_at": latest_created_at,
            "stale_against_message_head": stale,
        }
