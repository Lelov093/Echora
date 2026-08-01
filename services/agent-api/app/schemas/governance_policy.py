"""Product-facing governance automation contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


GovernanceMode = Literal["full_auto", "partial_auto", "manual"]
DomainOverride = Literal["inherit", "automatic", "manual"]


class GovernancePolicyUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: GovernanceMode
    domain_overrides: dict[str, DomainOverride] = Field(default_factory=dict)
    expected_revision: int = Field(ge=0)


class GovernancePolicyRollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
