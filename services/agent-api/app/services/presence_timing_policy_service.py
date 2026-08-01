"""Companion-and-surface-scoped control for assistive Presence timing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import BoundarySetting, Companion
from app.presence.contextual_bandit import (
    ALGORITHM_VERSION,
    FEATURE_SCHEMA,
    POLICY_MODE,
    SAFE_ACTIONS,
)
from app.services import learned_policy_readiness_service, settings_service


CONTRACT_VERSION = "presence-timing-policy.v1"
# Persisted compatibility keys. Renaming them would orphan existing Companion settings.
RULE_KEY = "presence_bandit_canary"
HISTORY_KEY = "presence_bandit_canary_history"
POLICY_SURFACES = ("queue", "hub")
_ACTION_RISK = {
    "no_show": 0,
    "silence": 0,
    "defer": 1,
    "queue": 2,
    "hub": 3,
}
_EXECUTABLE_ACTIONS = {"no_show", "silence", "queue", "hub"}


class PolicyRevisionConflict(ValueError):
    pass


class PolicyReadinessBlocked(ValueError):
    def __init__(self, message: str, details: dict[str, Any]):
        super().__init__(message)
        self.details = details


def get_policy(companion_id: uuid.UUID, surface: str) -> dict[str, Any]:
    surface = _validate_surface(surface)
    with settings_service.get_session() as session:
        companion = session.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")
        row = session.execute(
            select(BoundarySetting).where(
                BoundarySetting.companion_id == companion_id
            )
        ).scalar_one_or_none()
        root = dict((row.boundary_rules or {}).get(RULE_KEY) or {}) if row else {}
        stored = dict((root.get("surfaces") or {}).get(surface) or {})
        revision = int(root.get("revision", 0))
    return _projection(companion_id, surface, revision, stored)


def update_policy(
    companion_id: uuid.UUID,
    *,
    surface: str,
    enabled: bool,
    expected_revision: int,
) -> dict[str, Any]:
    surface = _validate_surface(surface)
    evidence = _eligibility(companion_id)
    if enabled and not evidence["eligible"]:
        raise PolicyReadinessBlocked(
            "Presence timing assistive mode is blocked by readiness evidence",
            evidence,
        )
    now = datetime.now(timezone.utc).isoformat()
    with settings_service.get_session() as session:
        companion = session.get(Companion, companion_id, with_for_update=True)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")
        row = session.execute(
            select(BoundarySetting)
            .where(BoundarySetting.companion_id == companion_id)
            .with_for_update()
        ).scalar_one_or_none()
        if row is None:
            row = BoundarySetting(
                user_id=companion.user_id,
                companion_id=companion_id,
            )
            session.add(row)
            session.flush()
        rules = dict(row.boundary_rules or {})
        root = dict(rules.get(RULE_KEY) or {})
        revision = int(root.get("revision", 0))
        if revision != expected_revision:
            raise PolicyRevisionConflict(
                f"Presence timing policy revision changed from "
                f"{expected_revision} to {revision}"
            )
        surfaces = dict(root.get("surfaces") or {})
        current = dict(surfaces.get(surface) or {})
        history = list(rules.get(HISTORY_KEY) or [])
        history.append(
            {
                "surface": surface,
                "revision": revision,
                **current,
                "replaced_at": now,
            }
        )
        surfaces[surface] = {
            "opt_in": bool(enabled),
            "requested_mode": "assistive" if enabled else "shadow",
            "readiness_run_id": evidence.get("readiness_run_id"),
            "algorithm_version": ALGORITHM_VERSION if enabled else None,
            "feature_schema": list(FEATURE_SCHEMA) if enabled else [],
            "updated_at": now,
            "updated_from": "companion_settings",
            "rollback_reason": None if enabled else "user_disabled",
        }
        rules[HISTORY_KEY] = history[-40:]
        rules[RULE_KEY] = {
            "contract_version": CONTRACT_VERSION,
            "revision": revision + 1,
            "surfaces": surfaces,
            "updated_at": now,
        }
        row.boundary_rules = rules
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
    return get_policy(companion_id, surface)


def rollback_policy(
    companion_id: uuid.UUID,
    *,
    surface: str,
    expected_revision: int,
) -> dict[str, Any]:
    return update_policy(
        companion_id,
        surface=surface,
        enabled=False,
        expected_revision=expected_revision,
    )


def resolve_for_presence(
    companion_id: uuid.UUID,
    *,
    surface: str,
    heuristic_action: str,
    shadow_policy: dict[str, Any],
    suppression: dict[str, Any],
) -> dict[str, Any]:
    """Resolve a non-escalating local Presence action or fail closed."""
    try:
        policy = get_policy(companion_id, surface)
        if suppression.get("hard_block") or suppression.get("suppress"):
            return _runtime_projection(policy, "safety_gate_authoritative")
        if not policy["opt_in"]:
            return _runtime_projection(policy, "shadow_not_opted_in")
        if policy["status"] != "assistive":
            return _runtime_projection(
                policy, policy.get("block_reason") or "readiness_blocked"
            )
        if shadow_policy.get("fallback_reason"):
            return _runtime_projection(
                policy, f"shadow_{shadow_policy['fallback_reason']}"
            )
        explanation = shadow_policy.get("explanation_json") or {}
        if explanation.get("algorithm_version") != policy.get("algorithm_version"):
            return _runtime_projection(policy, "algorithm_version_changed")
        if tuple(explanation.get("feature_schema") or ()) != FEATURE_SCHEMA:
            return _runtime_projection(policy, "feature_schema_changed")
        if explanation.get("random_user_exploration") is not False:
            return _runtime_projection(policy, "random_exploration_forbidden")
        action = str(shadow_policy.get("shadow_action") or "")
        if action not in SAFE_ACTIONS:
            return _runtime_projection(policy, "unsafe_action")
        if action not in _EXECUTABLE_ACTIONS:
            return _runtime_projection(policy, f"unsupported_action_effect:{action}")
        if _ACTION_RISK[action] > _ACTION_RISK.get(heuristic_action, 2):
            return _runtime_projection(policy, "interruptiveness_escalation_forbidden")
        return {
            **_runtime_projection(policy, None),
            "policy_mode": "assistive",
            "user_visible_policy": "presence_assistive",
            "applied": True,
            "selected_action": action,
        }
    except Exception as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "policy_mode": "heuristic",
            "user_visible_policy": "heuristic",
            "applied": False,
            "selected_action": heuristic_action,
            "fallback_reason": f"policy_resolution_failed:{type(exc).__name__}",
            "rollback_available": True,
        }


def _projection(
    companion_id: uuid.UUID,
    surface: str,
    revision: int,
    stored: dict[str, Any],
) -> dict[str, Any]:
    evidence = _eligibility(companion_id)
    opt_in = bool(stored.get("opt_in"))
    algorithm_matches = stored.get("algorithm_version") == ALGORITHM_VERSION
    schema_matches = tuple(stored.get("feature_schema") or ()) == FEATURE_SCHEMA
    enabled = opt_in and evidence["eligible"] and algorithm_matches and schema_matches
    if enabled:
        status, block_reason = "assistive", None
    elif opt_in and not evidence["eligible"]:
        status, block_reason = "heuristic_fallback", evidence["block_reason"]
    elif opt_in and not algorithm_matches:
        status, block_reason = "heuristic_fallback", "algorithm_version_changed"
    elif opt_in and not schema_matches:
        status, block_reason = "heuristic_fallback", "feature_schema_changed"
    else:
        status, block_reason = "shadow", evidence["block_reason"]
    return {
        "contract_version": CONTRACT_VERSION,
        "companion_id": str(companion_id),
        "surface": surface,
        "revision": revision,
        "opt_in": opt_in,
        "requested_mode": stored.get("requested_mode", "shadow"),
        "status": status,
        "effective_mode": "assistive" if enabled else "heuristic",
        "block_reason": block_reason,
        "readiness": evidence,
        "readiness_run_id": stored.get("readiness_run_id"),
        "algorithm_version": stored.get("algorithm_version"),
        "feature_schema": stored.get("feature_schema") or [],
        "updated_at": stored.get("updated_at"),
        "rollback_available": opt_in,
        "active_allowed": False,
        "random_user_exploration_allowed": False,
        "channel_outbound_allowed": False,
        "cross_companion_weights_allowed": False,
        "governance_preset_can_activate": False,
    }


def _eligibility(companion_id: uuid.UUID) -> dict[str, Any]:
    gate = learned_policy_readiness_service.latest_readiness(companion_id)
    presence = gate.get("presence") or {}
    presence_ready = presence.get("status") == "passed"
    runtime_shadow = POLICY_MODE == "shadow"
    eligible = presence_ready and runtime_shadow
    reasons = []
    if not presence_ready:
        reasons.append(
            f"presence_readiness:{presence.get('status', gate.get('status', 'not_evaluated'))}"
        )
    if not runtime_shadow:
        reasons.append("shadow_policy_not_ready")
    return {
        "eligible": eligible,
        "block_reason": None if eligible else ",".join(reasons),
        "readiness_status": presence.get(
            "status", gate.get("status", "not_evaluated")
        ),
        "readiness_run_id": gate.get("evaluation_run_id"),
        "algorithm_version": ALGORITHM_VERSION,
        "feature_schema": list(FEATURE_SCHEMA),
        "shadow_policy_ready": runtime_shadow,
        "presence_assistive_review_allowed": presence_ready,
        "overall_gate_status": gate.get("status", "not_evaluated"),
    }


def _runtime_projection(
    policy: dict[str, Any], fallback_reason: str | None
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "policy_mode": "heuristic",
        "user_visible_policy": "heuristic",
        "applied": False,
        "selected_action": None,
        "fallback_reason": fallback_reason,
        "surface": policy.get("surface"),
        "revision": policy.get("revision"),
        "algorithm_version": policy.get("algorithm_version"),
        "readiness_run_id": policy.get("readiness_run_id"),
        "rollback_available": policy.get("rollback_available", False),
    }


def _validate_surface(surface: str) -> str:
    normalized = str(surface).strip().lower()
    if normalized not in POLICY_SURFACES:
        raise ValueError("Presence timing policy surface must be queue or hub")
    return normalized
