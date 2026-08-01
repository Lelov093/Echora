"""FeedbackApplyFlow — apply feedback events to calibration."""

import uuid

from app.services import feedback_service


def apply_feedback(feedback_event_id: str) -> dict:
    """Apply a feedback event's calibration effects."""
    return feedback_service.apply_feedback_event(uuid.UUID(feedback_event_id))
