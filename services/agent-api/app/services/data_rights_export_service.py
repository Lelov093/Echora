"""User-owned, Companion-scoped data export without secrets or embeddings."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.db.base import Base
from app.db.models import Companion
from app.services.settings_service import get_session


CONTRACT_VERSION = "companion-data-export.v1"
SENSITIVE_KEY_PARTS = {
    "api_key",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
}

EXPORT_FIELDS: dict[str, tuple[str, ...]] = {
    "companion_identity_profiles": (
        "display_name", "identity_summary", "origin_story",
        "self_continuity_summary", "core_traits_json", "identity_labels_json",
        "voice_style_hint", "avatar_style_hint", "profile_status",
        "created_at", "updated_at",
    ),
    "companion_persona_profiles": (
        "persona_summary", "communication_style_summary",
        "tone_descriptors_json", "core_values_json", "response_preferences_json",
        "persona_lock_level", "drift_guard_level", "presence_style",
        "created_at", "updated_at",
    ),
    "companion_relationship_contracts": (
        "relationship_role", "contract_status", "contract_summary",
        "collaboration_style_summary", "support_scope_json",
        "shared_memory_policy", "cross_companion_disclosure_policy",
        "contract_json", "created_at", "updated_at",
    ),
    "companion_boundary_profiles": (
        "boundary_json", "private_memory_default", "shared_memory_default",
        "global_memory_read_scope", "cross_companion_read_policy",
        "review_required_private_to_shared",
        "review_required_shared_to_private",
        "review_required_cross_companion_share", "presence_interrupt_policy",
        "created_at", "updated_at",
    ),
    "companion_visibility_policies": (
        "memory_visibility_policy", "user_global_memory_scope",
        "relationship_memory_scope", "allow_low_risk_summary_read",
        "allow_authorized_global_read", "allow_sensitive_global_read",
        "allow_other_companion_private_read", "visibility_rules_json",
        "created_at", "updated_at",
    ),
    "conversations": (
        "id", "title", "mode_key", "status", "retention_mode",
        "cross_session_memory_enabled", "history_visible",
        "retention_expires_at", "current_topic", "current_goal", "summary",
        "created_at", "updated_at", "deleted_at",
    ),
    "messages": (
        "id", "conversation_id", "role", "content", "content_format",
        "source_modality", "created_at", "updated_at", "deleted_at",
    ),
    "memories": (
        "id", "conversation_id", "type", "state", "visibility",
        "consent_status", "memory_scope_type", "memory_layer", "content",
        "summary", "content_revision", "source_message_ids", "source_modality",
        "importance", "confidence", "emotional_intensity", "goal_relevance",
        "relationship_impact", "correction_value", "memory_strength",
        "last_reactivated_at", "usage_feedback", "helpful_feedback",
        "impact_summary", "lifecycle_summary", "visibility_policy_json",
        "created_at", "updated_at", "deleted_at",
    ),
    "growth_records": (
        "id", "type", "content", "reason", "evidence_memory_ids",
        "evidence_message_ids", "impact_scope", "impact_json",
        "applied_to_profile", "status", "reverted_at", "revert_reason",
        "created_at", "updated_at",
    ),
    "relationship_states": (
        "id", "familiarity", "understanding", "collaboration", "trust",
        "emotional_closeness", "boundary_awareness", "continuity", "summary",
        "revision", "belief_state_json", "explanation_summary",
        "last_changed_at", "created_at", "updated_at",
    ),
    "relationship_state_revisions": (
        "id", "relationship_state_id", "revision", "operation", "reason",
        "snapshot_before_json", "snapshot_after_json", "belief_before_json",
        "belief_after_json", "created_at", "updated_at",
    ),
    "presence_schedules": (
        "id", "status", "pause_reason", "destination_mode",
        "bound_conversation_id", "timezone", "weekdays", "timing_mode",
        "fixed_minute_of_day", "window_start_minute", "window_end_minute",
        "cadence_mode", "fixed_interval_minutes",
        "random_interval_min_minutes", "random_interval_max_minutes",
        "next_occurrence_at", "last_delivered_at", "created_at", "updated_at",
    ),
    "boundary_settings": (
        "memory_save_policy", "sensitive_memory_policy", "proactive_level",
        "notification_surface", "allow_auto_memory_low_risk",
        "allow_proactive_presence", "allow_sensitive_memory_without_review",
        "suppressed_presence_types", "boundary_rules", "quiet_hours",
        "suppressed_presence_rules", "memory_confirmation_policy",
        "growth_confirmation_policy", "feedback_usage_policy",
        "continuity_visibility_policy", "max_presence_per_day",
        "min_presence_interval_minutes", "meaningful_silence_enabled",
        "created_at", "updated_at",
    ),
    "companion_affect_states": (
        "valence", "arousal", "home_valence", "home_arousal",
        "half_life_hours", "revision", "last_transition_at",
        "expression_enabled", "expression_intensity", "expression_json",
        "created_at", "updated_at",
    ),
    "channel_bindings": (
        "id", "binding_status", "binding_scope", "permission_scope",
        "outbound_policy", "memory_policy", "requires_user_approval",
        "can_receive_inbound", "can_send_outbound", "checkin_enabled",
        "memory_write_requires_review", "raw_message_storage_allowed",
        "revoked_at", "created_at", "updated_at",
    ),
    "discord_dm_conversation_bindings": (
        "id", "conversation_id", "binding_status", "binding_source",
        "revision", "last_inbound_at", "last_outbound_at", "revoked_at",
        "created_at", "updated_at",
    ),
    "tool_runs": (
        "id", "conversation_id", "capability", "adapter_name",
        "adapter_version", "status", "risk_level", "permission_required",
        "permission_granted", "confirmation_required", "confirmation_summary",
        "input_json", "output_json", "error_json", "evidence_refs",
        "started_at", "completed_at", "elapsed_ms", "created_at", "updated_at",
    ),
}


def export_companion_data(companion_id: uuid.UUID) -> dict[str, Any]:
    import app.db.models  # noqa: F401

    exported_at = datetime.now(timezone.utc)
    with get_session() as session:
        companion = session.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")

        sections = {
            table_name: _export_table(
                session,
                table_name,
                companion.id,
                fields,
            )
            for table_name, fields in EXPORT_FIELDS.items()
        }
        payload = {
            "contract_version": CONTRACT_VERSION,
            "exported_at": exported_at.isoformat(),
            "owner_id": str(companion.user_id),
            "companion": {
                "id": str(companion.id),
                "name": companion.name,
                "subtitle": companion.subtitle,
                "identity_prompt": companion.identity_prompt,
                "base_personality": companion.base_personality,
                "tone_profile": _safe_value(companion.tone_profile),
                "companion_profile": _safe_value(companion.companion_profile),
                "current_mode": companion.current_mode,
                "current_status": companion.current_status,
                "created_at": companion.created_at.isoformat(),
                "updated_at": companion.updated_at.isoformat(),
            },
            "sections": sections,
            "manifest": {
                "format": "json",
                "section_counts": {
                    name: len(rows)
                    for name, rows in sections.items()
                },
                "excluded": [
                    "secrets_and_credentials",
                    "embeddings_and_search_indexes",
                    "raw_cross_boundary_payloads",
                    "reasoning_content",
                    "internal_audit_metadata",
                ],
            },
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        payload["manifest"]["sha256"] = hashlib.sha256(canonical).hexdigest()
        return payload


def _export_table(
    session: Any,
    table_name: str,
    companion_id: uuid.UUID,
    fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    table = Base.metadata.tables[table_name]
    columns = [table.c[field] for field in fields]
    statement = select(*columns).where(table.c.companion_id == companion_id)
    if "created_at" in table.c:
        statement = statement.order_by(table.c.created_at.asc(), table.c.id.asc())
    return [
        {
            field: _safe_value(value)
            for field, value in zip(fields, row, strict=True)
        }
        for row in session.execute(statement)
    ]


def _safe_value(value: Any, *, key: str = "") -> Any:
    normalized_key = key.casefold()
    if any(part in normalized_key for part in SENSITIVE_KEY_PARTS):
        return "[redacted]"
    if isinstance(value, dict):
        return {
            str(child_key): _safe_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
