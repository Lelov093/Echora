"""Companion persona guard service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CompanionBoundaryProfile,
    CompanionPersonaDriftCheck,
    CompanionPersonaProfile,
    CompanionRelationshipContract,
    CrossCompanionMemoryReview,
    ParticipantMemoryPermission,
    PrivateToSharedMemoryReview,
)
from app.services.growth_consistency_service import score_growth_consistency

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def check_persona_drift(companion_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        persona = _get_persona_profile(s, companion_id)
        contract = _get_contract_profile(s, companion_id)
        boundary = _get_boundary_profile(s, companion_id)
        if persona is None or contract is None or boundary is None:
            return None

        proposed_persona = payload.get("proposed_persona_patch_json") or {}
        proposed_presence = payload.get("proposed_presence_patch_json") or {}
        profile_consistency = score_growth_consistency(
            companion_id,
            payload.get("profile_patch_preview")
            or {
                "persona": {**proposed_persona, **proposed_presence},
                "relationship": payload.get("proposed_relationship_patch_json")
                or {},
                "boundary": payload.get("proposed_boundary_patch_json") or {},
            },
        )
        drift_score = 0.0
        evidence: dict[str, Any] = {
            "baseline_presence_style": persona.presence_style,
            "baseline_persona_lock_level": persona.persona_lock_level,
            "baseline_drift_guard_level": persona.drift_guard_level,
            "signals": [],
        }

        presence_style = proposed_presence.get("presence_style") or proposed_persona.get("presence_style")
        if presence_style and presence_style != persona.presence_style:
            drift_score += 0.35
            evidence["signals"].append("presence_style_changed")

        persona_summary = proposed_persona.get("persona_summary")
        if persona_summary and persona.persona_summary:
            overlap = _text_overlap_ratio(persona.persona_summary, persona_summary)
            if overlap < 0.35:
                drift_score += 0.40
                evidence["signals"].append("persona_summary_low_overlap")
            elif overlap < 0.55:
                drift_score += 0.20
                evidence["signals"].append("persona_summary_partial_overlap")

        tone_descriptors = proposed_persona.get("tone_descriptors_json") or []
        if tone_descriptors and persona.tone_descriptors_json:
            overlap = _list_overlap_ratio(persona.tone_descriptors_json, tone_descriptors)
            if overlap < 0.34:
                drift_score += 0.20
                evidence["signals"].append("tone_shift")

        contract_check = check_contract_violation(
            companion_id,
            {
                **payload,
                "proposed_persona_patch_json": proposed_persona,
                "proposed_presence_patch_json": proposed_presence,
            },
            session=s,
        )
        if contract_check["has_violation"]:
            drift_score += 0.25
            evidence["signals"].append("contract_violation_risk")

        leakage_check = check_private_memory_leakage(
            companion_id,
            payload,
            session=s,
        )
        if leakage_check["has_leakage_risk"]:
            drift_score += 0.25
            evidence["signals"].append("private_memory_leakage_risk")

        drift_score = min(
            1.0,
            max(drift_score, 1.0 - profile_consistency["consistency_score"]),
        )
        risk_level = _risk_level_from_score(drift_score)
        requires_review = (
            drift_score >= 0.55
            or contract_check["has_violation"]
            or leakage_check["has_leakage_risk"]
            or profile_consistency["requires_manual_review"]
        )
        blocks_auto_apply = (
            drift_score >= 0.8
            or contract_check["severity"] == "critical"
            or profile_consistency["blocks_commit"]
        )
        check_status = "blocked" if blocks_auto_apply else ("review_required" if requires_review else "passed")

        check = CompanionPersonaDriftCheck(
            user_id=persona.user_id,
            companion_id=companion_id,
            source_trace_run_id=_to_uuid(payload.get("source_trace_run_id")),
            source_growth_candidate_id=_to_uuid(payload.get("source_growth_candidate_id")),
            source_persona_growth_candidate_id=_to_uuid(payload.get("source_persona_growth_candidate_id")),
            co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
            shared_scene_id=_to_uuid(payload.get("shared_scene_id")),
            drift_risk_level=risk_level,
            check_status=check_status,
            baseline_source=payload.get("baseline_source", "persona_profile"),
            drift_score=drift_score,
            requires_review=requires_review,
            blocks_auto_apply=blocks_auto_apply,
            drift_summary=_drift_summary(risk_level, contract_check, leakage_check),
            evidence_json={
                **evidence,
                "contract_violation": contract_check,
                "private_memory_leakage": leakage_check,
                "profile_consistency": profile_consistency,
            },
            recommendation_json={
                "action": "hold_for_review" if requires_review else "allow_candidate_only",
                "recommended_surface": "hub_queue",
                "allow_auto_apply": False,
            },
            metadata_={"implementation_origin": "presence_and_persona"},
        )
        s.add(check)
        s.commit()
        s.refresh(check)
        return drift_check_to_dict(check)


def check_contract_violation(
    companion_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
    *,
    session: Session | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    owned_session = session is None
    s = session or get_session()
    try:
        contract = _get_contract_profile(s, companion_id)
        boundary = _get_boundary_profile(s, companion_id)
        if contract is None or boundary is None:
            return {"has_violation": False, "severity": "low", "reasons": ["profile_missing"]}

        reasons: list[str] = []
        severity = "low"
        if payload.get("share_private_memory") and contract.shared_memory_policy == "candidate_review":
            reasons.append("private_memory_requires_candidate_review")
            severity = "high"
        if payload.get("cross_companion_private_read") and contract.cross_companion_disclosure_policy == "review_required":
            reasons.append("cross_companion_disclosure_requires_review")
            severity = "high"
        if payload.get("global_memory_read_scope") == "full" and boundary.global_memory_read_scope != "authorized_full":
            reasons.append("global_memory_scope_exceeds_contract")
            severity = "critical"

        proposed_presence = payload.get("proposed_presence_patch_json") or {}
        if proposed_presence.get("presence_style") == "interruptive" and boundary.presence_interrupt_policy != "allow_interruptive":
            reasons.append("presence_interrupt_policy_conflict")
            severity = "medium" if severity == "low" else severity

        return {
            "has_violation": bool(reasons),
            "severity": severity,
            "reasons": reasons,
            "shared_memory_policy": contract.shared_memory_policy,
            "cross_companion_disclosure_policy": contract.cross_companion_disclosure_policy,
        }
    finally:
        if owned_session:
            s.close()


def check_private_memory_leakage(
    companion_id: uuid.UUID,
    payload: dict[str, Any] | None = None,
    *,
    session: Session | None = None,
) -> dict[str, Any]:
    payload = payload or {}
    owned_session = session is None
    s = session or get_session()
    try:
        boundary = _get_boundary_profile(s, companion_id)
        if boundary is None:
            return {"has_leakage_risk": False, "severity": "low", "reasons": ["profile_missing"]}

        reasons: list[str] = []
        severity = "low"
        requested_cross_read = bool(payload.get("cross_companion_private_read"))
        if requested_cross_read and boundary.cross_companion_read_policy != "allow":
            reasons.append("cross_companion_private_read_blocked")
            severity = "critical" if boundary.review_required_cross_companion_share else "high"

        if payload.get("private_to_shared") and boundary.review_required_private_to_shared:
            reasons.append("private_to_shared_requires_review")
            severity = "high" if severity == "low" else severity

        if payload.get("shared_to_private") and boundary.review_required_shared_to_private:
            reasons.append("shared_to_private_requires_review")
            severity = "high" if severity == "low" else severity

        participant_permission_id = _to_uuid(payload.get("participant_memory_permission_id"))
        if participant_permission_id:
            permission = s.get(ParticipantMemoryPermission, participant_permission_id)
            if permission:
                if requested_cross_read and not permission.allow_cross_companion_private_read:
                    reasons.append("participant_permission_denies_cross_read")
                    severity = "critical"
                if payload.get("share_private_memory") and not permission.allow_private_to_shared_sync:
                    reasons.append("participant_permission_denies_private_to_shared_sync")
                    severity = "high" if severity != "critical" else severity

        return {
            "has_leakage_risk": bool(reasons),
            "severity": severity,
            "reasons": reasons,
            "boundary_policy": boundary.cross_companion_read_policy,
        }
    finally:
        if owned_session:
            s.close()


def drift_check_to_dict(check: CompanionPersonaDriftCheck) -> dict[str, Any]:
    return {
        "id": str(check.id),
        "companion_id": str(check.companion_id),
        "drift_risk_level": check.drift_risk_level,
        "check_status": check.check_status,
        "drift_score": check.drift_score,
        "requires_review": check.requires_review,
        "blocks_auto_apply": check.blocks_auto_apply,
        "drift_summary": check.drift_summary,
        "evidence_json": check.evidence_json or {},
        "profile_consistency": (check.evidence_json or {}).get(
            "profile_consistency", {}
        ),
        "recommendation_json": check.recommendation_json or {},
    }


def _get_persona_profile(s: Session, companion_id: uuid.UUID) -> CompanionPersonaProfile | None:
    return s.execute(
        select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)
    ).scalar_one_or_none()


def _get_contract_profile(s: Session, companion_id: uuid.UUID) -> CompanionRelationshipContract | None:
    return s.execute(
        select(CompanionRelationshipContract).where(CompanionRelationshipContract.companion_id == companion_id)
    ).scalar_one_or_none()


def _get_boundary_profile(s: Session, companion_id: uuid.UUID) -> CompanionBoundaryProfile | None:
    return s.execute(
        select(CompanionBoundaryProfile).where(CompanionBoundaryProfile.companion_id == companion_id)
    ).scalar_one_or_none()


def _text_overlap_ratio(left: str, right: str) -> float:
    left_tokens = {token for token in left.lower().split() if token}
    right_tokens = {token for token in right.lower().split() if token}
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _list_overlap_ratio(left: list[Any], right: list[Any]) -> float:
    left_set = {str(item).lower() for item in left if item}
    right_set = {str(item).lower() for item in right if item}
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


def _risk_level_from_score(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.6:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def _drift_summary(
    risk_level: str,
    contract_check: dict[str, Any],
    leakage_check: dict[str, Any],
) -> str:
    parts = [f"persona drift risk is {risk_level}"]
    if contract_check["has_violation"]:
        parts.append("contract boundary needs review")
    if leakage_check["has_leakage_risk"]:
        parts.append("private memory leakage risk detected")
    return "; ".join(parts)


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
