"""Resolve and persist Companion-scoped governance automation safely.

The policy is stored inside the existing BoundarySetting.boundary_rules JSONB
document. No parallel source of truth or schema migration is introduced.
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import BoundarySetting, Companion
from app.services import memory_service, settings_service


CONTRACT_VERSION = "governance-policy.v1"
DEFAULT_MODE = "partial_auto"
DOMAIN_KEYS = (
    "memory",
    "growth",
    "relationship",
    "affect",
    "presence",
    "tools",
    "channels",
    "shared",
    "quality",
)
OVERRIDE_VALUES = {"inherit", "automatic", "manual"}

DOMAIN_CAPABILITIES: dict[str, dict[str, Any]] = {
    "memory": {
        "label": "记忆",
        "automation_support": "low_risk_private_commit",
        "automatic_available": True,
        "manual_required_for": ["sensitive", "correction", "shared", "cross_companion", "channel"],
    },
    "growth": {
        "label": "成长与人格",
        "automation_support": "automatic_detection_manual_apply",
        "automatic_available": False,
        "manual_required_for": ["profile_write", "core_persona", "boundary", "relationship"],
    },
    "relationship": {
        "label": "关系",
        "automation_support": "automatic_detection_manual_apply",
        "automatic_available": False,
        "manual_required_for": ["relationship_contract", "relationship_role", "boundary"],
    },
    "affect": {
        "label": "情绪表达",
        "automation_support": "bounded_runtime_separate_correction_gate",
        "automatic_available": False,
        "manual_required_for": ["correction", "expression_disable", "boundary_change"],
    },
    "presence": {
        "label": "主动陪伴",
        "automation_support": "schedule_policy_separate",
        "automatic_available": False,
        "manual_required_for": ["schedule", "destination", "quiet_focus_relaxation", "outbound"],
    },
    "tools": {
        "label": "工具",
        "automation_support": "risk_gated_runtime",
        "automatic_available": False,
        "manual_required_for": ["external_write", "destructive_action", "credential_use"],
    },
    "channels": {
        "label": "渠道",
        "automation_support": "binding_and_outbox_gated",
        "automatic_available": False,
        "manual_required_for": ["outbound", "binding", "revoke", "shared_memory"],
    },
    "shared": {
        "label": "共享与跨伙伴",
        "automation_support": "review_gated_only",
        "automatic_available": False,
        "manual_required_for": ["shared_memory", "cross_companion", "channel_memory", "continuation_capsule"],
    },
    "quality": {
        "label": "质量反馈",
        "automation_support": "trace_evaluation_bad_case_regression",
        "automatic_available": True,
        "manual_required_for": ["domain_state_application", "learned_policy_activation", "regression_resolution"],
    },
}

SAFETY_INVARIANTS = [
    "hard_stop_revoke_quiet_focus_override",
    "shared_cross_companion_channel_memory_review_gated",
    "core_persona_boundary_relationship_manual",
    "observer_never_auto_promoted",
    "memory_reranker_policy_mode_shadow",
    "presence_bandit_policy_mode_shadow",
]


class GovernanceRevisionConflict(ValueError):
    pass


def get_governance_policy(companion_id: uuid.UUID) -> dict[str, Any]:
    with settings_service.get_session() as session:
        companion = session.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")
        settings = session.execute(
            select(BoundarySetting).where(BoundarySetting.companion_id == companion_id)
        ).scalar_one_or_none()
        stored = _stored_policy(settings)
        rules = dict(settings.boundary_rules or {}) if settings is not None else {}
        history = rules.get("governance_policy_history")
        return _resolve_policy(
            companion_id,
            stored,
            history_count=len(history) if isinstance(history, list) else 0,
        )


def update_governance_policy(
    companion_id: uuid.UUID,
    *,
    mode: str,
    domain_overrides: dict[str, str],
    expected_revision: int,
) -> dict[str, Any]:
    if mode not in {"full_auto", "partial_auto", "manual"}:
        raise ValueError("Unsupported governance mode")
    unknown = set(domain_overrides) - set(DOMAIN_KEYS)
    if unknown:
        raise ValueError(f"Unsupported governance domains: {', '.join(sorted(unknown))}")
    if any(value not in OVERRIDE_VALUES for value in domain_overrides.values()):
        raise ValueError("Unsupported governance domain override")

    now = datetime.now(timezone.utc).isoformat()
    with settings_service.get_session() as session:
        companion = session.get(Companion, companion_id, with_for_update=True)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")
        settings = session.execute(
            select(BoundarySetting)
            .where(BoundarySetting.companion_id == companion_id)
            .with_for_update()
        ).scalar_one_or_none()
        if settings is None:
            settings = BoundarySetting(user_id=companion.user_id, companion_id=companion_id)
            session.add(settings)
            session.flush()

        rules = dict(settings.boundary_rules or {})
        current = _stored_policy(settings)
        current_revision = int(current.get("revision", 0))
        if current_revision != expected_revision:
            raise GovernanceRevisionConflict(
                f"Governance policy revision changed from {expected_revision} to {current_revision}"
            )

        history = list(rules.get("governance_policy_history") or [])
        history.append({
            "revision": current_revision,
            "mode": current.get("mode", DEFAULT_MODE),
            "domain_overrides": current.get("domain_overrides", {}),
            "replaced_at": now,
        })
        rules["governance_policy_history"] = history[-20:]
        rules["governance_policy"] = {
            "contract_version": CONTRACT_VERSION,
            "revision": current_revision + 1,
            "mode": mode,
            "domain_overrides": {
                key: domain_overrides.get(key, "inherit") for key in DOMAIN_KEYS
            },
            "updated_at": now,
            "updated_from": "settings_ui",
        }
        settings.boundary_rules = rules
        settings.updated_at = datetime.now(timezone.utc)
        session.commit()
        return _resolve_policy(companion_id, rules["governance_policy"], history_count=len(history[-20:]))


def rollback_governance_policy(
    companion_id: uuid.UUID,
    *,
    expected_revision: int,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with settings_service.get_session() as session:
        companion = session.get(Companion, companion_id, with_for_update=True)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")
        settings = session.execute(
            select(BoundarySetting)
            .where(BoundarySetting.companion_id == companion_id)
            .with_for_update()
        ).scalar_one_or_none()
        if settings is None:
            raise ValueError("No governance policy history is available")
        rules = dict(settings.boundary_rules or {})
        current = _stored_policy(settings)
        current_revision = int(current.get("revision", 0))
        if current_revision != expected_revision:
            raise GovernanceRevisionConflict(
                f"Governance policy revision changed from {expected_revision} to {current_revision}"
            )
        history = list(rules.get("governance_policy_history") or [])
        if not history:
            raise ValueError("No governance policy history is available")
        previous = history.pop()
        history.append({
            "revision": current_revision,
            "mode": current.get("mode", DEFAULT_MODE),
            "domain_overrides": current.get("domain_overrides", {}),
            "replaced_at": now,
            "reason": "rollback",
        })
        rules["governance_policy_history"] = history[-20:]
        rules["governance_policy"] = {
            "contract_version": CONTRACT_VERSION,
            "revision": current_revision + 1,
            "mode": previous.get("mode", DEFAULT_MODE),
            "domain_overrides": previous.get("domain_overrides", {}),
            "updated_at": now,
            "updated_from": "settings_rollback",
            "rolled_back_from_revision": current_revision,
            "restored_revision": previous.get("revision", 0),
        }
        settings.boundary_rules = rules
        settings.updated_at = datetime.now(timezone.utc)
        session.commit()
        return _resolve_policy(
            companion_id,
            rules["governance_policy"],
            history_count=len(history[-20:]),
        )


def resolve_memory_automation(companion_id: uuid.UUID) -> dict[str, Any]:
    policy = get_governance_policy(companion_id)
    domain = next(item for item in policy["domains"] if item["key"] == "memory")
    return {
        "enabled": domain["effective_mode"] == "automatic",
        "policy_revision": policy["revision"],
        "selected_mode": policy["mode"],
        "contract_version": policy["contract_version"],
    }


def quality_feedback_is_automatic(policy: dict[str, Any]) -> bool:
    domain = next(
        (item for item in policy.get("domains", []) if item.get("key") == "quality"),
        None,
    )
    return bool(domain and domain.get("effective_mode") == "automatic_feedback")


def auto_commit_memory_candidate(candidate_id: uuid.UUID, companion_id: uuid.UUID) -> dict[str, Any]:
    automation = resolve_memory_automation(companion_id)
    if not automation["enabled"]:
        return {"status": "manual_review", "reason": "memory_automation_disabled", **automation}
    result = memory_service.auto_commit_low_risk_memory_candidate(
        candidate_id,
        companion_id=companion_id,
        governance_evidence=automation,
    )
    if result.get("outcome") == "manual_review":
        return {
            "status": "manual_review",
            "reason": result.get("reason", "candidate_not_eligible"),
            "validation": result,
            **automation,
        }
    return {
        "status": "auto_committed",
        "reason": result.get("reason"),
        "persistence": _persistence_summary(result),
        **automation,
    }


def _persistence_summary(result: dict[str, Any]) -> dict[str, Any]:
    candidate = result.get("candidate") if isinstance(result.get("candidate"), dict) else {}
    memory = result.get("memory") if isinstance(result.get("memory"), dict) else {}
    return {
        "outcome": result.get("outcome"),
        "candidate_id": candidate.get("id"),
        "memory_id": memory.get("id"),
        "lifecycle_event_id": result.get("lifecycle_event_id"),
    }


def _stored_policy(settings: BoundarySetting | None) -> dict[str, Any]:
    rules = dict(settings.boundary_rules or {}) if settings is not None else {}
    stored = rules.get("governance_policy")
    return dict(stored) if isinstance(stored, dict) else {}


def _resolve_policy(
    companion_id: uuid.UUID,
    stored: dict[str, Any],
    *,
    history_count: int = 0,
) -> dict[str, Any]:
    mode = stored.get("mode") if stored.get("mode") in {"full_auto", "partial_auto", "manual"} else DEFAULT_MODE
    overrides = stored.get("domain_overrides") if isinstance(stored.get("domain_overrides"), dict) else {}
    domains = []
    for key in DOMAIN_KEYS:
        capability = deepcopy(DOMAIN_CAPABILITIES[key])
        requested = overrides.get(key, "inherit")
        if requested not in OVERRIDE_VALUES:
            requested = "inherit"
        desired = _desired_mode(mode, key, requested)
        available = bool(capability["automatic_available"])
        if key == "quality" and desired == "automatic":
            effective = "automatic_feedback"
            support_status = "supported"
        elif desired == "automatic" and available:
            effective = "automatic"
            support_status = "supported"
        elif desired == "automatic":
            effective = "manual"
            support_status = "not_yet_supported"
        else:
            effective = "manual"
            support_status = "supported"
        domains.append({
            "key": key,
            **capability,
            "override": requested,
            "requested_mode": desired,
            "effective_mode": effective,
            "support_status": support_status,
        })
    return {
        "contract_version": CONTRACT_VERSION,
        "companion_id": str(companion_id),
        "revision": int(stored.get("revision", 0)),
        "mode": mode,
        "domain_overrides": {key: overrides.get(key, "inherit") for key in DOMAIN_KEYS},
        "domains": domains,
        "safety_invariants": SAFETY_INVARIANTS,
        "history_count": history_count,
        "can_rollback": history_count > 0,
        "updated_at": stored.get("updated_at"),
        "learned_policy_status": {
            "memory_reranker": "shadow",
            "contextual_presence_bandit": "shadow",
        },
    }


def _desired_mode(mode: str, key: str, override: str) -> str:
    if override != "inherit":
        return override
    if mode == "manual":
        return "manual"
    if mode == "full_auto":
        return "automatic"
    return "automatic" if key in {"memory", "quality"} else "manual"
