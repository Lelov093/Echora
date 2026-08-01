"""Companion group persona consistency guard service."""

import uuid
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CoPresenceParticipant,
    CoPresenceSession,
    CompanionPersonaProfile,
    GroupPersonaConsistencyCheck,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def check_group_persona_consistency(
    *,
    co_presence_session_id: uuid.UUID | None = None,
    shared_scene_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        participants = _load_participants(s, co_presence_session_id=co_presence_session_id)
        if not participants:
            return None

        companion_ids = [item.participant_companion_id for item in participants if item.participant_companion_id]
        personas = list(
            s.execute(
                select(CompanionPersonaProfile).where(CompanionPersonaProfile.companion_id.in_(companion_ids))
            ).scalars().all()
        )
        by_companion = {item.companion_id: item for item in personas}

        presence_styles = {item.presence_style for item in personas}
        drift_levels = {item.drift_guard_level for item in personas}
        interaction_samples = payload.get("interaction_samples") or []
        conflict_reasons: list[str] = []
        score = 1.0

        if len(presence_styles) > 1:
            score -= 0.20
            conflict_reasons.append("presence_style_mismatch")
        if "strict" in drift_levels and "loose" in drift_levels:
            score -= 0.20
            conflict_reasons.append("drift_guard_mismatch")

        for sample in interaction_samples:
            text = str(sample).lower()
            if "contradict" in text or "compete" in text:
                score -= 0.25
                conflict_reasons.append("interaction_conflict")
            if "override user" in text:
                score -= 0.35
                conflict_reasons.append("user_alignment_conflict")

        score = max(0.0, min(1.0, score))
        requires_review = score < 0.75
        check_status = "blocked" if score < 0.35 else ("review_required" if requires_review else "passed")

        summaries = [
            {
                "companion_id": str(companion_id),
                "presence_style": by_companion[companion_id].presence_style,
                "drift_guard_level": by_companion[companion_id].drift_guard_level,
            }
            for companion_id in companion_ids
            if companion_id in by_companion
        ]

        record = GroupPersonaConsistencyCheck(
            user_id=participants[0].user_id,
            co_presence_session_id=co_presence_session_id,
            shared_scene_id=shared_scene_id,
            source_trace_run_id=_to_uuid(payload.get("source_trace_run_id")),
            consistency_scope=payload.get("consistency_scope", "co_presence_session"),
            check_status=check_status,
            consistency_score=score,
            affected_companion_ids=companion_ids,
            requires_review=requires_review,
            consistency_summary=_build_summary(score, conflict_reasons),
            conflict_json={
                "reasons": conflict_reasons,
                "interaction_samples": interaction_samples,
                "persona_snapshots": summaries,
            },
            recommendation_json={
                "recommended_surface": "hub_queue",
                "next_action": "review_group_alignment" if requires_review else "continue",
            },
            metadata_={"implementation_origin": "presence_and_persona"},
        )
        s.add(record)
        s.commit()
        s.refresh(record)
        return consistency_check_to_dict(record)


def consistency_check_to_dict(check: GroupPersonaConsistencyCheck) -> dict[str, Any]:
    return {
        "id": str(check.id),
        "co_presence_session_id": str(check.co_presence_session_id) if check.co_presence_session_id else None,
        "shared_scene_id": str(check.shared_scene_id) if check.shared_scene_id else None,
        "check_status": check.check_status,
        "consistency_score": check.consistency_score,
        "affected_companion_ids": [str(item) for item in (check.affected_companion_ids or [])],
        "requires_review": check.requires_review,
        "consistency_summary": check.consistency_summary,
        "conflict_json": check.conflict_json or {},
        "recommendation_json": check.recommendation_json or {},
    }


def _load_participants(
    s: Session,
    *,
    co_presence_session_id: uuid.UUID | None,
) -> list[CoPresenceParticipant]:
    if co_presence_session_id is None:
        return []
    return list(
        s.execute(
            select(CoPresenceParticipant)
            .where(
                CoPresenceParticipant.co_presence_session_id
                == co_presence_session_id,
                CoPresenceParticipant.join_status == "active",
            )
            .order_by(CoPresenceParticipant.joined_at.asc())
        ).scalars().all()
    )


def _build_summary(score: float, reasons: list[str]) -> str:
    if not reasons:
        return "group persona consistency passed"
    return f"group persona consistency score={score:.2f}; reasons={', '.join(reasons)}"


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
