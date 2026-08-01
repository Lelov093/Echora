from pydantic import BaseModel, Field


class AffectPreferenceUpdate(BaseModel):
    expected_revision: int = Field(ge=0)
    expression_enabled: bool
    expression_intensity: str = Field(pattern="^(off|subtle|balanced)$")


class AffectCorrectionRequest(BaseModel):
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=2, max_length=500)
