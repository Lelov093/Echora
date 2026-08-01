"""Policy-safe read projections for the Companion-first frontend."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    ChannelMemoryCandidate,
    ChannelBinding,
    ChannelPresencePolicy,
    Companion,
    CompanionBoundaryProfile,
    CompanionIdentityProfile,
    CompanionVoiceProfile,
    CompanionVoiceSession,
    CompanionLifecycleEvent,
    CompanionPersonaGrowthCandidate,
    CompanionPersonaProfile,
    CompanionRelationshipContract,
    Conversation,
    ContinuitySnapshot,
    CrossCompanionMemoryEvent,
    CrossCompanionMemoryReview,
    GrowthCandidate,
    GrowthRecord,
    Memory,
    MemoryCandidate,
    MemoryLifecycleEvent,
    PresenceOpportunity,
    PrivateToSharedMemoryReview,
    RealtimeMemoryBuffer,
    RealtimeSharedMemoryCandidate,
    RelationshipExplanationEvent,
    RelationshipCandidate,
    RelationshipEvent,
    RelationshipState,
    CompanionChronicleSummary,
    SharedToPrivateMemoryReview,
    ScopedHardStopEvent,
)
from app.services.companion_roster_service import get_session
from app.services import presence_service


PRIVATE_MEMORY_SCOPES = {"legacy_private", "private_companion", "relationship"}
VISIBLE_MEMORY_STATES = {"active", "archived", "consolidated"}
PENDING_REVIEW_STATUSES = {"pending", "pending_review", "candidate"}


def _one(s: Session, model: type, companion_id: uuid.UUID):
    return s.execute(select(model).where(model.companion_id == companion_id)).scalars().first()


def _companion_or_none(s: Session, companion_id: uuid.UUID) -> Companion | None:
    companion = s.get(Companion, companion_id)
    return companion if companion and companion.deleted_at is None else None


def _iso_text(value: str | None, fallback: str) -> str:
    value = (value or "").strip()
    return value or fallback


def _workspace_continuity(
    continuity: ContinuitySnapshot | None, conversation: Conversation | None,
) -> dict[str, Any] | None:
    if continuity:
        return {
            "conversation_id": str(continuity.conversation_id) if continuity.conversation_id else None,
            "current_topic": continuity.current_topic, "current_goal": continuity.current_goal,
            "current_phase": continuity.current_phase, "last_assistant_summary": continuity.last_assistant_summary,
            "suggested_next_steps": list(continuity.suggested_next_steps or []), "updated_at": continuity.updated_at,
        }
    if not conversation:
        return None
    first_meeting = (conversation.continuity_state or {}).get("origin") == "companion_creation"
    return {
        "conversation_id": str(conversation.id),
        "current_topic": conversation.current_topic, "current_goal": conversation.current_goal,
        "current_phase": "first_meeting" if first_meeting else None,
        "last_assistant_summary": conversation.summary,
        "suggested_next_steps": ["从第一次相识开始"] if first_meeting else [],
        "updated_at": conversation.updated_at,
    }


def get_workspace(companion_id: uuid.UUID) -> dict[str, Any] | None:
    with get_session() as s:
        companion = _companion_or_none(s, companion_id)
        if not companion:
            return None
        identity = _one(s, CompanionIdentityProfile, companion_id)
        persona = _one(s, CompanionPersonaProfile, companion_id)
        contract = _one(s, CompanionRelationshipContract, companion_id)
        boundary = _one(s, CompanionBoundaryProfile, companion_id)
        continuity = s.execute(
            select(ContinuitySnapshot).where(
                ContinuitySnapshot.companion_id == companion_id,
                ContinuitySnapshot.deleted_at.is_(None),
            ).order_by(ContinuitySnapshot.updated_at.desc()).limit(1)
        ).scalar_one_or_none()
        conversation = None if continuity else s.execute(
            select(Conversation).where(
                Conversation.companion_id == companion_id,
                Conversation.status == "active",
                Conversation.deleted_at.is_(None),
            ).order_by(Conversation.updated_at.desc()).limit(1)
        ).scalar_one_or_none()
        relationship = _one(s, RelationshipState, companion_id)
        memories = list(s.execute(
            select(Memory).where(
                Memory.owner_companion_id == companion_id,
                Memory.companion_id == companion_id,
                Memory.deleted_at.is_(None),
                Memory.memory_scope_type.in_(PRIVATE_MEMORY_SCOPES),
                Memory.state.in_(VISIBLE_MEMORY_STATES),
                Memory.visibility != "hidden",
                Memory.consent_status.notin_(["blocked", "revoked", "pending_review"]),
            ).order_by(Memory.updated_at.desc()).limit(6)
        ).scalars().all())
        now = datetime.now(timezone.utc)
        presence_candidates = list(s.execute(
            select(PresenceOpportunity).where(
                PresenceOpportunity.companion_id == companion_id,
                PresenceOpportunity.status == "queued",
                PresenceOpportunity.sensitivity < 0.8,
                or_(PresenceOpportunity.expires_at.is_(None), PresenceOpportunity.expires_at > now),
            ).order_by(PresenceOpportunity.priority.desc(), PresenceOpportunity.created_at.desc()).limit(12)
        ).scalars().all())
        presence = []
        for opportunity in presence_candidates:
            suppression = presence_service.evaluate_presence_suppression(
                companion.user_id, companion_id, opportunity.type, now=now
            )
            if suppression["decision"] != "eligible":
                continue
            presence.append(opportunity)
            if len(presence) == 3:
                break
        counts = _review_items(s, companion_id, include_items=False)["counts"]
        hard_stop = s.execute(select(ScopedHardStopEvent).where(
            ScopedHardStopEvent.user_id == companion.user_id,
            ScopedHardStopEvent.hard_stop_status == "active",
            ScopedHardStopEvent.released_at.is_(None),
            or_(
                ScopedHardStopEvent.hard_stop_scope == "all_realtime",
                (ScopedHardStopEvent.hard_stop_scope == "companion") & (ScopedHardStopEvent.companion_id == companion_id),
            ),
        ).order_by(ScopedHardStopEvent.created_at.desc()).limit(1)).scalar_one_or_none()
        bindings = list(s.execute(select(ChannelBinding).where(ChannelBinding.companion_id == companion_id)).scalars().all())
        channel_policies = list(s.execute(select(ChannelPresencePolicy).where(ChannelPresencePolicy.companion_id == companion_id)).scalars().all())
        voice_profile = s.execute(select(CompanionVoiceProfile).where(
            CompanionVoiceProfile.companion_id == companion_id,
            CompanionVoiceProfile.profile_status == "active",
        ).order_by(CompanionVoiceProfile.updated_at.desc()).limit(1)).scalar_one_or_none()
        voice_session = s.execute(select(CompanionVoiceSession).where(
            CompanionVoiceSession.speaker_companion_id == companion_id,
        ).order_by(CompanionVoiceSession.created_at.desc()).limit(1)).scalar_one_or_none()
        return {
            "companion": {
                "id": str(companion.id), "name": companion.name, "subtitle": companion.subtitle,
                "current_mode": companion.current_mode, "current_status": companion.current_status,
                "current_focus": companion.current_focus,
            },
            "identity": {
                "display_name": identity.display_name if identity else companion.name,
                "identity_summary": _iso_text(identity.identity_summary if identity else None, companion.identity_prompt or "长期陪伴中的赛博伙伴"),
                "core_traits": list(identity.core_traits_json or []) if identity else [],
                "persona_summary": _iso_text(persona.persona_summary if persona else None, companion.base_personality or "稳定且持续的伙伴人格"),
                "persona_lock_level": persona.persona_lock_level if persona else "guarded",
                "relationship_role": contract.relationship_role if contract else "companion",
                "relationship_summary": _iso_text(contract.contract_summary if contract else None, "长期伙伴关系"),
            },
            "boundary": {
                "private_memory_default": boundary.private_memory_default if boundary else "private_companion_only",
                "shared_memory_default": boundary.shared_memory_default if boundary else "candidate_review",
                "cross_companion_read_policy": boundary.cross_companion_read_policy if boundary else "blocked",
                "private_to_shared_review_required": boundary.review_required_private_to_shared if boundary else True,
                "shared_to_private_review_required": boundary.review_required_shared_to_private if boundary else True,
                "cross_companion_review_required": boundary.review_required_cross_companion_share if boundary else True,
            },
            "continuity": _workspace_continuity(continuity, conversation),
            "relationship": None if not relationship else {
                "summary": relationship.summary,
                "familiarity": relationship.familiarity, "understanding": relationship.understanding,
                "collaboration": relationship.collaboration, "trust": relationship.trust,
                "emotional_closeness": relationship.emotional_closeness,
                "boundary_awareness": relationship.boundary_awareness, "continuity": relationship.continuity,
            },
            "recent_private_memories": [{
                "id": str(m.id), "type": m.type, "summary": _iso_text(m.summary, m.content), "updated_at": m.updated_at,
            } for m in memories],
            "presence_preview": [{
                "id": str(p.id), "type": p.type, "title": p.title, "message": p.message,
                "priority": p.priority, "recommended_surface": p.recommended_surface, "expires_at": p.expires_at,
            } for p in presence],
            "review_counts": counts,
            "governance": {
                "hard_stop_active": hard_stop is not None,
                "hard_stop_scope": hard_stop.hard_stop_scope if hard_stop else None,
                "revoked_channels": sum(1 for item in bindings if item.binding_status == "revoked" or item.revoked_at is not None),
                "active_channels": sum(1 for item in bindings if item.binding_status == "active" and item.revoked_at is None),
            },
            "channels": [{
                "id": str(item.id), "status": item.binding_status, "scope": item.binding_scope,
                "outbound_policy": item.outbound_policy, "memory_review_required": item.memory_write_requires_review,
            } for item in bindings],
            "channel_presence": [{
                "status": item.policy_status, "mode": item.presence_mode, "muted": item.channel_mute,
                "checkin_enabled": item.low_frequency_checkin_enabled, "quiet_hours": item.quiet_hours_enforced,
            } for item in channel_policies],
            "voice": {
                "profile_status": voice_profile.profile_status if voice_profile else None,
                "profile_name": voice_profile.voice_profile_name if voice_profile else None,
                "session_status": voice_session.session_status if voice_session else None,
                "transcript_retention": voice_session.transcript_retention_policy if voice_session else None,
                "memory_write_policy": voice_session.memory_write_policy if voice_session else None,
                "real_audio_enabled": bool((voice_session.voice_runtime_json or {}).get("real_audio_enabled")) if voice_session else False,
            },
        }


def get_chronicle(companion_id: uuid.UUID, limit: int, offset: int) -> dict[str, Any] | None:
    with get_session() as s:
        if not _companion_or_none(s, companion_id):
            return None
        items: list[dict[str, Any]] = []
        snapshots = s.execute(select(ContinuitySnapshot).where(
            ContinuitySnapshot.companion_id == companion_id, ContinuitySnapshot.deleted_at.is_(None)
        )).scalars().all()
        for row in snapshots:
            items.append(_chronicle(row.id, companion_id, "continuity", row.updated_at, "对话延续", row.last_assistant_summary or row.current_topic or "延续状态已更新", row.conversation_id, None, row.trace_run_id))
        for row in s.execute(select(GrowthRecord).where(GrowthRecord.companion_id == companion_id)).scalars():
            items.append(_chronicle(row.id, companion_id, "growth", row.created_at, "伙伴成长", row.content, row.id, row.status, None))
        explanations = list(s.execute(select(RelationshipExplanationEvent).where(
            RelationshipExplanationEvent.companion_id == companion_id,
            RelationshipExplanationEvent.deleted_at.is_(None), RelationshipExplanationEvent.user_visible.is_(True),
        )).scalars())
        event_ids = {row.relationship_event_id for row in explanations if row.relationship_event_id}
        relationship_events = {
            event.id: event for event in (
                s.execute(select(RelationshipEvent).where(RelationshipEvent.id.in_(event_ids))).scalars()
                if event_ids else []
            )
        }
        for row in explanations:
            event = relationship_events.get(row.relationship_event_id)
            items.append(_chronicle(
                row.id, companion_id,
                "relationship" if event else "relationship_pending",
                row.created_at,
                row.title or ("关系变化" if event else "待确认的关系理解"),
                row.explanation,
                row.relationship_event_id or row.id,
                event.operation if event else "pending_review",
                row.trace_run_id,
            ))
        for row in s.execute(select(PresenceOpportunity).where(
            PresenceOpportunity.companion_id == companion_id,
            PresenceOpportunity.sensitivity < 0.8,
        )).scalars():
            items.append(_chronicle(
                row.id, companion_id, "presence", row.created_at, row.title,
                row.message or row.meaningful_silence_reason or "伙伴在场感状态已更新",
                row.id, row.status, None,
            ))
        lifecycle_rows = list(s.execute(select(MemoryLifecycleEvent).where(MemoryLifecycleEvent.companion_id == companion_id)).scalars())
        lifecycle_memory_ids = {row.memory_id for row in lifecycle_rows}
        for row in lifecycle_rows:
            items.append(_chronicle(row.id, companion_id, "memory", row.created_at, row.title or "记忆变化", row.reason or row.event_type, row.memory_id, row.new_state, row.trace_run_id))
        committed_memories = s.execute(select(Memory).where(
            Memory.owner_companion_id == companion_id,
            Memory.companion_id == companion_id,
            Memory.deleted_at.is_(None),
            Memory.memory_scope_type.in_(PRIVATE_MEMORY_SCOPES),
            Memory.state.in_(VISIBLE_MEMORY_STATES),
            Memory.consent_status == "user_confirmed",
        )).scalars()
        for row in committed_memories:
            if row.id not in lifecycle_memory_ids:
                items.append(_chronicle(row.id, companion_id, "memory", row.created_at, "记忆已确认", row.summary or row.content, row.id, row.state, None))
        for row in s.execute(select(CompanionLifecycleEvent).where(CompanionLifecycleEvent.companion_id == companion_id)).scalars():
            items.append(_chronicle(row.id, companion_id, "companion", row.occurred_at or row.created_at, row.title or "伙伴状态变化", row.detail or row.event_type, row.id, "pending_review" if row.review_required else None, None))
        items.sort(key=lambda x: x["occurred_at"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        summaries = [_chronicle_summary(row) for row in s.execute(select(CompanionChronicleSummary).where(
            CompanionChronicleSummary.companion_id == companion_id,
        ).order_by(CompanionChronicleSummary.version.desc()).limit(20)).scalars()]
        return {"companion_id": str(companion_id), "items": items[offset:offset + limit], "total": len(items), "limit": limit, "offset": offset, "summaries": summaries}


def _chronicle(row_id, companion_id, kind, occurred_at, title, summary, source_id, review_status, trace_id):
    return {
        "id": str(row_id), "companion_id": str(companion_id), "kind": kind,
        "occurred_at": occurred_at, "title": title, "summary": summary,
        "source_id": str(source_id) if source_id else None, "review_status": review_status,
        "trace_id": str(trace_id) if trace_id else None,
    }


def _chronicle_summary(row: CompanionChronicleSummary) -> dict[str, Any]:
    return {
        "id": str(row.id), "version": row.version, "status": row.status,
        "title": row.title, "summary": row.summary, "highlights": row.highlights_json or [],
        "period_start": row.period_start, "period_end": row.period_end,
        "source_event_refs": row.source_event_refs or [],
        "invalidation_reason": row.invalidation_reason, "created_at": row.created_at,
    }


def get_review_inbox(companion_id: uuid.UUID, limit: int, offset: int, kind: str | None = None) -> dict[str, Any] | None:
    with get_session() as s:
        if not _companion_or_none(s, companion_id):
            return None
        result = _review_items(s, companion_id, include_items=True)
        result["items"].sort(key=lambda x: x["created_at"], reverse=True)
        if kind:
            result["items"] = [item for item in result["items"] if item["kind"] == kind]
        result.update({"companion_id": str(companion_id), "total": len(result["items"]), "limit": limit, "offset": offset})
        result["items"] = result["items"][offset:offset + limit]
        return result


def _review_items(s: Session, companion_id: uuid.UUID, *, include_items: bool) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    def add(rows, kind, title, summary, status="pending_review", risk=None, source=lambda row: None):
        rows = list(rows)
        if include_items:
            for row in rows:
                items.append({
                    "id": str(row.id), "companion_id": str(companion_id), "kind": kind,
                    "created_at": row.created_at, "title": title(row), "summary": _iso_text(summary(row), "等待你的确认"),
                    "status": status(row) if callable(status) else status,
                    "risk_level": risk(row) if callable(risk) else risk,
                    "source_id": str(source(row)) if source(row) else None,
                })
        counts[kind] = len(rows)

    counts: dict[str, int] = {}
    add(s.execute(select(MemoryCandidate).where(
        MemoryCandidate.companion_id == companion_id, MemoryCandidate.proposed_owner_companion_id == companion_id,
        MemoryCandidate.status == "pending",
    )).scalars(), "memory", lambda _: "待确认记忆", lambda r: r.suggested_summary or r.content, status=lambda r: r.status, risk=lambda r: "high" if r.sensitivity_risk >= 0.8 else None)
    add(s.execute(select(GrowthCandidate).where(GrowthCandidate.companion_id == companion_id, GrowthCandidate.status == "candidate")).scalars(), "growth", lambda _: "待确认成长", lambda r: r.content, status=lambda r: r.status, risk=lambda r: r.risk_level)
    add(s.execute(select(RelationshipCandidate).where(
        RelationshipCandidate.companion_id == companion_id,
        RelationshipCandidate.status == "pending",
    )).scalars(), "relationship", lambda _: "待确认关系理解", lambda r: r.summary, status=lambda r: r.status, risk=lambda r: r.risk_level)
    add(s.execute(select(CompanionPersonaGrowthCandidate).where(
        CompanionPersonaGrowthCandidate.companion_id == companion_id,
        CompanionPersonaGrowthCandidate.candidate_status == "pending_review",
        CompanionPersonaGrowthCandidate.requires_user_review.is_(True),
    )).scalars(), "persona_growth", lambda _: "人格成长建议", lambda r: r.growth_summary, status=lambda r: r.candidate_status, risk=lambda r: r.impact_level)
    add(s.execute(select(PrivateToSharedMemoryReview).where(
        PrivateToSharedMemoryReview.source_companion_id == companion_id, PrivateToSharedMemoryReview.decision == "pending",
    )).scalars(), "private_to_shared", lambda _: "私有记忆共享申请", lambda r: r.review_reason, source=lambda r: r.memory_id)
    add(s.execute(select(SharedToPrivateMemoryReview).where(
        SharedToPrivateMemoryReview.target_companion_id == companion_id, SharedToPrivateMemoryReview.decision == "pending",
    )).scalars(), "shared_to_private", lambda _: "共享记忆收录申请", lambda r: r.review_reason, source=lambda r: r.shared_memory_id)
    cross = s.execute(select(CrossCompanionMemoryReview, CrossCompanionMemoryEvent).join(
        CrossCompanionMemoryEvent, CrossCompanionMemoryReview.cross_companion_memory_event_id == CrossCompanionMemoryEvent.id
    ).where(CrossCompanionMemoryReview.decision == "pending", or_(
        CrossCompanionMemoryEvent.source_companion_id == companion_id,
        CrossCompanionMemoryEvent.target_companion_id == companion_id,
    ))).all()
    cross_rows = []
    for review, event in cross:
        review._safe_event_reason = event.reason
        cross_rows.append(review)
    add(cross_rows, "cross_companion", lambda _: "跨伙伴记忆申请", lambda r: r.review_reason or r._safe_event_reason, source=lambda r: r.cross_companion_memory_event_id)
    add(s.execute(select(ChannelMemoryCandidate).where(
        ChannelMemoryCandidate.companion_id == companion_id,
        ChannelMemoryCandidate.candidate_status == "pending_review",
        ChannelMemoryCandidate.requires_user_review.is_(True),
        ChannelMemoryCandidate.auto_commit_allowed.is_(False),
    )).scalars(), "channel", lambda _: "频道记忆候选", lambda r: r.candidate_summary, status=lambda r: r.candidate_status, source=lambda r: r.channel_binding_id)
    realtime = s.execute(select(RealtimeSharedMemoryCandidate).join(
        RealtimeMemoryBuffer, RealtimeSharedMemoryCandidate.source_buffer_id == RealtimeMemoryBuffer.id
    ).where(
        RealtimeMemoryBuffer.owner_companion_id == companion_id,
        RealtimeSharedMemoryCandidate.candidate_status == "pending_review",
        RealtimeSharedMemoryCandidate.requires_user_review.is_(True),
        RealtimeSharedMemoryCandidate.auto_commit_shared_memory.is_(False),
    )).scalars()
    add(realtime, "realtime_shared", lambda _: "实时共享记忆候选", lambda r: r.candidate_summary, status=lambda r: r.candidate_status, source=lambda r: r.source_buffer_id)
    counts["total"] = sum(counts.values())
    return {"items": items, "counts": counts}
