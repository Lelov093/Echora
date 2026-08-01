"""Companion companion persona growth service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CompanionPersonaGrowthCandidate,
    CompanionPersonaGrowthEvent,
    CompanionPersonaProfile,
    GrowthCandidate,
    SharedExperienceRecord,
)
from app.services.evidence_service import score_growth_evidence
from app.services.growth_consistency_service import score_growth_consistency
from app.services import growth_control_service

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def validate_growth_evidence(companion_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        persona = s.execute(
            select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)
        ).scalar_one_or_none()
        if persona is None:
            return None

        evidence_memory_ids: list[uuid.UUID] = []
        additional_evidence_count = 0
        additional_confidences: list[float] = []
        reasons: list[str] = []
        if payload.get("source_growth_candidate_id"):
            growth_candidate = s.get(GrowthCandidate, _to_uuid(payload["source_growth_candidate_id"]))
            if growth_candidate:
                evidence_memory_ids.extend(growth_candidate.evidence_memory_ids or [])
                reasons.append("growth_candidate")
        if payload.get("shared_experience_record_id"):
            experience = s.get(SharedExperienceRecord, _to_uuid(payload["shared_experience_record_id"]))
            if experience:
                additional_evidence_count += 1
                additional_confidences.append(
                    float((experience.metadata_ or {}).get("confidence", 0.75))
                )
                reasons.append("shared_experience")
        if payload.get("evidence_items"):
            additional_evidence_count += len(payload["evidence_items"])
            additional_confidences.extend(
                [0.70 for _ in payload["evidence_items"]]
            )
            reasons.append("explicit_evidence_items")

        recurrence = payload.get("recurrence")
        if recurrence is None:
            recurrence = min(1.0, additional_evidence_count / 3.0)
        evidence = score_growth_evidence(
            companion_id,
            evidence_memory_ids,
            correction_strength=float(payload.get("correction_strength", 0.0)),
            recurrence=float(recurrence),
            additional_evidence_count=additional_evidence_count,
            additional_confidences=additional_confidences,
        )
        high_impact = payload.get("impact_level") in {"high", "critical"}
        review_reason = "high impact growth remains candidate-only" if high_impact else None
        return {
            "companion_id": str(companion_id),
            "evidence_score": evidence["evidence_score"],
            "confidence": evidence["factors"]["confidence_avg"],
            "evidence_sources": (
                evidence["memory_count"] + evidence["additional_evidence_count"]
            ),
            "reasons": reasons,
            "is_sufficient": evidence["is_sufficient"],
            "review_reason": review_reason,
            "impact_level": payload.get("impact_level", "medium"),
            "evidence": evidence,
        }


def create_persona_growth_candidate(companion_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    if not growth_control_service.suggestions_allowed(
        companion_id,
        str(payload.get("growth_dimension") or "self_narrative"),
    ):
        return None
    evidence = validate_growth_evidence(companion_id, payload)
    if evidence is None or not evidence["is_sufficient"]:
        return None

    with get_session() as s:
        persona = s.execute(
            select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)
        ).scalar_one_or_none()
        if persona is None:
            return None

        consistency = score_growth_consistency(
            companion_id,
            {
                "persona": {
                    **(payload.get("proposed_persona_patch_json") or {}),
                    **(payload.get("proposed_presence_patch_json") or {}),
                },
                "relationship": payload.get("proposed_relationship_patch_json")
                or {},
                "boundary": payload.get("proposed_boundary_patch_json") or {},
            },
        )
        impact_level = payload.get("impact_level", "medium")
        if consistency["risk_level"] in {"high", "critical"}:
            impact_level = "high"
        candidate_status = "pending_review"
        requires_user_review = (
            True
            if impact_level in {"high", "critical"}
            or consistency["requires_manual_review"]
            else bool(payload.get("requires_user_review", True))
        )
        candidate = CompanionPersonaGrowthCandidate(
            user_id=persona.user_id,
            companion_id=companion_id,
            source_growth_candidate_id=_to_uuid(payload.get("source_growth_candidate_id")),
            shared_experience_record_id=_to_uuid(payload.get("shared_experience_record_id")),
            co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
            source_trace_run_id=_to_uuid(payload.get("source_trace_run_id")),
            growth_dimension=payload.get("growth_dimension", "persona_summary"),
            impact_level=impact_level,
            candidate_status=candidate_status,
            growth_summary=payload.get("growth_summary", ""),
            evidence_summary=payload.get("evidence_summary"),
            proposed_persona_patch_json=payload.get("proposed_persona_patch_json") or {},
            proposed_presence_patch_json=payload.get("proposed_presence_patch_json") or {},
            confidence=evidence["confidence"],
            evidence_score=evidence["evidence_score"],
            requires_user_review=requires_user_review,
            review_reason=(
                evidence["review_reason"]
                or (
                    "profile consistency requires manual review"
                    if consistency["requires_manual_review"]
                    else None
                )
                or payload.get("review_reason")
            ),
            metadata_={
                "phase": "core_algorithm_r5",
                "evidence_reasons": evidence["reasons"],
                "consistency": consistency,
            },
        )
        s.add(candidate)
        s.flush()

        event = CompanionPersonaGrowthEvent(
            user_id=persona.user_id,
            companion_id=companion_id,
            source_persona_growth_candidate_id=candidate.id,
            source_growth_record_id=None,
            source_trace_run_id=_to_uuid(payload.get("source_trace_run_id")),
            co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
            event_type="candidate_committed",
            impact_level=impact_level,
            event_summary=payload.get("event_summary") or f"Growth candidate created for {payload.get('growth_dimension', 'persona_summary')}",
            applied_patch_json={
                "persona": payload.get("proposed_persona_patch_json") or {},
                "presence": payload.get("proposed_presence_patch_json") or {},
            },
            evidence_json={**evidence, "consistency": consistency},
            review_required=True,
            occurred_at=datetime.now(timezone.utc),
            metadata_={"phase": "core_algorithm_r5", "candidate_only": True},
        )
        s.add(event)
        s.commit()
        s.refresh(candidate)
        s.refresh(event)
        return {
            "candidate": growth_candidate_to_dict(candidate),
            "event": growth_event_to_dict(event),
            "evidence": evidence,
            "consistency": consistency,
        }


def growth_candidate_to_dict(candidate: CompanionPersonaGrowthCandidate) -> dict[str, Any]:
    return {
        "id": str(candidate.id),
        "companion_id": str(candidate.companion_id),
        "growth_dimension": candidate.growth_dimension,
        "impact_level": candidate.impact_level,
        "candidate_status": candidate.candidate_status,
        "growth_summary": candidate.growth_summary,
        "evidence_score": candidate.evidence_score,
        "confidence": candidate.confidence,
        "requires_user_review": candidate.requires_user_review,
        "review_reason": candidate.review_reason,
        "proposed_persona_patch_json": candidate.proposed_persona_patch_json or {},
        "proposed_presence_patch_json": candidate.proposed_presence_patch_json or {},
    }


def growth_event_to_dict(event: CompanionPersonaGrowthEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "companion_id": str(event.companion_id),
        "event_type": event.event_type,
        "impact_level": event.impact_level,
        "event_summary": event.event_summary,
        "review_required": event.review_required,
        "applied_patch_json": event.applied_patch_json or {},
        "evidence_json": event.evidence_json or {},
    }


def decide_persona_growth_candidate(companion_id: uuid.UUID, candidate_id: uuid.UUID, decision: str) -> dict[str, Any] | None:
    """Apply or reject one reviewed persona-growth candidate inside its Companion scope."""
    if decision not in {"approved", "rejected"}:
        return None
    with get_session() as s:
        candidate = s.get(CompanionPersonaGrowthCandidate, candidate_id)
        if candidate is None or candidate.companion_id != companion_id or candidate.candidate_status != "pending_review":
            return None
        candidate.candidate_status = "rejected" if decision == "rejected" else "committed"
        applied_patch: dict[str, Any] = {}
        if decision == "approved":
            persona = s.execute(select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id == companion_id)).scalar_one_or_none()
            if persona is None:
                return None
            for field in ("persona_summary", "communication_style_summary", "tone_descriptors_json", "core_values_json", "response_preferences_json", "persona_lock_level", "drift_guard_level", "presence_style"):
                value = (candidate.proposed_persona_patch_json or {}).get(field, (candidate.proposed_presence_patch_json or {}).get(field))
                if value is not None:
                    setattr(persona, field, value)
                    applied_patch[field] = value
            persona.updated_at = datetime.now(timezone.utc)
            s.add(CompanionPersonaGrowthEvent(
                user_id=candidate.user_id,
                companion_id=companion_id,
                source_persona_growth_candidate_id=candidate.id,
                source_growth_record_id=None,
                source_trace_run_id=candidate.source_trace_run_id,
                co_presence_session_id=candidate.co_presence_session_id,
                event_type="review_approved",
                impact_level=candidate.impact_level,
                event_summary=candidate.growth_summary,
                applied_patch_json=applied_patch,
                evidence_json={"review_reason": candidate.review_reason, "evidence_score": candidate.evidence_score},
                review_required=True,
                occurred_at=datetime.now(timezone.utc),
                metadata_={"surface": "review_inbox"},
            ))
        s.commit()
        s.refresh(candidate)
        return {"candidate": growth_candidate_to_dict(candidate), "applied_patch": applied_patch}


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
