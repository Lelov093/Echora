"""Summarize realtime signals, update EWMA state, and gate interruption."""

import uuid

from sqlalchemy import or_, select

from app.agents.nodes.realtime_trace_utils import append_step, record_trace_event
from app.agents.state import RealtimeAgentState
from app.db.models import (
    CompanionResidentStatusEvent,
    FocusModeEvent,
    RealtimeChannelStateEvent,
    RealtimeCoPresenceSession,
    RealtimeSessionChannel,
    ScopedHardStopEvent,
)
from app.services.realtime_algorithm_service import (
    decide_realtime_interruption,
    infer_signal_features,
    normalize_observed_signal,
    update_realtime_latent_state,
)
from app.services.trace_service import get_session


def realtime_algorithm_decision_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        session_id = uuid.UUID(state["realtime_session_id"])
        companion_id = uuid.UUID(state["companion_id"])
        user_id = uuid.UUID(state["user_id"])
        session = s.get(RealtimeCoPresenceSession, session_id)
        if session is None:
            state.setdefault("errors", []).append({"step": "realtime_algorithm_decision", "error": "session_not_found"})
            return state

        focus = _active_focus(s, user_id, companion_id, session_id)
        resident = _latest_resident(s, user_id, companion_id)
        hard_stop = _active_hard_stop(s, user_id, companion_id, session_id)
        channel = _default_channel(s, session_id)
        raw_signal = _latest_channel_signal(s, session_id)
        signal = normalize_observed_signal(raw_signal)
        features = infer_signal_features(
            signal,
            focus_active=focus is not None,
            boundary_snapshot=session.boundary_snapshot_json or {},
        )
        runtime_state = dict(session.runtime_state_json or {})
        algorithm_state = dict(runtime_state.get("realtime_algorithm") or {})
        latent_state = update_realtime_latent_state(algorithm_state.get("latent_state"), features)

        permission_snapshot = session.permission_snapshot_json or {}
        permission_allowed = bool(
            permission_snapshot.get("allows_proactive_realtime")
            or permission_snapshot.get("allows_unsolicited_presence")
            or (resident and resident.allows_unsolicited_presence)
        )
        boundary_snapshot = session.boundary_snapshot_json or {}
        boundary_allowed = not bool(
            boundary_snapshot.get("block_proactive_realtime")
            or boundary_snapshot.get("hard_block")
            or boundary_snapshot.get("realtime_revoked")
        )
        revoked = (
            session.session_status in {"ended", "revoked"}
            or bool(permission_snapshot.get("revoked"))
            or channel is None
            or channel.channel_status in {"closed", "failed", "revoked"}
        )
        hard_stop_active = hard_stop is not None or bool((state.get("scoped_hard_stop") or {}).get("active"))
        decision = decide_realtime_interruption(
            latent_state,
            permission_allowed=permission_allowed,
            boundary_allowed=boundary_allowed,
            focus_active=focus is not None,
            hard_stop_active=hard_stop_active,
            revoked=revoked,
        )

        algorithm_state = {
            "algorithm_version": decision["algorithm_version"],
            "observed_signal": signal,
            "latent_state": latent_state,
            "interruption_decision": decision,
        }
        runtime_state["realtime_algorithm"] = algorithm_state
        session.runtime_state_json = runtime_state
        realtime_state = dict(state.get("realtime_session") or {})
        realtime_state["observed_signal"] = signal
        realtime_state["realtime_latent_state"] = latent_state
        realtime_state["realtime_algorithm_decision"] = decision
        state["realtime_session"] = realtime_state

        event = record_trace_event(
            s,
            state,
            event_type="session_state",
            event_status="recorded" if decision["proactive_insert_allowed"] else "suppressed",
            event_summary=f"Realtime interruption decision: {decision['decision']} ({decision['reason']}).",
            event_payload_json={
                "algorithm_version": decision["algorithm_version"],
                "signal": signal,
                "latent_state": latent_state,
                "decision": decision,
                "real_media_enabled": False,
            },
        )
        append_step(
            state,
            step="realtime_algorithm_decision",
            order=206,
            realtime_trace_event_id=str(event.id),
            algorithm_version=decision["algorithm_version"],
            decision=decision["decision"],
            reason=decision["reason"],
            score=decision["score"],
            threshold=decision["threshold"],
            proactive_insert_allowed=decision["proactive_insert_allowed"],
        )
        s.commit()
    return state


