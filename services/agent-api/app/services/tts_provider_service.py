"""Realtime compatibility TTS provider adapter service.

The first adapter is deliberately simulation-only: it records text/audio metadata
without generating or retaining real audio.
"""

from dataclasses import dataclass
from typing import Any, Protocol


class TtsProviderAdapter(Protocol):
    provider_kind: str

    def synthesize(self, payload: dict[str, Any], *, event_type: str = "queued") -> dict[str, Any]:
        ...


@dataclass
class SimulatedTtsProvider:
    provider_kind: str = "simulation"

    def synthesize(self, payload: dict[str, Any], *, event_type: str = "queued") -> dict[str, Any]:
        text = str(payload.get("text") or payload.get("text_preview") or "simulated companion response").strip()
        artifact_suffix = abs(hash(text)) % 100000
        return {
            "event_type": event_type,
            "text_preview": text[:240],
            "audio_artifact_ref": f"simulation://tts/{artifact_suffix}" if event_type in {"completed", "started"} else None,
            "audio_retention_policy": "ephemeral",
            "raw_payload_json": {
                "provider": self.provider_kind,
                "simulation": True,
                "voice_key": payload.get("voice_key"),
                "has_real_audio": False,
            },
        }


def simulate_tts(payload: dict[str, Any], *, event_type: str = "queued") -> dict[str, Any]:
    return SimulatedTtsProvider().synthesize(payload, event_type=event_type)


def get_tts_provider(provider_kind: str | None = None) -> TtsProviderAdapter:
    if provider_kind in (None, "", "simulation", "provider_adapter"):
        return SimulatedTtsProvider()
    return SimulatedTtsProvider()
