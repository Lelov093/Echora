"""ContinuityRefreshFlow — refresh continuity snapshots."""

import uuid

from app.services import continuity_service


def refresh_continuity(companion_id: str, conversation_id: str | None = None) -> dict:
    """Force a continuity snapshot refresh."""
    return continuity_service.refresh_continuity({
        "companion_id": companion_id,
        "conversation_id": conversation_id,
        "snapshot_type": "manual_refresh",
        "user_id": "4a4f3806-0d3e-4ab1-80ed-51f93b60aa80",
    })
