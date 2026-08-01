"""Presence Boundary Gate — checks settings before allowing opportunities."""

from typing import Any

from app.core.algorithm_contract import PRESENCE_PRIORITY_CONTRACT


def check_boundary(
    boundary_settings: dict[str, Any],
    priority_score: float,
    presence_type: str = "continuation",
    interruption_risk: float = 0.0,
    sensitivity_risk: float = 0.0,
    recent_dismissal_count: int = 0,
    recommended_surface: str = "queue",
) -> dict:
    """Check if a Presence Opportunity should be allowed.

    Returns dict with allowed, surface, and reason.
    """
    allowed = True
    reasons = []
    surface = recommended_surface if recommended_surface in {"hub", "queue"} else "queue"

    # 1. allow_proactive_presence
    if not boundary_settings.get("allow_proactive_presence", True):
        allowed = False
        reasons.append("proactive presence disabled by settings")

    # 2. proactive_level
    level = boundary_settings.get("proactive_level", "medium")
    if level == "low" and priority_score < 0.75:
        allowed = False
        reasons.append("proactive_level=low, priority too low")
    elif (
        level == "medium"
        and priority_score
        < PRESENCE_PRIORITY_CONTRACT["thresholds"]["low_priority_queue"]
    ):
        allowed = False
        reasons.append("proactive_level=medium, priority too low")

    # 3. notification_surface
    surface_setting = boundary_settings.get("notification_surface", "hub_queue_only")
    if surface_setting == "hub_queue_only":
        surface = "hub" if recommended_surface == "hub" else "queue"
    elif surface_setting == "allow_light_notification":
        surface = "queue"
    elif surface_setting == "disabled":
        allowed = False
        reasons.append("notifications disabled")

    # 4. suppressed types
    suppressed = boundary_settings.get("suppressed_presence_types", [])
    if isinstance(suppressed, list) and presence_type in suppressed:
        allowed = False
        reasons.append(f"type '{presence_type}' suppressed by user")

    # 5. recent dismissals
    if recent_dismissal_count >= PRESENCE_PRIORITY_CONTRACT["dismissal_suppress_count"]:
        allowed = False
        reasons.append("same-type dismissals exceeded recent window limit")

    # 6. interruption risk
    if interruption_risk >= 0.70:
        allowed = False
        reasons.append("interruption risk too high")

    # 7. sensitivity
    if sensitivity_risk >= 0.70:
        surface = "hub"
        reasons.append("sensitive content: hub only, no queue notification")

    return {
        "allowed": allowed,
        "surface": surface,
        "reasons": reasons,
        "blocked": not allowed,
        "decision": "blocked" if not allowed else "allowed",
    }
