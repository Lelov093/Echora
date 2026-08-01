"""Realtime compatibility STT provider adapter service.

Initial Realtime compatibility only ships a simulation adapter. Real provider calls stay behind this
small interface and are not required for the realtime voice contract.
"""

from dataclasses import dataclass
from typing import Any, Protocol


class SttProviderAdapter(Protocol):
    provider_kind: str

    def transcribe(self, payload: dict[str, Any], *, final: bool = False) -> dict[str, Any]:
        ...


@dataclass
class SimulatedSttProvider:
    provider_kind: str = "simulation"

    def transcribe(self, payload: dict[str, Any], *, final: bool = False) -> dict[str, Any]:
        text = str(payload.get("text") or payload.get("transcript_text") or "simulated voice transcript").strip()
        return {
            "event_type": "final" if final else "partial",
            "transcript_text": text,
            "confidence": float(payload.get("confidence", 0.99 if final else 0.72)),
            "language": payload.get("language") or "auto",
            "transcript_is_ephemeral": True,
            "retention_policy": "ephemeral",
            "raw_payload_json": {
                "provider": self.provider_kind,
                "simulation": True,
                "audio_ref": payload.get("audio_ref"),
                "final": final,
            },
        }


def simulate_stt(payload: dict[str, Any], *, final: bool = False) -> dict[str, Any]:
    return SimulatedSttProvider().transcribe(payload, final=final)


def get_stt_provider(provider_kind: str | None = None) -> SttProviderAdapter:
    if provider_kind in (None, "", "simulation", "provider_adapter"):
        return SimulatedSttProvider()
    return SimulatedSttProvider()
