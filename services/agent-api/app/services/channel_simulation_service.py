"""Channel Gateway simulation support.

The channel simulation exercises the Channel Gateway contract without any real
network, Discord SDK, or external token.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    ChannelDeliveryEvent,
    ChannelFailureEvent,
    ChannelRateLimitEvent,
    Companion,
    User,
)
from app.services import (
    channel_gateway_service,
    channel_memory_boundary_service,
    channel_message_service,
)

_engine = None
_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "api_key", "authorization", "credential", "raw")
# Existing seeded databases identify the test provider with this compatibility key.
_COMPAT_PROVIDER_KEY = "mock_channel"


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


class ChannelSimulationAdapter:
    provider_key = _COMPAT_PROVIDER_KEY

    def simulate_inbound(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        message_result = channel_message_service.ingest_inbound(
            {
                "channel_binding_id": payload.get("channel_binding_id"),
                "message_summary": payload.get("message_summary") or "Simulated inbound message",
                "external_message_ref_hash": payload.get("external_message_ref_hash") or f"simulated-in-{uuid.uuid4().hex[:12]}",
                "external_conversation_ref_hash": payload.get("external_conversation_ref_hash"),
                "safe_payload_json": {
                    "adapter": "channel_simulation",
                    "shared_channel_ref_hash": payload.get("shared_channel_ref_hash"),
                    **_safe_json(payload.get("safe_payload_json")),
                },
            }
        )
        if not message_result:
            return None
        candidate = None
        if payload.get("generate_memory_candidate"):
            message = message_result["message"]
            candidate = channel_memory_boundary_service.create_candidate(
                {
                    "channel_binding_id": message["channel_binding_id"],
                    "channel_message_event_id": message["id"],
                    "target_memory_scope": payload.get("target_memory_scope") or "companion_private",
                    "candidate_summary": payload.get("candidate_summary") or "Simulated channel memory candidate",
                    "suggested_memory_content": payload.get("suggested_memory_content") or "",
                    "salience_score": payload.get("salience_score", 0.5),
                    "safe_evidence_json": {"adapter": "channel_simulation"},
                }
            )
        return {
            "adapter": "channel_simulation",
            "inbound": message_result,
            "memory_candidate": candidate,
            "real_provider_call": False,
        }

    def simulate_outbound(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        outbound = channel_message_service.queue_outbound(
            {
                "channel_binding_id": payload.get("channel_binding_id"),
                "reply_to_message_event_id": payload.get("reply_to_message_event_id"),
                "message_summary": payload.get("message_summary") or "Simulated outbound message",
                "external_delivery_ref_hash": payload.get("external_delivery_ref_hash") or f"simulated-out-{uuid.uuid4().hex[:12]}",
                "safe_payload_json": {
                    "adapter": "channel_simulation",
                    "shared_channel_ref_hash": payload.get("shared_channel_ref_hash"),
                    **_safe_json(payload.get("safe_payload_json")),
                },
                "safe_delivery_payload_json": {"adapter": "channel_simulation", **_safe_json(payload.get("safe_delivery_payload_json"))},
            }
        )
        if not outbound:
            return None
        delivery = outbound.get("delivery") or {}
        if delivery.get("delivery_status") == "queued":
            with get_session() as s:
                row = s.get(ChannelDeliveryEvent, uuid.UUID(delivery["id"]))
                if row is not None:
                    row.delivery_status = "sent"
                    row.delivered_at = _now()
                    row.delivery_summary = "Simulated delivery sent"
                    s.commit()
                    s.refresh(row)
                    outbound["delivery"] = channel_message_service._delivery_to_dict(row)
        outbound["simulated_delivery_result"] = {
            "adapter": "channel_simulation",
            "status": outbound.get("delivery", {}).get("delivery_status"),
            "real_provider_call": False,
        }
        return outbound

    def simulate_failure(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        with channel_gateway_service.get_session() as s:
            binding = s.get(channel_gateway_service.ChannelBinding, _to_uuid(payload.get("channel_binding_id")))
            if binding is None:
                return None
            event = ChannelFailureEvent(
                provider_id=binding.provider_id,
                provider_bot_id=binding.provider_bot_id,
                channel_binding_id=binding.id,
                failure_type=payload.get("failure_type") or "provider_error",
                failure_status="recorded",
                safe_error_summary=payload.get("safe_error_summary") or "Simulation provider failure",
                safe_error_json={"adapter": "channel_simulation"},
                occurred_at=_now(),
                metadata_={"source": "channel_simulation"},
            )
            s.add(event)
            s.commit()
            s.refresh(event)
            return _failure_to_dict(event)

    def simulate_rate_limit(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        with channel_gateway_service.get_session() as s:
            binding = s.get(channel_gateway_service.ChannelBinding, _to_uuid(payload.get("channel_binding_id")))
            if binding is None:
                return None
            event = ChannelRateLimitEvent(
                provider_id=binding.provider_id,
                provider_bot_id=binding.provider_bot_id,
                channel_binding_id=binding.id,
                rate_limit_status="active",
                retry_after_seconds=max(0, int(payload.get("retry_after_seconds", 30))),
                safe_rate_limit_json={"adapter": "channel_simulation"},
                occurred_at=_now(),
                metadata_={"source": "channel_simulation"},
            )
            s.add(event)
            s.commit()
            s.refresh(event)
            return _rate_limit_to_dict(event)


def simulate_two_companion_copresence(payload: dict[str, Any]) -> dict[str, Any] | None:
    user_id, companion_a_id, companion_b_id = _resolve_user_and_companions(payload)
    provider = channel_gateway_service.get_provider_by_key(_COMPAT_PROVIDER_KEY)
    if provider is None:
        return None
    shared_channel_ref_hash = payload.get("shared_channel_ref_hash") or f"simulated-shared-{uuid.uuid4().hex[:12]}"
    bot_a = channel_gateway_service.register_bot(
        user_id,
        {
            "provider_id": provider["id"],
            "bot_key": f"simulated-a-{uuid.uuid4().hex[:8]}",
            "bot_display_name": "Simulated Companion A",
            "safe_metadata_json": {"role": "simulated_companion_a"},
        },
    )
    bot_b = channel_gateway_service.register_bot(
        user_id,
        {
            "provider_id": provider["id"],
            "bot_key": f"simulated-b-{uuid.uuid4().hex[:8]}",
            "bot_display_name": "Simulated Companion B",
            "safe_metadata_json": {"role": "simulated_companion_b"},
        },
    )
    if bot_a is None or bot_b is None:
        return None

    binding_a = channel_gateway_service.create_binding(
        user_id,
        {
            "companion_id": str(companion_a_id),
            "provider_id": provider["id"],
            "provider_bot_id": bot_a["id"],
            "binding_scope": "guild_channel",
            "permission_scope": "reply_only",
            "outbound_policy": "reply_only",
            "external_channel_ref_hash": shared_channel_ref_hash,
        },
    )
    binding_b = channel_gateway_service.create_binding(
        user_id,
        {
            "companion_id": str(companion_b_id),
            "provider_id": provider["id"],
            "provider_bot_id": bot_b["id"],
            "binding_scope": "guild_channel",
            "permission_scope": "reply_only",
            "outbound_policy": "user_approved_only",
            "external_channel_ref_hash": shared_channel_ref_hash,
        },
    )
    if binding_a is None or binding_b is None:
        return None
    adapter = ChannelSimulationAdapter()
    inbound = adapter.simulate_inbound(
        {
            "channel_binding_id": binding_a["id"],
            "message_summary": "Simulated shared channel inbound received by Companion A bot",
            "shared_channel_ref_hash": shared_channel_ref_hash,
            "generate_memory_candidate": True,
            "candidate_summary": "Simulated co-presence shared channel candidate",
        }
    )
    outbound = adapter.simulate_outbound(
        {
            "channel_binding_id": binding_b["id"],
            "message_summary": "Simulated shared channel outbound sent by Companion B bot",
            "shared_channel_ref_hash": shared_channel_ref_hash,
        }
    )
    return {
        "adapter": "channel_simulation",
        "shared_channel_ref_hash": shared_channel_ref_hash,
        "participants": [
            {"companion_id": str(companion_a_id), "provider_bot_id": bot_a["id"], "binding_id": binding_a["id"]},
            {"companion_id": str(companion_b_id), "provider_bot_id": bot_b["id"], "binding_id": binding_b["id"]},
        ],
        "inbound": inbound,
        "outbound": outbound,
        "real_provider_call": False,
    }


def revoke_simulated_binding(binding_id: uuid.UUID, reason: str | None = None) -> dict[str, Any] | None:
    return channel_gateway_service.revoke_binding(binding_id, reason or "channel simulation revoke")


def _resolve_user_and_companions(payload: dict[str, Any]) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user_id = _to_uuid(payload.get("user_id"))
    companion_a_id = _to_uuid(payload.get("companion_a_id"))
    companion_b_id = _to_uuid(payload.get("companion_b_id"))
    with get_session() as s:
        if user_id is None:
            user_id = s.execute(select(User).order_by(User.created_at.asc()).limit(1)).scalar_one().id
        companions = list(
            s.execute(select(Companion).where(Companion.user_id == user_id).order_by(Companion.created_at.asc())).scalars().all()
        )
        while len(companions) < 2:
            companion = Companion(
                user_id=user_id,
                name=f"Simulated Channel Companion {len(companions) + 1}",
                subtitle="Simulated channel adapter companion",
                current_mode="project",
                current_status="idle",
            )
            s.add(companion)
            s.commit()
            companions.append(companion)
        return user_id, companion_a_id or companions[0].id, companion_b_id or companions[1].id


def _failure_to_dict(row: ChannelFailureEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "provider_id": str(row.provider_id),
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "failure_type": row.failure_type,
        "failure_status": row.failure_status,
        "safe_error_summary": row.safe_error_summary,
        "safe_error_json": row.safe_error_json or {},
    }


def _rate_limit_to_dict(row: ChannelRateLimitEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "provider_id": str(row.provider_id),
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "rate_limit_status": row.rate_limit_status,
        "retry_after_seconds": row.retry_after_seconds,
        "safe_rate_limit_json": row.safe_rate_limit_json or {},
    }


def _safe_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _scrub(value)


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower().replace("-", "_") for part in _SENSITIVE_KEY_PARTS):
                continue
            result[key_text] = _scrub(item)
        return result
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _to_uuid(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
