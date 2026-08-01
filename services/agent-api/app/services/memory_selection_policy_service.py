"""Companion-scoped control for assistive memory selection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import BoundarySetting, Companion
from app.memory.learned_reranker import FEATURE_SCHEMA, latest_shadow_model
from app.services import learned_policy_readiness_service, settings_service


CONTRACT_VERSION = "memory-selection-policy.v1"
# Persisted compatibility keys. Renaming them would orphan existing Companion settings.
RULE_KEY = "memory_reranker_canary"
HISTORY_KEY = "memory_reranker_canary_history"


class PolicyRevisionConflict(ValueError):
    pass


class PolicyReadinessBlocked(ValueError):
    def __init__(self, message: str, details: dict[str, Any]):
        super().__init__(message)
        self.details = details


def get_policy(companion_id: uuid.UUID) -> dict[str, Any]:
    with settings_service.get_session() as session:
        companion = session.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")
        row = session.execute(
            select(BoundarySetting).where(
                BoundarySetting.companion_id == companion_id
            )
        ).scalar_one_or_none()
        stored = dict((row.boundary_rules or {}).get(RULE_KEY) or {}) if row else {}
    return _projection(companion_id, stored)


def update_policy(
    companion_id: uuid.UUID,
    *,
    enabled: bool,
    expected_revision: int,
) -> dict[str, Any]:
    evidence = _eligibility(companion_id)
    if enabled and not evidence["eligible"]:
        raise PolicyReadinessBlocked(
            "Memory selection assistive mode is blocked by readiness evidence",
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
        current = dict(rules.get(RULE_KEY) or {})
        revision = int(current.get("revision", 0))
        if revision != expected_revision:
            raise PolicyRevisionConflict(
                f"Memory selection policy revision changed from "
                f"{expected_revision} to {revision}"
            )
        history = list(rules.get(HISTORY_KEY) or [])
        history.append({**current, "replaced_at": now})
        rules[HISTORY_KEY] = history[-20:]
        rules[RULE_KEY] = {
            "contract_version": CONTRACT_VERSION,
            "revision": revision + 1,
            "opt_in": bool(enabled),
            "requested_mode": "assistive" if enabled else "shadow",
            "readiness_run_id": evidence.get("readiness_run_id"),
            "model_run_id": evidence.get("model_run_id") if enabled else None,
            "model_version": evidence.get("model_version") if enabled else None,
            "updated_at": now,
            "updated_from": "companion_settings",
            "rollback_reason": None if enabled else "user_disabled",
        }
        row.boundary_rules = rules
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
    return get_policy(companion_id)


def rollback_policy(
    companion_id: uuid.UUID, *, expected_revision: int
) -> dict[str, Any]:
    return update_policy(
        companion_id,
        enabled=False,
        expected_revision=expected_revision,
    )


def resolve_for_retrieval(
    companion_id: uuid.UUID,
    learned_shadow: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed to heuristic without changing the persisted policy."""
    try:
        policy = get_policy(companion_id)
        if not policy["opt_in"]:
            return _runtime_projection(policy, "shadow_not_opted_in")
        if policy["status"] != "assistive":
            return _runtime_projection(
                policy, policy.get("block_reason") or "readiness_blocked"
            )
        if learned_shadow.get("fallback_reason"):
            return _runtime_projection(
                policy, f"shadow_{learned_shadow['fallback_reason']}"
            )
        if learned_shadow.get("model_run_id") != policy.get("model_run_id"):
            return _runtime_projection(policy, "model_version_changed")
        return {
            **_runtime_projection(policy, None),
            "policy_mode": "assistive",
            "user_visible_policy": "learned_assistive",
            "applied": True,
        }
    except Exception as exc:
        return {
            "contract_version": CONTRACT_VERSION,
            "policy_mode": "heuristic",
            "user_visible_policy": "heuristic",
            "applied": False,
            "fallback_reason": f"policy_resolution_failed:{type(exc).__name__}",
            "rollback_available": True,
        }


def _projection(
    companion_id: uuid.UUID, stored: dict[str, Any]
) -> dict[str, Any]:
    evidence = _eligibility(companion_id)
    opt_in = bool(stored.get("opt_in"))
    stored_model_matches = (
        stored.get("model_run_id") == evidence.get("model_run_id")
        and stored.get("model_version") == evidence.get("model_version")
    )
    enabled = opt_in and evidence["eligible"] and stored_model_matches
    if enabled:
        status, block_reason = "assistive", None
    elif opt_in and not evidence["eligible"]:
        status, block_reason = "heuristic_fallback", evidence["block_reason"]
    elif opt_in and not stored_model_matches:
        status, block_reason = "heuristic_fallback", "model_version_changed"
    else:
        status, block_reason = "shadow", evidence["block_reason"]
    return {
        "contract_version": CONTRACT_VERSION,
        "companion_id": str(companion_id),
        "revision": int(stored.get("revision", 0)),
        "opt_in": opt_in,
        "requested_mode": stored.get("requested_mode", "shadow"),
        "status": status,
        "effective_mode": "assistive" if enabled else "heuristic",
        "block_reason": block_reason,
        "readiness": evidence,
        "readiness_run_id": stored.get("readiness_run_id"),
        "model_run_id": stored.get("model_run_id"),
        "model_version": stored.get("model_version"),
        "updated_at": stored.get("updated_at"),
        "rollback_available": opt_in,
        "active_allowed": False,
        "cross_companion_weights_allowed": False,
        "governance_preset_can_activate": False,
    }


def _eligibility(companion_id: uuid.UUID) -> dict[str, Any]:
    gate = learned_policy_readiness_service.latest_readiness(companion_id)
    model = latest_shadow_model(companion_id)
    schema_ok = bool(
        model
        and tuple((model.get("score_json") or {}).get("feature_schema") or ())
        == FEATURE_SCHEMA
    )
    model_ready = bool(
        model and (model.get("score_json") or {}).get("model_status") == "ready"
    )
    readiness_ready = bool(
        gate.get("status") == "ready_for_assistive_review"
        and gate.get("assistive_review_allowed") is True
    )
    eligible = readiness_ready and schema_ok and model_ready
    reasons = []
    if not readiness_ready:
        reasons.append(f"readiness:{gate.get('status', 'not_evaluated')}")
    if not model_ready:
        reasons.append("shadow_model_not_ready")
    if model and not schema_ok:
        reasons.append("feature_schema_mismatch")
    return {
        "eligible": eligible,
        "block_reason": None if eligible else ",".join(reasons),
        "readiness_status": gate.get("status", "not_evaluated"),
        "readiness_run_id": gate.get("evaluation_run_id"),
        "model_run_id": model.get("id") if model else None,
        "model_version": (model or {}).get("score_json", {}).get("model_version"),
        "model_ready": model_ready,
        "feature_schema_compatible": schema_ok,
        "assistive_review_allowed": bool(
            gate.get("assistive_review_allowed")
        ),
    }


def _runtime_projection(
    policy: dict[str, Any], fallback_reason: str | None
) -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "policy_mode": "heuristic",
        "user_visible_policy": "heuristic",
        "applied": False,
        "fallback_reason": fallback_reason,
        "revision": policy.get("revision"),
        "model_run_id": policy.get("model_run_id"),
        "readiness_run_id": policy.get("readiness_run_id"),
        "rollback_available": policy.get("rollback_available", False),
    }