def _latest_channel_signal(s, session_id: uuid.UUID) -> dict:
    event = (
        s.execute(
            select(RealtimeChannelStateEvent)
            .where(RealtimeChannelStateEvent.realtime_session_id == session_id)
            .order_by(RealtimeChannelStateEvent.occurred_at.desc(), RealtimeChannelStateEvent.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    )
    if event is None:
        return {"signal_type": "channel", "safe_summary": "Realtime channel is idle.", "source": "channel_state"}
    payload = event.event_payload_json or {}
    nested = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    explicit_summary = nested.get("safe_summary") or nested.get("summary")
    if explicit_summary:
        safe_summary = explicit_summary
    else:
        raw_preview = payload.get("preview") or nested.get("text")
        safe_summary = (
            f"{payload.get('event_type') or event.event_type} observed ({len(str(raw_preview))} chars)."
            if raw_preview
            else payload.get("event_type") or event.event_type
        )
    return {
        "event_type": (payload.get("event_type") or event.event_type),
        "safe_summary": safe_summary,
        "source": "realtime_channel_event",
    }


def _active_focus(s, user_id: uuid.UUID, companion_id: uuid.UUID, session_id: uuid.UUID):
    return (
        s.execute(
            select(FocusModeEvent)
            .where(
                FocusModeEvent.user_id == user_id,
                FocusModeEvent.focus_status.in_(["active", "started"]),
                FocusModeEvent.suppress_presence.is_(True),
                FocusModeEvent.ended_at.is_(None),
                or_(FocusModeEvent.companion_id.is_(None), FocusModeEvent.companion_id == companion_id),
                or_(FocusModeEvent.realtime_session_id.is_(None), FocusModeEvent.realtime_session_id == session_id),
            )
            .order_by(FocusModeEvent.started_at.desc(), FocusModeEvent.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    )


def _latest_resident(s, user_id: uuid.UUID, companion_id: uuid.UUID):
    return (
        s.execute(
            select(CompanionResidentStatusEvent)
            .where(
                CompanionResidentStatusEvent.user_id == user_id,
                CompanionResidentStatusEvent.companion_id == companion_id,
            )
            .order_by(CompanionResidentStatusEvent.occurred_at.desc(), CompanionResidentStatusEvent.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    )


def _active_hard_stop(s, user_id: uuid.UUID, companion_id: uuid.UUID, session_id: uuid.UUID):
    return (
        s.execute(
            select(ScopedHardStopEvent)
            .where(
                ScopedHardStopEvent.user_id == user_id,
                ScopedHardStopEvent.hard_stop_status == "active",
                ScopedHardStopEvent.released_at.is_(None),
                or_(
                    ScopedHardStopEvent.hard_stop_scope == "all_realtime",
                    (ScopedHardStopEvent.hard_stop_scope == "session")
                    & (ScopedHardStopEvent.realtime_session_id == session_id),
                    (ScopedHardStopEvent.hard_stop_scope == "companion")
                    & (ScopedHardStopEvent.companion_id == companion_id),
                ),
            )
            .order_by(ScopedHardStopEvent.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    )


def _default_channel(s, session_id: uuid.UUID):
    return (
        s.execute(
            select(RealtimeSessionChannel)
            .where(RealtimeSessionChannel.realtime_session_id == session_id)
            .order_by(RealtimeSessionChannel.is_default_event_stream.desc(), RealtimeSessionChannel.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
    )
