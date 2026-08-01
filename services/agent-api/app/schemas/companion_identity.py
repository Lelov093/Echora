"""Companion companion identity / persona / contract schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class CompanionIdentityProfileRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    display_name: str
    identity_summary: str = ""
    origin_story: str | None = None
    self_continuity_summary: str | None = None
    core_traits_json: list[Any] = Field(default_factory=list)
    identity_labels_json: list[Any] = Field(default_factory=list)
    voice_style_hint: str | None = None
    avatar_style_hint: str | None = None
    profile_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanionPersonaProfileRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    persona_summary: str = ""
    communication_style_summary: str | None = None
    tone_descriptors_json: list[Any] = Field(default_factory=list)
    core_values_json: list[Any] = Field(default_factory=list)
    response_preferences_json: dict[str, Any] = Field(default_factory=dict)
    persona_lock_level: str
    drift_guard_level: str
    presence_style: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanionRelationshipContractRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    relationship_role: str
    contract_status: str
    contract_summary: str = ""
    collaboration_style_summary: str | None = None
    support_scope_json: list[Any] = Field(default_factory=list)
    shared_memory_policy: str
    cross_companion_disclosure_policy: str
    contract_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanionBoundaryProfileRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    boundary_json: dict[str, Any] = Field(default_factory=dict)
    private_memory_default: str
    shared_memory_default: str
    global_memory_read_scope: str
    cross_companion_read_policy: str
    review_required_private_to_shared: bool = True
    review_required_shared_to_private: bool = True
    review_required_cross_companion_share: bool = True
    presence_interrupt_policy: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanionVisibilityPolicyRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    memory_visibility_policy: str
    user_global_memory_scope: str
    relationship_memory_scope: str
    allow_low_risk_summary_read: bool = True
    allow_authorized_global_read: bool = True
    allow_sensitive_global_read: bool = False
    allow_other_companion_private_read: bool = False
    visibility_rules_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanionLifecycleEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    event_type: str
    event_source: str
    title: str | None = None
    detail: str | None = None
    previous_state_json: dict[str, Any] = Field(default_factory=dict)
    new_state_json: dict[str, Any] = Field(default_factory=dict)
    review_required: bool = False
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanionIdentityProfileUpsert(BaseModel):
    display_name: str
    identity_summary: str = ""
    origin_story: str | None = None
    self_continuity_summary: str | None = None
    core_traits_json: list[Any] = Field(default_factory=list)
    identity_labels_json: list[Any] = Field(default_factory=list)
    voice_style_hint: str | None = None
    avatar_style_hint: str | None = None
    profile_status: str = "active"


class CompanionPersonaProfileUpsert(BaseModel):
    persona_summary: str = ""
    communication_style_summary: str | None = None
    tone_descriptors_json: list[Any] = Field(default_factory=list)
    core_values_json: list[Any] = Field(default_factory=list)
    response_preferences_json: dict[str, Any] = Field(default_factory=dict)
    persona_lock_level: str = "guarded"
    drift_guard_level: str = "standard"
    presence_style: Literal["quiet", "balanced", "expressive"] = "balanced"


class CompanionRelationshipContractUpsert(BaseModel):
    relationship_role: str = "companion"
    contract_status: str = "active"
    contract_summary: str = ""
    collaboration_style_summary: str | None = None
    support_scope_json: list[Any] = Field(default_factory=list)
    shared_memory_policy: str = "candidate_review"
    cross_companion_disclosure_policy: str = "review_required"
    contract_json: dict[str, Any] = Field(default_factory=dict)


class CompanionBoundaryProfileUpsert(BaseModel):
    boundary_json: dict[str, Any] = Field(default_factory=dict)
    private_memory_default: str = "private_companion_only"
    shared_memory_default: str = "candidate_review"
    global_memory_read_scope: str = "low_risk_summary_only"
    cross_companion_read_policy: str = "blocked"
    review_required_private_to_shared: bool = True
    review_required_shared_to_private: bool = True
    review_required_cross_companion_share: bool = True
    presence_interrupt_policy: str = "respect_existing_boundary"


class CompanionVisibilityPolicyUpsert(BaseModel):
    memory_visibility_policy: str = "scoped_summary"
    user_global_memory_scope: str = "low_risk_summary_only"
    relationship_memory_scope: str = "contract_scoped"
    allow_low_risk_summary_read: bool = True
    allow_authorized_global_read: bool = True
    allow_sensitive_global_read: bool = False
    allow_other_companion_private_read: bool = False
    visibility_rules_json: dict[str, Any] = Field(default_factory=dict)


class CompanionLifecycleEventCreate(BaseModel):
    event_type: str
    event_source: str = "manual"
    title: str | None = None
    detail: str | None = None
    previous_state_json: dict[str, Any] = Field(default_factory=dict)
    new_state_json: dict[str, Any] = Field(default_factory=dict)
    review_required: bool = False


class CompanionProfileBundleRead(BaseModel):
    companion_id: uuid.UUID
    identity: CompanionIdentityProfileRead | None = None
    persona: CompanionPersonaProfileRead | None = None
    contract: CompanionRelationshipContractRead | None = None
    boundary: CompanionBoundaryProfileRead | None = None
    visibility: CompanionVisibilityPolicyRead | None = None


class CompanionCreateRequest(BaseModel):
    user_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=80)
    subtitle: str | None = Field(default=None, max_length=160)
    identity_prompt: str | None = Field(default=None, max_length=1000)
    base_personality: str | None = Field(default=None, max_length=1000)
    current_mode: Literal["project", "creative"] = "project"
    companion_environment: Literal["product", "test"] = "product"
    provenance: Literal["user_created", "seed", "smoke", "import", "system"] = "user_created"
    tone_profile: dict[str, Any] = Field(default_factory=dict)
    companion_profile: dict[str, Any] = Field(default_factory=dict)
    identity: CompanionIdentityProfileUpsert = Field(default_factory=lambda: CompanionIdentityProfileUpsert(display_name=""))
    persona: CompanionPersonaProfileUpsert = Field(default_factory=CompanionPersonaProfileUpsert)
    contract: CompanionRelationshipContractUpsert = Field(default_factory=CompanionRelationshipContractUpsert)
    boundary: CompanionBoundaryProfileUpsert = Field(default_factory=CompanionBoundaryProfileUpsert)
    visibility: CompanionVisibilityPolicyUpsert = Field(default_factory=CompanionVisibilityPolicyUpsert)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_scope(self):
        if self.provenance == "smoke" and self.companion_environment != "test":
            raise ValueError("smoke Companions must use the test environment")
        if not self.identity.display_name:
            self.identity.display_name = self.name
        return self


class CompanionOwnerSettingsPatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    identity_summary: str | None = Field(default=None, max_length=1000)
    origin_story: str | None = Field(default=None, max_length=2000)
    self_continuity_summary: str | None = Field(default=None, max_length=1200)
    core_traits_json: list[str] | None = Field(default=None, max_length=8)
    identity_labels_json: list[str] | None = Field(default=None, max_length=8)
    persona_summary: str | None = Field(default=None, max_length=1600)
    communication_style_summary: str | None = Field(default=None, max_length=1000)
    tone_descriptors_json: list[str] | None = Field(default=None, max_length=8)
    core_values_json: list[str] | None = Field(default=None, max_length=8)
    response_preferences_json: dict[str, str] | None = None
    presence_style: Literal["quiet", "balanced", "expressive"] | None = None
    relationship_role: Literal["companion", "collaborator", "mentor", "observer"] | None = None
    contract_summary: str | None = Field(default=None, max_length=1000)
    collaboration_style_summary: str | None = Field(default=None, max_length=1200)
    support_scope_json: list[str] | None = Field(default=None, max_length=8)
    user_preferred_name: str | None = Field(default=None, max_length=80)
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str | None = Field(default=None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    presence_interrupt_policy: Literal["respect_existing_boundary", "user_initiated_only"] | None = None
    expected_identity_updated_at: datetime
    expected_persona_updated_at: datetime
    expected_contract_updated_at: datetime
    expected_boundary_updated_at: datetime

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "core_traits_json",
        "identity_labels_json",
        "tone_descriptors_json",
        "core_values_json",
        "support_scope_json",
    )
    @classmethod
    def normalize_profile_lists(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = []
        for item in value:
            text = item.strip()
            if not text or text in normalized:
                continue
            if len(text) > 80:
                raise ValueError("profile list items must not exceed 80 characters")
            normalized.append(text)
        return normalized

    @field_validator("response_preferences_json")
    @classmethod
    def validate_response_preferences(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        allowed = {
            "response_length": {"concise", "balanced", "detailed"},
            "guidance_style": {"listen_first", "ask_then_advise", "direct_help"},
            "correction_style": {"gentle", "direct", "collaborative"},
            "humor_style": {"restrained", "natural", "playful"},
            "conflict_style": {"calm_clarify", "direct_discuss", "give_space"},
        }
        unknown = set(value) - set(allowed)
        if unknown:
            raise ValueError(f"unsupported response preference keys: {sorted(unknown)}")
        for key, item in value.items():
            if item not in allowed[key]:
                raise ValueError(f"unsupported response preference value for {key}")
        return value

    @model_validator(mode="after")
    def require_change(self):
        version_fields = {field for field in self.model_fields_set if field.startswith("expected_")}
        if self.model_fields_set == version_fields:
            raise ValueError("at least one owner setting must be provided")
        return self


class CompanionLifecycleTransitionRequest(BaseModel):
    expected_identity_updated_at: datetime
    confirm_preserve_history: bool
    confirm_boundaries_and_channels: bool = False
