from pydantic import BaseModel, ConfigDict


class MemorySelectionPolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    expected_revision: int


class MemorySelectionPolicyRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int
