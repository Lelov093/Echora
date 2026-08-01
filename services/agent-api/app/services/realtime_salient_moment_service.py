"""Realtime compatibility realtime salient moment service."""

import uuid
from typing import Any

from app.db.models import (
    CompanionPrivateSalientMoment,
    RealtimeMemoryBuffer,
    RealtimeMemoryBufferItem,
    SalientMoment,
    SharedSalientMoment,
)
from app.services.realtime_copresence_service import get_session


def detect_salient_moment(buffer_item_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        item = s.get(RealtimeMemoryBufferItem, buffer_item_id)
        if item is None or not item.can_generate_salient_moment:
            return None
        buffer = s.get(RealtimeMemoryBuffer, item.buffer_id)
        if buffer is None:
            return None
        summary = payload.get("moment_summary") or item.content_summary or "Realtime salient moment"
        score = _score(summary, payload)
        scope = payload.get("moment_scope") or ("companion_private" if buffer.buffer_scope == "companion_private" else "shared_episodic")
        if scope not in {"companion_private", "shared_scene", "shared_episodic"}:
            scope = "shared_episodic"
        moment = SalientMoment(
            user_id=item.user_id,
            realtime_session_id=item.realtime_session_id,
            buffer_id=buffer.id,
            buffer_item_id=item.id,
            moment_scope=scope,
            moment_status="candidate_pending_review",
            moment_title=payload.get("moment_title") or summary[:80],
            moment_summary=summary,
            salience_score=score,
            review_required=True,
            auto_write_disabled=True,
            evidence_json={
                "source_buffer_item_id": str(item.id),
                "source_type": item.source_type,
                "heuristic": "keyword_and_length",
            },
            policy_snapshot_json={
                "auto_write_private_memory": False,
                "auto_write_shared_memory": False,
                "shared_episodic_memory_requires_review": True,
            },
            metadata_={"implementation_origin": "realtime_memory"},
        )
        s.add(moment)
        s.flush()
        if scope == "companion_private" and buffer.owner_companion_id:
            s.add(
                CompanionPrivateSalientMoment(
                    user_id=item.user_id,
                    salient_moment_id=moment.id,
                    companion_id=buffer.owner_companion_id,
                    private_memory_sync_policy="review_required",
                    auto_write_private_memory=False,
                    review_required=True,
                    metadata_={"implementation_origin": "realtime_memory"},
                )
            )
        else:
            s.add(
                SharedSalientMoment(
                    user_id=item.user_id,
                    salient_moment_id=moment.id,
                    shared_scene_id=buffer.shared_scene_id,
                    shared_memory_sync_policy="review_required",
                    auto_write_shared_memory=False,
                    review_required=True,
                    metadata_={"implementation_origin": "realtime_memory"},
                )
            )
        s.commit()
        s.refresh(moment)
        return moment_to_dict(moment)


def get_salient_moment(moment_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        moment = s.get(SalientMoment, moment_id)
        return moment_to_dict(moment) if moment else None


def moment_to_dict(moment: SalientMoment) -> dict[str, Any]:
    return {
        "id": str(moment.id),
        "user_id": str(moment.user_id),
        "realtime_session_id": str(moment.realtime_session_id) if moment.realtime_session_id else None,
        "buffer_id": str(moment.buffer_id) if moment.buffer_id else None,
        "buffer_item_id": str(moment.buffer_item_id) if moment.buffer_item_id else None,
        "moment_scope": moment.moment_scope,
        "moment_status": moment.moment_status,
        "moment_title": moment.moment_title,
        "moment_summary": moment.moment_summary,
        "salience_score": moment.salience_score,
        "review_required": moment.review_required,
        "auto_write_disabled": moment.auto_write_disabled,
        "evidence_json": moment.evidence_json or {},
        "policy_snapshot_json": moment.policy_snapshot_json or {},
    }


def _score(summary: str, payload: dict[str, Any]) -> float:
    if "salience_score" in payload:
        return max(0.0, min(float(payload["salience_score"]), 1.0))
    important_terms = ["important", "promise", "decision", "remember", "milestone", "shared"]
    score = 0.55 + min(len(summary) / 1000, 0.2)
    if any(term in summary.lower() for term in important_terms):
        score += 0.2
    return max(0.0, min(score, 1.0))
