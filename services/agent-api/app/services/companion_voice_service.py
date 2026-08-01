"""Realtime compatibility companion voice service with simulated STT/TTS adapters."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.db.models import (
    Companion,
    CompanionVoiceProfile,
    CompanionVoiceSession,
    RealtimeCoPresenceParticipant,
    RealtimeCoPresenceSession,
    SttEvent,
    TtsEvent,
    TurnTakingEvent,
    User,
    VoiceInterruptionEvent,
    VoicePersonaGuardRun,
    VoiceProviderConfig,
    VoiceTurn,
)
from app.services import stt_provider_service, tts_provider_service, turn_taking_service
from app.services.realtime_copresence_service import get_session


def list_voice_sessions(
    *,
    user_id: uuid.UUID | None = None,
    realtime_session_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(CompanionVoiceSession)
        if user_id:
            stmt = stmt.where(CompanionVoiceSession.user_id == user_id)
        if realtime_session_id:
            stmt = stmt.where(CompanionVoiceSession.realtime_session_id == realtime_session_id)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(CompanionVoiceSession.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            ).scalars().all()
        )
        return {"items": [_voice_session_to_dict(item) for item in items], "total": total}


def create_voice_session(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        user = s.get(User, user_id)
        realtime_session = s.get(RealtimeCoPresenceSession, _to_uuid(payload.get("realtime_session_id")))
        speaker_companion = s.get(Companion, _to_uuid(payload.get("speaker_companion_id")))
        if user is None or realtime_session is None or speaker_companion is None:
            return None
        if realtime_session.user_id != user_id or speaker_companion.user_id != user_id:
            return None

        speaker_participant_id = _resolve_speaker_participant_id(s, realtime_session.id, speaker_companion.id, payload)
        combined_provider = _ensure_simulation_provider(s, user_id, speaker_companion.id, "combined")
        profile = _ensure_voice_profile(s, user_id, speaker_companion.id, combined_provider.id, payload)
        now = _now()
        voice_session = CompanionVoiceSession(
            user_id=user_id,
            realtime_session_id=realtime_session.id,
            co_presence_session_id=realtime_session.co_presence_session_id,
            speaker_companion_id=speaker_companion.id,
            speaker_realtime_participant_id=speaker_participant_id,
            voice_profile_id=profile.id,
            stt_provider_config_id=combined_provider.id,
            tts_provider_config_id=combined_provider.id,
            session_status="active",
            transcript_retention_policy="ephemeral",
            memory_write_policy="candidate_review",
            allow_multi_speaker=False,
            permission_snapshot_json=payload.get("permission_snapshot_json") or realtime_session.permission_snapshot_json or {},
            voice_runtime_json={
                "provider_mode": "simulation",
                "real_audio_enabled": False,
                "media_server_enabled": False,
                **(payload.get("voice_runtime_json") or {}),
            },
            started_at=now,
            metadata_={"source": "voice_simulation"},
        )
        s.add(voice_session)
        s.flush()
        first_turn = _create_voice_turn(s, voice_session, "listening")
        _record_turn_taking_event(s, voice_session, first_turn, {"event_type": "listening_started"})
        s.commit()
        s.refresh(voice_session)
        return get_voice_session_bundle(voice_session.id)


def get_voice_session_bundle(voice_session_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        voice_session = s.get(CompanionVoiceSession, voice_session_id)
        if voice_session is None:
            return None
        turns = list(
            s.execute(
                select(VoiceTurn)
                .where(VoiceTurn.voice_session_id == voice_session.id)
                .order_by(VoiceTurn.turn_index.asc(), VoiceTurn.created_at.asc())
            ).scalars().all()
        )
        stt_events = list(
            s.execute(
                select(SttEvent)
                .where(SttEvent.voice_session_id == voice_session.id)
                .order_by(SttEvent.occurred_at.asc(), SttEvent.created_at.asc())
            ).scalars().all()
        )
        tts_events = list(
            s.execute(
                select(TtsEvent)
                .where(TtsEvent.voice_session_id == voice_session.id)
                .order_by(TtsEvent.occurred_at.asc(), TtsEvent.created_at.asc())
            ).scalars().all()
        )
        turn_events = list(
            s.execute(
                select(TurnTakingEvent)
                .where(TurnTakingEvent.voice_session_id == voice_session.id)
                .order_by(TurnTakingEvent.occurred_at.asc(), TurnTakingEvent.created_at.asc())
            ).scalars().all()
        )
        interruptions = list(
            s.execute(
                select(VoiceInterruptionEvent)
                .where(VoiceInterruptionEvent.voice_session_id == voice_session.id)
                .order_by(VoiceInterruptionEvent.occurred_at.asc(), VoiceInterruptionEvent.created_at.asc())
            ).scalars().all()
        )
        guards = list(
            s.execute(
                select(VoicePersonaGuardRun)
                .where(VoicePersonaGuardRun.voice_session_id == voice_session.id)
                .order_by(VoicePersonaGuardRun.created_at.asc())
            ).scalars().all()
        )
        return {
            **_voice_session_to_dict(voice_session),
            "turns": [_voice_turn_to_dict(item) for item in turns],
            "stt_events": [_stt_event_to_dict(item) for item in stt_events],
            "tts_events": [_tts_event_to_dict(item) for item in tts_events],
            "turn_taking_events": [_turn_taking_event_to_dict(item) for item in turn_events],
            "interruption_events": [_interruption_to_dict(item) for item in interruptions],
            "persona_guard_runs": [_guard_to_dict(item) for item in guards],
        }


def record_stt_partial(voice_session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _record_stt_event(voice_session_id, payload, final=False)


def record_stt_final(voice_session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _record_stt_event(voice_session_id, payload, final=True)


def record_tts_event(voice_session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    event_type = payload.get("event_type") or "queued"
    if event_type not in {"queued", "started", "delta", "completed", "error"}:
        event_type = "queued"
    with get_session() as s:
        voice_session = s.get(CompanionVoiceSession, voice_session_id)
        if voice_session is None:
            return None
        turn = _get_or_create_current_turn(s, voice_session, "speaking")
        provider = tts_provider_service.get_tts_provider("simulation")
        result = provider.synthesize(payload, event_type=event_type)
        event = TtsEvent(
            user_id=voice_session.user_id,
            voice_session_id=voice_session.id,
            voice_turn_id=turn.id,
            provider_config_id=voice_session.tts_provider_config_id,
            event_type=result["event_type"],
            event_status="recorded",
            text_preview=result["text_preview"],
            audio_artifact_ref=result["audio_artifact_ref"],
            audio_retention_policy="ephemeral",
            raw_payload_json=result["raw_payload_json"],
            occurred_at=_now(),
            metadata_={"source": "voice_simulation"},
        )
        s.add(event)
        turn.companion_response_preview = result["text_preview"]
        turn.turn_status = "completed" if event_type == "completed" else "speaking"
        if event_type == "completed":
            turn.completed_at = _now()
        s.commit()
        s.refresh(event)
        return _tts_event_to_dict(event)


def decide_turn_taking_state(voice_session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        voice_session = s.get(CompanionVoiceSession, voice_session_id)
        if voice_session is None:
            return None
        turn = _get_or_create_current_turn(s, voice_session, "listening")
        event = _record_turn_taking_event(s, voice_session, turn, payload)
        s.commit()
        s.refresh(event)
        return _turn_taking_event_to_dict(event)


def record_interruption(voice_session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        voice_session = s.get(CompanionVoiceSession, voice_session_id)
        if voice_session is None:
            return None
        turn = _get_or_create_current_turn(s, voice_session, "interrupted")
        interruption_type = payload.get("interruption_type") or "user_interrupt"
        if interruption_type not in {"user_interrupt", "hard_stop", "companion_interrupt", "timeout"}:
            interruption_type = "user_interrupt"
        event = VoiceInterruptionEvent(
            user_id=voice_session.user_id,
            voice_session_id=voice_session.id,
            voice_turn_id=turn.id,
            source_participant_id=_to_uuid(payload.get("source_participant_id")),
            target_participant_id=_to_uuid(payload.get("target_participant_id")),
            interruption_type=interruption_type,
            interruption_status="recorded",
            stops_tts=True,
            requires_trace=True,
            interruption_payload_json={"reason": payload.get("reason"), "simulation": True},
            occurred_at=_now(),
            metadata_={"source": "voice_simulation"},
        )
        s.add(event)
        turn.turn_status = "interrupted"
        if interruption_type == "hard_stop":
            voice_session.session_status = "ended"
            voice_session.ended_at = _now()
        s.commit()
        s.refresh(event)
        return _interruption_to_dict(event)


def run_voice_persona_guard(voice_session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        voice_session = s.get(CompanionVoiceSession, voice_session_id)
        if voice_session is None:
            return None
        turn = _get_or_create_current_turn(s, voice_session, "processing")
        text = str(payload.get("transcript_excerpt") or turn.user_utterance_preview or "").lower()
        risk = "medium" if any(term in text for term in ["ignore persona", "break character", "system prompt"]) else "low"
        requires_review = risk != "low"
        guard = VoicePersonaGuardRun(
            user_id=voice_session.user_id,
            voice_session_id=voice_session.id,
            voice_turn_id=turn.id,
            speaker_companion_id=voice_session.speaker_companion_id,
            guard_status="review_required" if requires_review else "passed",
            drift_risk_level=risk,
            voice_style_consistency_score=0.72 if requires_review else 0.96,
            requires_review=requires_review,
            blocks_response=False,
            transcript_excerpt_ephemeral=True,
            evidence_json={"transcript_excerpt": text[:240], "ephemeral": True},
            recommendation_json={"action": "review_voice_style" if requires_review else "continue"},
            metadata_={"source": "voice_simulation"},
        )
        s.add(guard)
        s.commit()
        s.refresh(guard)
        return _guard_to_dict(guard)


def _record_stt_event(voice_session_id: uuid.UUID, payload: dict[str, Any], *, final: bool) -> dict[str, Any] | None:
    with get_session() as s:
        voice_session = s.get(CompanionVoiceSession, voice_session_id)
        if voice_session is None:
            return None
        turn = _get_or_create_current_turn(s, voice_session, "listening")
        provider = stt_provider_service.get_stt_provider("simulation")
        result = provider.transcribe(payload, final=final)
        event = SttEvent(
            user_id=voice_session.user_id,
            voice_session_id=voice_session.id,
            voice_turn_id=turn.id,
            provider_config_id=voice_session.stt_provider_config_id,
            event_type=result["event_type"],
            event_status="recorded",
            transcript_text=result["transcript_text"],
            transcript_is_ephemeral=True,
            retention_policy="ephemeral",
            confidence=result["confidence"],
            language=result["language"],
            raw_payload_json=result["raw_payload_json"],
            occurred_at=_now(),
            metadata_={"source": "voice_simulation"},
        )
        s.add(event)
        turn.user_utterance_preview = result["transcript_text"][:240]
        turn.turn_status = "processing" if final else "listening"
        s.commit()
        s.refresh(event)
        return _stt_event_to_dict(event)


def _ensure_simulation_provider(
    s,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    provider_scope: str,
) -> VoiceProviderConfig:
    existing = s.execute(
        select(VoiceProviderConfig)
        .where(
            VoiceProviderConfig.user_id == user_id,
            VoiceProviderConfig.companion_id == companion_id,
            VoiceProviderConfig.provider_scope == provider_scope,
            VoiceProviderConfig.provider_kind == "simulation",
            VoiceProviderConfig.provider_status == "active",
        )
        .order_by(VoiceProviderConfig.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    if existing:
        return existing
    provider = VoiceProviderConfig(
        user_id=user_id,
        companion_id=companion_id,
        provider_scope=provider_scope,
        provider_kind="simulation",
        provider_status="active",
        provider_name="voice_simulation",
        is_default=True,
        supports_streaming=False,
        stores_plaintext_secret=False,
        credentials_ref=None,
        provider_config_json={"real_provider_required": False},
        metadata_={"source": "voice_simulation"},
    )
    s.add(provider)
    s.flush()
    return provider


def _ensure_voice_profile(
    s,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    provider_config_id: uuid.UUID,
    payload: dict[str, Any],
) -> CompanionVoiceProfile:
    profile_id = _to_uuid(payload.get("voice_profile_id"))
    if profile_id:
        profile = s.get(CompanionVoiceProfile, profile_id)
        if profile:
            return profile
    existing = s.execute(
        select(CompanionVoiceProfile)
        .where(
            CompanionVoiceProfile.user_id == user_id,
            CompanionVoiceProfile.companion_id == companion_id,
            CompanionVoiceProfile.profile_status == "active",
        )
        .order_by(CompanionVoiceProfile.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    if existing:
        return existing
    profile = CompanionVoiceProfile(
        user_id=user_id,
        companion_id=companion_id,
        provider_config_id=provider_config_id,
        profile_status="active",
        voice_profile_name=payload.get("voice_profile_name") or "default",
        voice_persona_summary=payload.get("voice_persona_summary") or "Simulated voice profile for Realtime compatibility",
        tts_voice_key=payload.get("tts_voice_key") or "simulation-default",
        stt_locale=payload.get("stt_locale") or "auto",
        speaking_style_json=payload.get("speaking_style_json") or {"style": "calm"},
        turn_taking_preferences_json=payload.get("turn_taking_preferences_json") or {"single_speaker": True},
        metadata_={"source": "voice_simulation"},
    )
    s.add(profile)
    s.flush()
    return profile


def _resolve_speaker_participant_id(
    s,
    realtime_session_id: uuid.UUID,
    speaker_companion_id: uuid.UUID,
    payload: dict[str, Any],
) -> uuid.UUID | None:
    explicit = _to_uuid(payload.get("speaker_realtime_participant_id"))
    if explicit:
        return explicit
    participant = s.execute(
        select(RealtimeCoPresenceParticipant)
        .where(
            RealtimeCoPresenceParticipant.realtime_session_id == realtime_session_id,
            RealtimeCoPresenceParticipant.participant_companion_id == speaker_companion_id,
        )
        .order_by(RealtimeCoPresenceParticipant.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    return participant.id if participant else None


def _create_voice_turn(s, voice_session: CompanionVoiceSession, status: str) -> VoiceTurn:
    max_turn = (
        s.execute(
            select(func.max(VoiceTurn.turn_index)).where(VoiceTurn.voice_session_id == voice_session.id)
        ).scalar()
        or 0
    )
    turn = VoiceTurn(
        user_id=voice_session.user_id,
        voice_session_id=voice_session.id,
        realtime_session_id=voice_session.realtime_session_id,
        speaker_companion_id=voice_session.speaker_companion_id,
        speaker_realtime_participant_id=voice_session.speaker_realtime_participant_id,
        turn_index=max_turn + 1,
        turn_status=status,
        input_modality="voice",
        output_modality="voice",
        transcript_retention_policy="ephemeral",
        memory_candidate_policy="candidate_review",
        turn_payload_json={"memory_candidate_requires_review": True},
        started_at=_now(),
        metadata_={"source": "voice_simulation"},
    )
    s.add(turn)
    s.flush()
    return turn


def _get_or_create_current_turn(s, voice_session: CompanionVoiceSession, status: str) -> VoiceTurn:
    turn = s.execute(
        select(VoiceTurn)
        .where(
            VoiceTurn.voice_session_id == voice_session.id,
            VoiceTurn.turn_status.notin_(["completed", "interrupted", "cancelled"]),
        )
        .order_by(VoiceTurn.turn_index.desc())
        .limit(1)
    ).scalar_one_or_none()
    if turn:
        return turn
    return _create_voice_turn(s, voice_session, status)


def _record_turn_taking_event(
    s,
    voice_session: CompanionVoiceSession,
    turn: VoiceTurn,
    payload: dict[str, Any],
) -> TurnTakingEvent:
    decision = turn_taking_service.decide_turn_taking_state(payload)
    event = TurnTakingEvent(
        user_id=voice_session.user_id,
        voice_session_id=voice_session.id,
        voice_turn_id=turn.id,
        current_speaker_companion_id=voice_session.speaker_companion_id,
        selected_participant_id=voice_session.speaker_realtime_participant_id,
        event_type=decision["event_type"],
        event_status=decision["event_status"],
        turn_index=turn.turn_index,
        decision_json=decision["decision_json"],
        occurred_at=_now(),
        metadata_={"source": "voice_simulation"},
    )
    s.add(event)
    return event


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _voice_session_to_dict(item: CompanionVoiceSession) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "user_id": str(item.user_id),
        "realtime_session_id": str(item.realtime_session_id),
        "co_presence_session_id": str(item.co_presence_session_id) if item.co_presence_session_id else None,
        "speaker_companion_id": str(item.speaker_companion_id),
        "speaker_realtime_participant_id": str(item.speaker_realtime_participant_id)
        if item.speaker_realtime_participant_id
        else None,
        "voice_profile_id": str(item.voice_profile_id) if item.voice_profile_id else None,
        "stt_provider_config_id": str(item.stt_provider_config_id) if item.stt_provider_config_id else None,
        "tts_provider_config_id": str(item.tts_provider_config_id) if item.tts_provider_config_id else None,
        "session_status": item.session_status,
        "transcript_retention_policy": item.transcript_retention_policy,
        "memory_write_policy": item.memory_write_policy,
        "allow_multi_speaker": item.allow_multi_speaker,
        "permission_snapshot_json": item.permission_snapshot_json or {},
        "voice_runtime_json": item.voice_runtime_json or {},
        "started_at": _dt(item.started_at),
        "ended_at": _dt(item.ended_at),
    }


def _voice_turn_to_dict(item: VoiceTurn) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "turn_index": item.turn_index,
        "turn_status": item.turn_status,
        "input_modality": item.input_modality,
        "output_modality": item.output_modality,
        "transcript_retention_policy": item.transcript_retention_policy,
        "memory_candidate_policy": item.memory_candidate_policy,
        "user_utterance_preview": item.user_utterance_preview,
        "companion_response_preview": item.companion_response_preview,
        "turn_payload_json": item.turn_payload_json or {},
    }


def _stt_event_to_dict(item: SttEvent) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "voice_session_id": str(item.voice_session_id),
        "voice_turn_id": str(item.voice_turn_id) if item.voice_turn_id else None,
        "event_type": item.event_type,
        "event_status": item.event_status,
        "transcript_text": item.transcript_text,
        "transcript_is_ephemeral": item.transcript_is_ephemeral,
        "retention_policy": item.retention_policy,
        "confidence": item.confidence,
        "language": item.language,
        "raw_payload_json": item.raw_payload_json or {},
        "occurred_at": _dt(item.occurred_at),
    }


def _tts_event_to_dict(item: TtsEvent) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "voice_session_id": str(item.voice_session_id),
        "voice_turn_id": str(item.voice_turn_id) if item.voice_turn_id else None,
        "event_type": item.event_type,
        "event_status": item.event_status,
        "text_preview": item.text_preview,
        "audio_artifact_ref": item.audio_artifact_ref,
        "audio_retention_policy": item.audio_retention_policy,
        "raw_payload_json": item.raw_payload_json or {},
        "occurred_at": _dt(item.occurred_at),
    }


def _turn_taking_event_to_dict(item: TurnTakingEvent) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "voice_session_id": str(item.voice_session_id),
        "voice_turn_id": str(item.voice_turn_id) if item.voice_turn_id else None,
        "current_speaker_companion_id": str(item.current_speaker_companion_id)
        if item.current_speaker_companion_id
        else None,
        "selected_participant_id": str(item.selected_participant_id) if item.selected_participant_id else None,
        "event_type": item.event_type,
        "event_status": item.event_status,
        "turn_index": item.turn_index,
        "decision_json": item.decision_json or {},
        "occurred_at": _dt(item.occurred_at),
    }


def _interruption_to_dict(item: VoiceInterruptionEvent) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "voice_session_id": str(item.voice_session_id),
        "voice_turn_id": str(item.voice_turn_id) if item.voice_turn_id else None,
        "interruption_type": item.interruption_type,
        "interruption_status": item.interruption_status,
        "stops_tts": item.stops_tts,
        "requires_trace": item.requires_trace,
        "interruption_payload_json": item.interruption_payload_json or {},
        "occurred_at": _dt(item.occurred_at),
    }


def _guard_to_dict(item: VoicePersonaGuardRun) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "voice_session_id": str(item.voice_session_id),
        "voice_turn_id": str(item.voice_turn_id) if item.voice_turn_id else None,
        "speaker_companion_id": str(item.speaker_companion_id),
        "guard_status": item.guard_status,
        "drift_risk_level": item.drift_risk_level,
        "voice_style_consistency_score": item.voice_style_consistency_score,
        "requires_review": item.requires_review,
        "blocks_response": item.blocks_response,
        "transcript_excerpt_ephemeral": item.transcript_excerpt_ephemeral,
        "evidence_json": item.evidence_json or {},
        "recommendation_json": item.recommendation_json or {},
    }
