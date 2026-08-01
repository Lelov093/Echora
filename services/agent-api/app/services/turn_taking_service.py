"""Realtime compatibility turn-taking decision helper."""

from typing import Any


def select_realtime_speaker(
    participants: list[dict[str, Any]],
    active_companion_id: str | None,
) -> dict[str, Any] | None:
    """Select one active speaker and never promote an observing participant."""
    eligible = [
        participant
        for participant in participants
        if participant.get("participant_status") == "active"
        and participant.get("participant_role") == "speaker_companion"
        and participant.get("can_speak") is True
        and participant.get("participant_companion_id") not in (None, "")
    ]
    if active_companion_id:
        active = [
            participant
            for participant in eligible
            if str(participant.get("participant_companion_id")) == str(active_companion_id)
        ]
        if active:
            return active[0]
    return eligible[0] if eligible else None


def decide_turn_taking_state(payload: dict[str, Any]) -> dict[str, Any]:
    requested = str(payload.get("event_type") or "").strip()
    if requested:
        event_type = requested
    elif payload.get("speech_detected"):
        event_type = "speech_detected"
    elif payload.get("release_turn"):
        event_type = "turn_released"
    else:
        event_type = "speaker_selected"

    if event_type not in {
        "listening_started",
        "speaker_selected",
        "speech_detected",
        "turn_locked",
        "turn_released",
        "turn_completed",
    }:
        event_type = "speaker_selected"

    return {
        "event_type": event_type,
        "event_status": "recorded",
        "decision_json": {
            "reason": payload.get("reason") or "single speaker companion selected",
            "single_speaker": True,
            "source": "realtime_voice_simulation",
        },
    }
