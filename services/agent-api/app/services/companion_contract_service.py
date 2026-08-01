"""Companion companion contract and boundary service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import Companion, CompanionBoundaryProfile, CompanionRelationshipContract
from app.schemas.companion_identity import (
    CompanionBoundaryProfileRead,
    CompanionRelationshipContractRead,
)
from app.services.companion_roster_service import (
    _ensure_companion_profiles,
    _record_lifecycle_event,
    get_session,
)

_HIGH_IMPACT_CONTRACT_FIELDS = {
    "relationship_role",
    "shared_memory_policy",
    "cross_companion_disclosure_policy",
    "contract_json",
}
_HIGH_IMPACT_BOUNDARY_FIELDS = {
    "private_memory_default",
    "shared_memory_default",
    "global_memory_read_scope",
    "cross_companion_read_policy",
    "review_required_private_to_shared",
    "review_required_shared_to_private",
    "review_required_cross_companion_share",
    "boundary_json",
}


def get_contract(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        if _ensure_companion_profiles(s, companion):
            s.commit()
        contract = s.execute(
            select(CompanionRelationshipContract).where(
                CompanionRelationshipContract.companion_id == companion_id
            )
        ).scalar_one()
        return CompanionRelationshipContractRead.model_validate(contract).model_dump(mode="json")


def patch_contract(companion_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        _ensure_companion_profiles(s, companion)
        contract = s.execute(
            select(CompanionRelationshipContract).where(
                CompanionRelationshipContract.companion_id == companion_id
            )
        ).scalar_one()
        previous = CompanionRelationshipContractRead.model_validate(contract).model_dump(mode="json")
        touched = set()
        for field in [
            "relationship_role",
            "contract_status",
            "contract_summary",
            "collaboration_style_summary",
            "support_scope_json",
            "shared_memory_policy",
            "cross_companion_disclosure_policy",
            "contract_json",
        ]:
            if field in payload and payload[field] is not None:
                setattr(contract, field, payload[field])
                touched.add(field)
        contract.updated_at = datetime.now(timezone.utc)
        s.flush()
        review_required = bool(touched & _HIGH_IMPACT_CONTRACT_FIELDS)
        _record_lifecycle_event(
            s,
            companion_id=companion.id,
            user_id=companion.user_id,
            event_type="relationship_contract_initialized",
            event_source="api",
            title="Relationship contract updated",
            detail="Contract/boundary-impacting relationship changes recorded",
            previous_state_json=previous,
            new_state_json=CompanionRelationshipContractRead.model_validate(contract).model_dump(mode="json"),
            review_required=review_required,
            metadata={
                "implementation_origin": "companion_profile",
                "surface": "contract",
                "trace_required": review_required,
                "changed_fields": sorted(touched),
            },
        )
        s.commit()
        return CompanionRelationshipContractRead.model_validate(contract).model_dump(mode="json")


def get_boundary(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        if _ensure_companion_profiles(s, companion):
            s.commit()
        boundary = s.execute(
            select(CompanionBoundaryProfile).where(CompanionBoundaryProfile.companion_id == companion_id)
        ).scalar_one()
        return CompanionBoundaryProfileRead.model_validate(boundary).model_dump(mode="json")


def patch_boundary(companion_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if not companion or companion.deleted_at is not None:
            return None
        _ensure_companion_profiles(s, companion)
        boundary = s.execute(
            select(CompanionBoundaryProfile).where(CompanionBoundaryProfile.companion_id == companion_id)
        ).scalar_one()
        previous = CompanionBoundaryProfileRead.model_validate(boundary).model_dump(mode="json")
        touched = set()
        for field in [
            "boundary_json",
            "private_memory_default",
            "shared_memory_default",
            "global_memory_read_scope",
            "cross_companion_read_policy",
            "review_required_private_to_shared",
            "review_required_shared_to_private",
            "review_required_cross_companion_share",
            "presence_interrupt_policy",
        ]:
            if field in payload and payload[field] is not None:
                setattr(boundary, field, payload[field])
                touched.add(field)
        boundary.updated_at = datetime.now(timezone.utc)
        s.flush()
        review_required = bool(touched & _HIGH_IMPACT_BOUNDARY_FIELDS)
        _record_lifecycle_event(
            s,
            companion_id=companion.id,
            user_id=companion.user_id,
            event_type="boundary_profile_initialized",
            event_source="api",
            title="Boundary profile updated",
            detail="Boundary and visibility-impacting changes recorded",
            previous_state_json=previous,
            new_state_json=CompanionBoundaryProfileRead.model_validate(boundary).model_dump(mode="json"),
            review_required=review_required,
            metadata={
                "implementation_origin": "companion_profile",
                "surface": "boundary",
                "trace_required": review_required,
                "changed_fields": sorted(touched),
            },
        )
        s.commit()
        return CompanionBoundaryProfileRead.model_validate(boundary).model_dump(mode="json")
