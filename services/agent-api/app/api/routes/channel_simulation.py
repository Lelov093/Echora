"""Test-only channel adapter routes."""

import uuid

from fastapi import APIRouter

from app.schemas.common import err, ok
from app.services.channel_simulation_service import ChannelSimulationAdapter, revoke_simulated_binding, simulate_two_companion_copresence

router = APIRouter(prefix="/channel-simulation", tags=["Test Support"])


@router.post("/inbound")
def channel_simulation_inbound(body: dict):
    data = ChannelSimulationAdapter().simulate_inbound(body or {})
    if not data:
        return err("CHANNEL_SIMULATION_INBOUND_FAILED", "Unable to simulate simulated inbound")
    return ok(data)


@router.post("/outbound")
def channel_simulation_outbound(body: dict):
    data = ChannelSimulationAdapter().simulate_outbound(body or {})
    if not data:
        return err("CHANNEL_SIMULATION_OUTBOUND_FAILED", "Unable to simulate simulated outbound")
    return ok(data)


@router.post("/failure")
def channel_simulation_failure(body: dict):
    data = ChannelSimulationAdapter().simulate_failure(body or {})
    if not data:
        return err("CHANNEL_SIMULATION_FAILURE_FAILED", "Unable to simulate simulated failure")
    return ok(data)


@router.post("/rate-limit")
def channel_simulation_rate_limit(body: dict):
    data = ChannelSimulationAdapter().simulate_rate_limit(body or {})
    if not data:
        return err("CHANNEL_SIMULATION_RATE_LIMIT_FAILED", "Unable to simulate simulated rate limit")
    return ok(data)


@router.post("/revoke")
def channel_simulation_revoke(body: dict):
    if not body.get("channel_binding_id"):
        return err("CHANNEL_SIMULATION_REVOKE_BINDING_REQUIRED", "channel_binding_id is required")
    data = revoke_simulated_binding(uuid.UUID(body["channel_binding_id"]), body.get("reason"))
    if not data:
        return err("CHANNEL_SIMULATION_REVOKE_FAILED", "Unable to revoke simulated binding")
    return ok(data)


@router.post("/scenarios/two-companion-copresence")
def channel_simulation_two_companion_copresence(body: dict):
    data = simulate_two_companion_copresence(body or {})
    if not data:
        return err("CHANNEL_SIMULATION_SCENARIO_FAILED", "Unable to run simulated co-presence scenario")
    return ok(data)
