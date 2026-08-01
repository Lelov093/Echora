"""Companion profile consistency scoring for growth decisions."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select

from app.db.models import (
    CompanionBoundaryProfile,
    CompanionPersonaProfile,
    CompanionRelationshipContract,
    GrowthConsistencyCheck,
)
from app.services.persistence_helpers import (
    create_row,
    default_ids,
    get_session,
    list_rows,
)

_TOKEN_RE = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]", re.IGNORECASE)
_CORE_KEYS = {
    "identity_summary",
    "core_traits_json",
    "core_values_json",
    "persona_lock_level",
    "drift_guard_level",
}
_BOUNDARY_KEYS = {
    "boundary_json",
    "private_memory_default",
    "shared_memory_default",
    "global_memory_read_scope",
    "cross_companion_read_policy",
    "review_required_private_to_shared",
    "review_required_shared_to_private",
    "review_required_cross_companion_share",
    "presence_interrupt_policy",
}
_RELATIONSHIP_KEYS = {
    "relationship_role",
    "contract_status",
    "contract_summary",
    "collaboration_style_summary",
    "support_scope_json",
    "shared_memory_policy",
    "cross_companion_disclosure_policy",
    "contract_json",
}


def score_growth_consistency(
    companion_id: uuid.UUID,
    profile_patch_preview: dict[str, Any] | None,
) -> dict[str, Any]:
    patch = _normalize_patch(profile_patch_preview or {})
    with get_session() as session:
        persona = session.execute(
            select(CompanionPersonaProfile).where(
                CompanionPersonaProfile.companion_id == companion_id
            )
        ).scalar_one_or_none()
        relationship = session.execute(
            select(CompanionRelationshipContract).where(
                CompanionRelationshipContract.companion_id == companion_id
            )
        ).scalar_one_or_none()
        boundary = session.execute(
            select(CompanionBoundaryProfile).where(
                CompanionBoundaryProfile.companion_id == companion_id
            )
        ).scalar_one_or_none()

    conflicts: list[str] = []
    core_score = 1.0
    persona_score = 1.0
    relationship_score = 1.0
    boundary_score = 1.0

    persona_patch = patch["persona"]
    relationship_patch = patch["relationship"]
    boundary_patch = patch["boundary"]

    core_changes = sorted(set(persona_patch) & _CORE_KEYS)
    if core_changes:
        core_score = 0.20
        conflicts.append("core_persona_change_requires_manual_review")

    if persona and persona_patch.get("persona_summary"):
        overlap = _text_overlap(
            persona.persona_summary or "",
            str(persona_patch["persona_summary"]),
        )
        persona_score = min(persona_score, overlap)
        if overlap < 0.55:
            conflicts.append("persona_summary_conflict")
    if persona and persona_patch.get("tone_descriptors_json"):
        tone_overlap = _list_overlap(
            persona.tone_descriptors_json or [],
            persona_patch["tone_descriptors_json"],
        )
        persona_score = min(persona_score, tone_overlap)
        if tone_overlap < 0.50:
            conflicts.append("persona_tone_conflict")

    if relationship_patch:
        relationship_score = 0.45
        conflicts.append("relationship_change_requires_manual_review")
        if relationship and any(
            key in relationship_patch
            and relationship_patch[key] != getattr(relationship, key, None)
            for key in _RELATIONSHIP_KEYS
        ):
            relationship_score = 0.25

    if boundary_patch:
        boundary_score = 0.20
        conflicts.append("boundary_change_requires_manual_review")
        if boundary and any(
            key in boundary_patch
            and boundary_patch[key] != getattr(boundary, key, None)
            for key in _BOUNDARY_KEYS
        ):
            boundary_score = 0.10

    consistency_score = (
        0.30 * core_score
        + 0.30 * persona_score
        + 0.20 * relationship_score
        + 0.20 * boundary_score
    )
    if consistency_score < 0.55 or boundary_patch or core_changes:
        risk_level = "high"
        status = "blocked" if consistency_score < 0.35 else "needs_review"
    elif consistency_score < 0.80 or relationship_patch:
        risk_level = "medium"
        status = "needs_review"
    else:
        risk_level = "low"
        status = "passed"
    return {
        "consistency_score": round(consistency_score, 6),
        "risk_level": risk_level,
        "status": status,
        "requires_manual_review": status != "passed",
        "blocks_commit": status == "blocked",
        "dimension_scores": {
            "profile_core": round(core_score, 6),
            "persona": round(persona_score, 6),
            "relationship": round(relationship_score, 6),
            "boundary": round(boundary_score, 6),
        },
        "conflicts": conflicts,
        "profile_patch_preview": patch,
        "algorithm_version": "core-growth-consistency-v1",
    }


def persist_growth_consistency_check(
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    growth_candidate_id: uuid.UUID | None,
    trace_run_id: uuid.UUID | None,
    result: dict[str, Any],
) -> dict:
    return create_growth_consistency_check(
        {
            "user_id": user_id,
            "companion_id": companion_id,
            "growth_candidate_id": growth_candidate_id,
            "trace_run_id": trace_run_id,
            "consistency_score": result["consistency_score"],
            "risk_level": result["risk_level"],
            "status": result["status"],
            "conflict_json": {
                "conflicts": result["conflicts"],
                "dimension_scores": result["dimension_scores"],
            },
            "profile_patch_preview_json": result["profile_patch_preview"],
            "recommendation": (
                "manual_review"
                if result["requires_manual_review"]
                else "commit_allowed"
            ),
            "metadata": {
                "algorithm_version": result["algorithm_version"],
                "blocks_commit": result["blocks_commit"],
            },
        }
    )


def create_growth_consistency_check(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        data.setdefault("status", "needs_review")
        return create_row(session, GrowthConsistencyCheck, data)


def list_growth_consistency_checks(
    page: int = 1,
    page_size: int = 20,
    **filters,
) -> dict:
    with get_session() as session:
        return list_rows(session, GrowthConsistencyCheck, filters, page, page_size)


def _normalize_patch(patch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if any(key in patch for key in ("persona", "relationship", "boundary")):
        return {
            "persona": dict(patch.get("persona") or {}),
            "relationship": dict(patch.get("relationship") or {}),
            "boundary": dict(patch.get("boundary") or {}),
        }
    persona = {
        key: value
        for key, value in patch.items()
        if key not in _RELATIONSHIP_KEYS and key not in _BOUNDARY_KEYS
    }
    return {
        "persona": persona,
        "relationship": {
            key: value for key, value in patch.items() if key in _RELATIONSHIP_KEYS
        },
        "boundary": {
            key: value for key, value in patch.items() if key in _BOUNDARY_KEYS
        },
    }


def _text_overlap(left: str, right: str) -> float:
    left_tokens = set(_TOKEN_RE.findall(left.lower()))
    right_tokens = set(_TOKEN_RE.findall(right.lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _list_overlap(left: list[Any], right: list[Any]) -> float:
    left_values = {str(value).lower() for value in left if value}
    right_values = {str(value).lower() for value in right if value}
    if not left_values or not right_values:
        return 0.0
    return len(left_values & right_values) / len(left_values | right_values)
