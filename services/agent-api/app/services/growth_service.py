"""Growth Candidate & Growth Record service layer."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CompanionPersonaProfile,
    GrowthCandidate,
    GrowthRecord,
    MemoryCandidate,
)
from app.services.evidence_service import score_growth_confidence
from app.services.growth_consistency_service import (
    persist_growth_consistency_check,
    score_growth_consistency,
)

_engine = None


class GrowthMutationError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def _record_growth_feedback(
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    action: str,
    reason: str | None = None,
) -> dict:
    from app.services.feedback_service import create_feedback_event

    return create_feedback_event(
        {
            "user_id": str(user_id),
            "companion_id": str(companion_id),
            "target_type": target_type,
            "target_id": str(target_id),
            "action": action,
            "reason": reason,
            "idempotency_key": f"growth:{target_type}:{target_id}:{action}",
            "sample_provenance": {"source_service": "growth_service"},
            "context_json": {"target_type": target_type, "target_id": str(target_id)},
            "algorithm_key": "growth",
            "effect_already_applied": True,
        }
    )


def list_growth_candidates(companion_id: uuid.UUID | None = None, status: str | None = None,
                           page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(GrowthCandidate)
        if companion_id:
            stmt = stmt.where(GrowthCandidate.companion_id == companion_id)
        if status:
            stmt = stmt.where(GrowthCandidate.status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(GrowthCandidate.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_growth_candidate(candidate_id: uuid.UUID) -> GrowthCandidate | None:
    with get_session() as s:
        return s.get(GrowthCandidate, candidate_id)


def edit_growth_candidate(
    candidate_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    content: str,
    reason: str,
) -> GrowthCandidate | None:
    normalized = content.strip()
    with get_session() as session:
        candidate = session.execute(
            select(GrowthCandidate).where(
                GrowthCandidate.id == candidate_id,
                GrowthCandidate.companion_id == companion_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if candidate is None:
            return None
        if candidate.status not in {"candidate", "accepted"}:
            raise GrowthMutationError(
                "GROWTH_CANDIDATE_NOT_EDITABLE",
                "Only a pending Growth suggestion can be edited.",
                {"status": candidate.status},
            )
        if normalized == candidate.content:
            raise GrowthMutationError(
                "GROWTH_CANDIDATE_UNCHANGED",
                "The edited Growth suggestion is unchanged.",
            )
        metadata = dict(candidate.metadata_ or {})
        edits = list(metadata.get("user_edits") or [])
        edits.append({
            "previous_content": candidate.content,
            "reason": reason.strip(),
            "edited_at": datetime.now(timezone.utc).isoformat(),
        })
        metadata["user_edits"] = edits
        candidate.metadata_ = metadata
        candidate.content = normalized
        candidate.user_feedback_reason = reason.strip()
        candidate.status = "candidate"
        candidate.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(candidate)
        return candidate


def commit_growth_candidate(candidate_id: uuid.UUID, user_id: uuid.UUID,
                            companion_id: uuid.UUID, apply_to_profile: bool = True) -> dict | None:
    """Commit an evidence-gated candidate and optionally apply a safe patch."""
    with get_session() as s:
        cand = s.get(GrowthCandidate, candidate_id)
        if (
            not cand
            or cand.user_id != user_id
            or cand.companion_id != companion_id
        ):
            return None

        if cand.committed_growth_record_id:
            rec = s.get(GrowthRecord, cand.committed_growth_record_id)
            if rec:
                _record_growth_feedback(
                    user_id=cand.user_id,
                    companion_id=cand.companion_id,
                    target_type="growth_candidate",
                    target_id=cand.id,
                    action="accept",
                )
                return {"candidate": _gc_dict(cand), "growth_record": _gr_dict(rec)}

        if cand.status not in ("candidate", "accepted"):
            return None

        evidence_score = float(cand.evidence_score or 0.0)
        patch = _normalize_profile_patch(cand.profile_patch_preview or {})
        consistency = score_growth_consistency(cand.companion_id, patch)
        high_impact = (
            cand.type
            in {
                "communication_style",
                "self_narrative",
                "boundary_update",
            }
            or cand.risk_level in {"high", "critical"}
            or consistency["requires_manual_review"]
        )
        minimum_evidence = 0.80 if high_impact else 0.55
        if evidence_score < minimum_evidence:
            cand.status = "observing"
            cand.user_feedback_reason = (
                f"evidence_score {evidence_score:.3f} below "
                f"{minimum_evidence:.2f} commit threshold"
            )
            s.commit()
            return None
        if high_impact and not (cand.evidence_memory_ids or []):
            cand.user_feedback_reason = (
                "high-impact growth requires companion-scoped evidence memories"
            )
            s.commit()
            return None
        if consistency["blocks_commit"]:
            cand.risk_level = "high"
            cand.requires_user_review = True
            cand.user_feedback_reason = "profile consistency check blocked commit"
            s.commit()
            return None

        trace_run_id = _candidate_trace_run_id(cand)
        persist_growth_consistency_check(
            user_id=cand.user_id,
            companion_id=cand.companion_id,
            growth_candidate_id=cand.id,
            trace_run_id=trace_run_id,
            result=consistency,
        )
        recurrence = (
            (cand.score_json or {})
            .get("trigger", {})
            .get("factors", {})
            .get("topic_recurrence", 0.0)
        )
        confidence = score_growth_confidence(
            evidence_strength=evidence_score,
            user_confirmation_rate=1.0,
            recurrence=recurrence,
            consistency_with_profile=consistency["consistency_score"],
        )
        cand.confidence = confidence["growth_confidence"]
        cand.calibration_json = {
            **(cand.calibration_json or {}),
            "commit_confidence": confidence,
            "consistency": consistency,
        }

        profile = s.execute(
            select(CompanionPersonaProfile).where(
                CompanionPersonaProfile.companion_id == cand.companion_id
            )
        ).scalar_one_or_none()
        profile_before = _profile_snapshot(profile)
        applied_patch = {}
        if apply_to_profile and profile is not None:
            applied_patch = _apply_profile_patch(
                profile,
                patch,
                allow_guarded_fields=(
                    evidence_score >= 0.80
                    and consistency["consistency_score"] >= 0.80
                    and cand.type == "self_narrative"
                ),
            )
            if applied_patch:
                s.flush()
        profile_after = _profile_snapshot(profile)
        actually_applied = bool(applied_patch)

        rec = GrowthRecord(
            user_id=user_id, companion_id=companion_id,
            source_candidate_id=cand.id,
            type=cand.type, content=cand.content, reason=cand.reason,
            evidence_memory_ids=cand.evidence_memory_ids or [],
            evidence_message_ids=cand.evidence_message_ids or [],
            impact_scope=cand.impact_scope or [],
            impact_json={
                "evidence_score": evidence_score,
                "minimum_evidence": minimum_evidence,
                "consistency": consistency,
                "growth_confidence": confidence,
                "requested_apply_to_profile": bool(apply_to_profile),
                "actually_applied": actually_applied,
            },
            applied_to_profile=actually_applied,
            profile_patch_json=applied_patch,
            profile_version_before=profile_before,
            profile_version_after=profile_after,
            status="committed",
        )
        s.add(rec)
        s.flush()
        cand.status = "committed"
        cand.committed_growth_record_id = rec.id
        cand.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(cand)
        s.refresh(rec)
        _record_growth_feedback(
            user_id=cand.user_id,
            companion_id=cand.companion_id,
            target_type="growth_candidate",
            target_id=cand.id,
            action="accept",
        )
        return {"candidate": _gc_dict(cand), "growth_record": _gr_dict(rec)}


def reject_growth_candidate(candidate_id: uuid.UUID, reason: str | None = None) -> GrowthCandidate | None:
    with get_session() as s:
        cand = s.get(GrowthCandidate, candidate_id)
        if not cand:
            return None
        cand.status = "rejected"
        cand.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(cand)
        _record_growth_feedback(
            user_id=cand.user_id,
            companion_id=cand.companion_id,
            target_type="growth_candidate",
            target_id=cand.id,
            action="reject",
            reason=reason,
        )
        return cand


def list_growth_records(companion_id: uuid.UUID | None = None, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(GrowthRecord)
        if companion_id:
            stmt = stmt.where(GrowthRecord.companion_id == companion_id)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(GrowthRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_growth_record(record_id: uuid.UUID) -> GrowthRecord | None:
    with get_session() as s:
        return s.get(GrowthRecord, record_id)


def revert_growth_record(record_id: uuid.UUID, reason: str | None = None) -> GrowthRecord | None:
    with get_session() as s:
        r = s.get(GrowthRecord, record_id)
        if not r:
            return None
        if r.status == "reverted":
            return r
        restored_fields = {}
        profile = s.execute(
            select(CompanionPersonaProfile).where(
                CompanionPersonaProfile.companion_id == r.companion_id
            )
        ).scalar_one_or_none()
        if r.applied_to_profile and profile is not None:
            restored_fields = _restore_profile_snapshot(
                profile,
                r.profile_version_before or {},
            )
            if restored_fields:
                s.flush()

        correction_candidate = _create_revert_correction_candidate(
            s,
            r,
            reason,
        )
        source_candidate = (
            s.get(GrowthCandidate, r.source_candidate_id)
            if r.source_candidate_id
            else None
        )
        if source_candidate is not None:
            source_candidate.confidence = max(
                0.0, float(source_candidate.confidence or 0.0) - 0.20
            )
            source_candidate.negative_feedback_count = int(
                source_candidate.negative_feedback_count or 0
            ) + 1
            source_candidate.feedback_score = max(
                -1.0, float(source_candidate.feedback_score or 0.0) - 0.20
            )
            source_candidate.user_feedback_reason = reason

        r.status = "reverted"
        r.applied_to_profile = False
        r.reverted_at = datetime.now(timezone.utc)
        r.revert_reason = reason
        r.revert_impact_json = {
            "restored_profile_fields": restored_fields,
            "restored_profile_version": _profile_snapshot(profile),
            "correction_memory_candidate_id": (
                str(correction_candidate.id) if correction_candidate else None
            ),
            "source_candidate_confidence_reduced": source_candidate is not None,
        }
        r.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(r)
        _record_growth_feedback(
            user_id=r.user_id,
            companion_id=r.companion_id,
            target_type="growth_record",
            target_id=r.id,
            action="revert",
            reason=reason,
        )
        return r


def _gc_dict(c: GrowthCandidate) -> dict:
    return {
        "id": str(c.id), "type": c.type, "content": c.content,
        "conversation_id": str(c.conversation_id) if c.conversation_id else None,
        "confidence": c.confidence, "risk_level": c.risk_level,
        "evidence_score": c.evidence_score,
        "requires_user_review": c.requires_user_review,
        "status": c.status,
        "profile_patch_preview": c.profile_patch_preview or {},
        "score_json": c.score_json or {},
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _gr_dict(r: GrowthRecord) -> dict:
    return {
        "id": str(r.id), "type": r.type, "content": r.content,
        "status": r.status, "applied_to_profile": r.applied_to_profile,
        "profile_patch_json": r.profile_patch_json or {},
        "profile_version_before": r.profile_version_before or {},
        "profile_version_after": r.profile_version_after or {},
        "revert_impact_json": r.revert_impact_json or {},
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _normalize_profile_patch(patch: dict) -> dict[str, dict]:
    if any(key in patch for key in ("persona", "relationship", "boundary")):
        return {
            "persona": dict(patch.get("persona") or {}),
            "relationship": dict(patch.get("relationship") or {}),
            "boundary": dict(patch.get("boundary") or {}),
        }
    return {"persona": dict(patch), "relationship": {}, "boundary": {}}


def _profile_snapshot(profile: CompanionPersonaProfile | None) -> dict:
    if profile is None:
        return {}
    return {
        "profile_id": str(profile.id),
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        "persona_summary": profile.persona_summary,
        "communication_style_summary": profile.communication_style_summary,
        "tone_descriptors_json": list(profile.tone_descriptors_json or []),
        "core_values_json": list(profile.core_values_json or []),
        "response_preferences_json": dict(profile.response_preferences_json or {}),
        "persona_lock_level": profile.persona_lock_level,
        "drift_guard_level": profile.drift_guard_level,
        "presence_style": profile.presence_style,
    }


def _apply_profile_patch(
    profile: CompanionPersonaProfile,
    patch: dict[str, dict],
    *,
    allow_guarded_fields: bool,
) -> dict:
    persona_patch = patch.get("persona") or {}
    allowed = {
        "communication_style_summary",
        "tone_descriptors_json",
        "response_preferences_json",
        "presence_style",
    }
    if allow_guarded_fields:
        allowed.add("persona_summary")
    applied = {}
    for key, value in persona_patch.items():
        if key not in allowed or not hasattr(profile, key):
            continue
        if getattr(profile, key) != value:
            setattr(profile, key, value)
            applied[key] = value
    return applied


def _restore_profile_snapshot(
    profile: CompanionPersonaProfile,
    snapshot: dict,
) -> dict:
    restored = {}
    for key in (
        "persona_summary",
        "communication_style_summary",
        "tone_descriptors_json",
        "core_values_json",
        "response_preferences_json",
        "persona_lock_level",
        "drift_guard_level",
        "presence_style",
    ):
        if key in snapshot and getattr(profile, key) != snapshot[key]:
            setattr(profile, key, snapshot[key])
            restored[key] = snapshot[key]
    return restored


def _create_revert_correction_candidate(
    session: Session,
    record: GrowthRecord,
    reason: str | None,
) -> MemoryCandidate:
    content = (
        f"Correction after reverting growth '{record.content[:180]}': "
        f"{(reason or 'The applied growth did not match the user intent.')[:240]}"
    )
    candidate = MemoryCandidate(
        user_id=record.user_id,
        companion_id=record.companion_id,
        proposed_owner_companion_id=record.companion_id,
        content=content,
        suggested_summary=content[:200],
        suggested_type="correction",
        importance=0.9,
        confidence=0.9,
        correction_value=1.0,
        score=0.9,
        reason="Growth revert generated a review-gated correction memory candidate",
        needs_user_confirmation=True,
        requires_companion_memory_review=True,
        status="pending",
        score_json={
            "source_growth_record_id": str(record.id),
            "algorithm_version": "core-growth-revert-v1",
        },
        calibration_json={
            "source": "growth_revert",
            "review_gated": True,
        },
    )
    session.add(candidate)
    session.flush()
    return candidate


def _candidate_trace_run_id(candidate: GrowthCandidate) -> uuid.UUID | None:
    trace_id = (candidate.score_json or {}).get("trace_run_id")
    return uuid.UUID(str(trace_id)) if trace_id else None
