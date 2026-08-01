"""Typed commands for runtime quality feedback."""

from pydantic import BaseModel, ConfigDict, Field


class QualityFeedbackRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_attempt_count: int = Field(ge=0)


class QualityFeedbackRetestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_feedback_revision: int = Field(ge=1)
    reason: str = Field(min_length=2, max_length=500)
