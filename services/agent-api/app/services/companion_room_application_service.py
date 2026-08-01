"""Product application orchestration over Co-Presence and Shared Scene truth."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    CompanionRoomMembershipEvent,
    Conversation,
    CoPresenceParticipant,
    CoPresenceSession,
    CoPresenceSessionPolicy,
    ParticipantMemoryPermission,
    SharedScene,
)
from app.services import (
    companion_roster_service,
    co_presence_service,
    conversation_service,
    participant_awareness_service,
    shared_scene_service,
)


logger = logging.getLogger(__name__)


class CompanionRoomError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def create_companion_room(payload: dict[str, Any]) -> dict[str, Any]:
    primary_id = _uuid(payload["primary_companion_id"])
    primary = _active_product_companion(primary_id)
    owner_id = _uuid(primary["user_id"])
    participants = payload.get("participants") or []
    _validate_participants(owner_id, primary_id, participants)

    session = co_presence_service.create_co_presence_session(
        owner_id,
        {
            "primary_companion_id": str(primary_id),
            "session_title": payload["title"],
            "session_summary": payload.get("summary"),
            "session_source": "companion_home",
            "visibility_scope": "role_summary",
            "entry_reason": "user_created_room",
            "allow_autonomous_companion_interaction": False,
            "cross_companion_private_read_policy": "deny",
            "private_to_shared_policy": "review_required",
            "shared_to_private_policy": "review_required",
        },
    )
    if not session:
        raise CompanionRoomError("COMPANION_ROOM_CREATE_FAILED", "无法建立聊天室的 Co-Presence 会话。")

    session_id = _uuid(session["id"])
    scene = None
    conversation = None
    try:
        for item in participants:
            role = item.get("role", "active_companion")
            session = co_presence_service.add_participant_to_session(
                session_id,
                {
                    "participant_type": "companion",
                    "participant_companion_id": str(item["companion_id"]),
                    "participant_role": role,
                    "can_speak": role == "active_companion",
                    "can_delegate": False,
                    "visibility_scope": "role_summary",
                    "memory_permission": {
                        "memory_participation_override": "none" if role == "observing_companion" else "shared_candidate_allowed",
                        "allow_cross_companion_private_read": False,
                        "review_required": True,
                    },
                },
            )
            if not session:
                raise CompanionRoomError("COMPANION_ROOM_PARTICIPANT_FAILED", "无法加入选定的伙伴。")

        scene = shared_scene_service.create_shared_scene(
            owner_id,
            {
                "co_presence_session_id": str(session_id),
                "owner_companion_id": str(primary_id),
                "scene_title": payload["title"],
                "scene_summary": payload.get("summary"),
                "scene_type": "conversation",
                "scene_status": "active",
                "source_type": "co_presence_session",
                "visibility_scope": "role_summary",
                "visibility_policy_json": {
                    "cross_companion_memory": "review_required",
                    "observer_auto_speaker": False,
                },
                "metadata": {"surface": "companion_home", "product_kind": "companion_room"},
            },
        )
        if not scene:
            raise CompanionRoomError("COMPANION_ROOM_SCENE_FAILED", "无法建立聊天室的共享场景。")
        conversation = conversation_service.create_conversation(
            {
                "user_id": owner_id,
                "companion_id": primary_id,
                "co_presence_session_id": session_id,
                "shared_scene_id": _uuid(scene["id"]),
                "title": payload["title"],
                "mode_key": "daily",
                "retention_mode": "standard",
                "cross_session_memory_enabled": False,
                "metadata_": {
                    "product_kind": "companion_room",
                    "runtime_status": "multi_companion_active",
                    "multi_companion_execution": True,
                },
            }
        )
        _bootstrap_membership_events(session_id)
        return {
            "session": get_companion_room(session_id),
            "scene": scene,
            "conversation": conversation_service._conv_dict(conversation),
        }
    except Exception:
        # A partially assembled room must never remain active or imply that every invite succeeded.
        if conversation is not None:
            try:
                conversation_service.set_conversation_archived(
                    conversation.id, primary_id, True, include_companion_room=True
                )
            except Exception:
                logger.exception("Failed to archive partial Room Conversation %s", conversation.id)
        if scene is not None:
            try:
                shared_scene_service.patch_shared_scene(
                    _uuid(scene["id"]),
                    {"scene_status": "closed", "closed_at": datetime.now(timezone.utc).isoformat()},
                )
            except Exception:
                logger.exception("Failed to close partial Room Shared Scene %s", scene.get("id"))
        try:
            co_presence_service.end_co_presence_session(session_id)
        except Exception:
            # Preserve the original creation error while retaining operational evidence.
            logger.exception("Failed to compensate partially created companion room %s", session_id)
        raise


def update_companion_room(session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    current = co_presence_service.get_co_presence_session_bundle(session_id)
    if not current:
        raise CompanionRoomError("COMPANION_ROOM_NOT_FOUND", "聊天室不存在或已不可访问。")
    if current.get("session_status") != "active":
        raise CompanionRoomError("COMPANION_ROOM_NOT_ACTIVE", "已结束的聊天室不能继续修改。")
    _active_product_companion(_uuid(current["primary_companion_id"]))
    previous = {"session_title": current["session_title"], "session_summary": current.get("session_summary")}
    session_patch = {}
    if "title" in payload:
        session_patch["session_title"] = payload["title"]
    if "summary" in payload:
        session_patch["session_summary"] = payload["summary"]
    updated = co_presence_service.patch_co_presence_session(session_id, session_patch)
    if not updated:
        raise CompanionRoomError("COMPANION_ROOM_UPDATE_FAILED", "聊天室信息未能保存。")
    try:
        for scene_id in current.get("shared_scene_ids") or []:
            scene_patch = {}
            if "title" in payload:
                scene_patch["scene_title"] = payload["title"]
            if "summary" in payload:
                scene_patch["scene_summary"] = payload["summary"]
            if scene_patch and not shared_scene_service.patch_shared_scene(_uuid(scene_id), scene_patch):
                raise CompanionRoomError("COMPANION_ROOM_SCENE_UPDATE_FAILED", "共享场景未能同步更新。")
        if "title" in payload:
            with co_presence_service.get_session() as s:
                conversation = s.execute(
                    select(Conversation).where(
                        Conversation.co_presence_session_id == session_id,
                        Conversation.deleted_at.is_(None),
                    ).limit(1)
                ).scalar_one_or_none()
            if conversation is not None and not conversation_service.update_conversation(
                conversation.id,
                _uuid(current["primary_companion_id"]),
                {"title": payload["title"]},
                include_companion_room=True,
            ):
                raise CompanionRoomError("COMPANION_ROOM_CONVERSATION_UPDATE_FAILED", "聊天室 Conversation 未能同步更新。")
    except Exception:
        try:
            co_presence_service.patch_co_presence_session(session_id, previous)
            if "title" in payload and 'conversation' in locals() and conversation is not None:
                conversation_service.update_conversation(
                    conversation.id,
                    _uuid(current["primary_companion_id"]),
                    {"title": previous["session_title"]},
                    include_companion_room=True,
                )
        except Exception:
            # Do not mask the original scene-sync failure with a compensation failure.
            logger.exception("Failed to restore companion room %s after scene sync failure", session_id)
        raise
    return {"session": updated, "shared_scene_ids": current.get("shared_scene_ids") or []}


def archive_companion_room(session_id: uuid.UUID) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with co_presence_service.get_session() as s:
        room = _locked_product_room(s, session_id)
        _require_active_room(room)
        _active_or_archived_product_companion(room.primary_companion_id)
        room.session_status = "ended"
        room.ended_at = now
        participants = list(s.execute(select(CoPresenceParticipant).where(
            CoPresenceParticipant.co_presence_session_id == room.id
        ).with_for_update()).scalars().all())
        for participant in participants:
            if participant.join_status != "active":
                continue
            from_status = participant.join_status
            participant.join_status = "inactive" if participant.participant_type == "companion" else "left"
            participant.can_speak = False
            participant.left_at = now
            participant.membership_revision += 1
            if participant.participant_type == "companion":
                room.roster_revision += 1
                _append_membership_event(
                    s, room, participant, "inactivated", from_status=from_status,
                    to_status="inactive", from_role=participant.participant_role,
                    to_role=participant.participant_role, reason="room_archived", now=now,
                )
        _sync_room_awareness(s, room, participants)
        for scene in s.execute(select(SharedScene).where(SharedScene.co_presence_session_id == room.id)).scalars():
            scene.scene_status = "closed"; scene.closed_at = now
        for conversation in s.execute(select(Conversation).where(Conversation.co_presence_session_id == room.id)).scalars():
            conversation.status = "archived"
        policy = s.execute(select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == room.id)).scalar_one()
        co_presence_service._refresh_session_summaries(s, room, policy)
        s.commit()
    return {"session": get_companion_room(session_id), "scene_close_failures": []}


def get_companion_room(session_id: uuid.UUID) -> dict[str, Any]:
    bundle = co_presence_service.get_co_presence_session_bundle(session_id)
    if not bundle or bundle.get("session_source") != "companion_home":
        raise CompanionRoomError("COMPANION_ROOM_NOT_FOUND", "聊天室不存在或已不可访问。")
    with co_presence_service.get_session() as s:
        conversation = s.execute(
            select(Conversation)
            .where(Conversation.co_presence_session_id == session_id, Conversation.deleted_at.is_(None))
            .order_by(Conversation.created_at.asc())
            .limit(1)
        ).scalar_one_or_none()
        events = list(
            s.execute(
                select(CompanionRoomMembershipEvent)
                .where(CompanionRoomMembershipEvent.co_presence_session_id == session_id)
                .order_by(CompanionRoomMembershipEvent.roster_revision.desc(), CompanionRoomMembershipEvent.occurred_at.desc())
                .limit(50)
            ).scalars().all()
        )
    from app.services import companion_room_channel_service

    return {
        **bundle,
        "conversation": conversation_service._conv_dict(conversation) if conversation else None,
        "membership_events": [_membership_event_to_dict(item) for item in events],
        "discord_channel": companion_room_channel_service.get_room_channel_projection(session_id),
        "runtime_status": "multi_companion_active",
        "composer_enabled": bundle.get("session_status") == "active" and bool(conversation and conversation.status == "active"),
    }


def invite_room_member(session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    companion_id = _uuid(payload["companion_id"])
    now = datetime.now(timezone.utc)
    with co_presence_service.get_session() as s:
        room = _locked_product_room(s, session_id)
        _require_active_room(room)
        _require_roster_revision(room, int(payload["expected_roster_revision"]))
        companion = _active_product_companion(companion_id)
        if _uuid(companion["user_id"]) != room.user_id:
            raise CompanionRoomError("COMPANION_ROOM_SCOPE_MISMATCH", "所有伙伴必须属于同一位关系创建者。")
        existing = s.execute(
            select(CoPresenceParticipant).where(
                CoPresenceParticipant.co_presence_session_id == room.id,
                CoPresenceParticipant.participant_companion_id == companion_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            code = "COMPANION_ROOM_MEMBER_REVOKED" if existing.join_status == "revoked" else "COMPANION_ROOM_MEMBER_EXISTS"
            raise CompanionRoomError(code, "该伙伴已有房间成员历史；请使用成员状态操作。")
        policy = s.execute(
            select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == room.id)
        ).scalar_one()
        observer = payload.get("mode") == "observer"
        participant = CoPresenceParticipant(
            user_id=room.user_id,
            co_presence_session_id=room.id,
            participant_type="companion",
            participant_role="observing_companion" if observer else "active_companion",
            participant_companion_id=companion_id,
            join_status="active",
            visibility_scope="role_summary",
            can_speak=not observer,
            can_delegate=False,
            membership_revision=1,
            policy_override_json={},
            metadata_={"implementation_origin": "companion_room_binding", "joined_context_from": now.isoformat()},
        )
        s.add(participant)
        s.flush()
        participant_awareness_service.ensure_self_awareness_state(s, co_presence_session=room, participant=participant)
        participant_awareness_service.ensure_participant_memory_permission(
            s,
            co_presence_session=room,
            participant=participant,
            policy=policy,
            overrides={
                "memory_participation_override": "none" if observer else "shared_candidate_allowed",
                "allow_cross_companion_private_read": False,
                "review_required": True,
            },
        )
        participant_awareness_service.sync_participant_awareness_links(s, co_presence_session=room, participant=participant)
        room.roster_revision += 1
        _append_membership_event(
            s, room, participant, "invited", from_status=None, to_status="active",
            from_role=None, to_role=participant.participant_role, reason=payload.get("reason"), now=now,
        )
        co_presence_service._refresh_session_summaries(s, room, policy)
        _pause_conflicting_channel_binding(s, room, "room_roster_changed")
        s.commit()
    return get_companion_room(session_id)


def create_successor_room(session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a same-active-roster Room with an explicitly reviewed bounded capsule."""
    with co_presence_service.get_session() as s:
        source = _locked_product_room(s, session_id)
        _require_active_room(source)
        _require_roster_revision(source, int(payload["expected_roster_revision"]))
        participants = list(s.execute(select(CoPresenceParticipant).where(
            CoPresenceParticipant.co_presence_session_id == source.id,
            CoPresenceParticipant.participant_type == "companion",
            CoPresenceParticipant.join_status == "active",
        )).scalars().all())
        primary_id = source.primary_companion_id
        primary_participant = next(
            (item for item in participants if item.participant_companion_id == primary_id), None
        )
        if (
            primary_participant is None or not primary_participant.can_speak
            or primary_participant.participant_role == "observing_companion"
        ):
            raise CompanionRoomError(
                "COMPANION_ROOM_SUCCESSOR_PRIMARY_NOT_SPEAKER",
                "请先将主伙伴恢复为允许发言，再按当前成员开启下一段。",
            )
        roster = [{
            "companion_id": str(item.participant_companion_id),
            "role": "observing_companion" if item.participant_role == "observing_companion" or not item.can_speak else "active_companion",
        } for item in participants if item.participant_companion_id != primary_id]
        source_revision = source.roster_revision
        owner_id = source.user_id

    created = create_companion_room({
        "primary_companion_id": str(primary_id),
        "title": payload["title"],
        "summary": payload.get("summary"),
        "participants": roster,
    })
    successor = created["session"]
    successor_id = _uuid(successor["id"])
    now = datetime.now(timezone.utc)
    with co_presence_service.get_session() as s:
        conversation = s.execute(select(Conversation).where(
            Conversation.co_presence_session_id == successor_id,
            Conversation.deleted_at.is_(None),
        ).limit(1)).scalar_one()
        capsule = {
            "contract_version": "room-continuation.v1",
            "source_room_id": str(session_id),
            "source_roster_revision": source_revision,
            "owner_id": str(owner_id),
            "review_status": "user_confirmed",
            "reviewed_at": now.isoformat(),
            "summary": payload["continuation_summary"],
            "raw_message_history_included": False,
            "cross_companion_private_memory_included": False,
        }
        conversation.continuity_state = {**(conversation.continuity_state or {}), "room_continuation_capsule": capsule}
        conversation.metadata_ = {
            **(conversation.metadata_ or {}),
            "successor_of_room_id": str(session_id),
            "continuation_capsule_reviewed": True,
        }
        s.commit()
    return {**created, "continuation_capsule": capsule}


def transition_room_member(session_id: uuid.UUID, participant_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    action = str(payload["action"])
    with co_presence_service.get_session() as s:
        room = _locked_product_room(s, session_id)
        _require_active_room(room)
        _require_roster_revision(room, int(payload["expected_roster_revision"]))
        participant = s.execute(
            select(CoPresenceParticipant).where(
                CoPresenceParticipant.id == participant_id,
                CoPresenceParticipant.co_presence_session_id == room.id,
            ).with_for_update()
        ).scalar_one_or_none()
        if participant is None or participant.participant_type != "companion" or participant.participant_companion_id is None:
            raise CompanionRoomError("COMPANION_ROOM_MEMBER_NOT_FOUND", "未找到对应的伙伴成员。")
        if participant.membership_revision != int(payload["expected_participant_revision"]):
            raise CompanionRoomError(
                "COMPANION_ROOM_MEMBER_REVISION_CONFLICT", "成员状态已经变化，请刷新后重试。",
                {"current_revision": participant.membership_revision},
            )
        if participant.join_status == "revoked":
            raise CompanionRoomError("COMPANION_ROOM_MEMBER_REVOKED", "已撤销成员不能重新激活或改写历史。")
        if participant.participant_companion_id == room.primary_companion_id and action in {"inactivate", "revoke"}:
            raise CompanionRoomError("COMPANION_ROOM_PRIMARY_MEMBER_LOCKED", "主伙伴不能被踢出或停用；如需结束关系请归档聊天室。")
        from_status = participant.join_status
        from_role = participant.participant_role
        event_type = _apply_member_action(participant, action, now)
        if participant.participant_companion_id == room.primary_companion_id and action == "speaker":
            participant.participant_role = "primary_companion"
        participant.membership_revision += 1
        participant.updated_at = now
        room.roster_revision += 1
        policy = s.execute(
            select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == room.id)
        ).scalar_one()
        permission = s.execute(
            select(ParticipantMemoryPermission).where(ParticipantMemoryPermission.participant_id == participant.id)
        ).scalar_one_or_none()
        if permission is not None:
            permission.memory_participation_override = (
                "shared_candidate_allowed"
                if participant.join_status == "active" and participant.can_speak
                else "none"
            )
            permission.allow_cross_companion_private_read = False
            permission.review_required = True
        participant_awareness_service.ensure_self_awareness_state(
            s, co_presence_session=room, participant=participant,
            overrides={
                "awareness_status": participant_awareness_service.awareness_status_for_join_status(
                    participant.join_status
                )
            },
        )
        participant_awareness_service.sync_participant_awareness_links(
            s, co_presence_session=room, participant=participant, updated_by_source="user"
        )
        _append_membership_event(
            s, room, participant, event_type, from_status=from_status, to_status=participant.join_status,
            from_role=from_role, to_role=participant.participant_role, reason=payload.get("reason"), now=now,
        )
        co_presence_service._refresh_session_summaries(s, room, policy)
        _pause_conflicting_channel_binding(s, room, "room_roster_changed")
        s.commit()
    return get_companion_room(session_id)


def restore_companion_room(session_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    with co_presence_service.get_session() as s:
        room = _locked_product_room(s, session_id)
        if room.session_status != "ended":
            raise CompanionRoomError("COMPANION_ROOM_NOT_ARCHIVED", "只有已归档聊天室可以恢复。")
        _require_roster_revision(room, int(payload["expected_roster_revision"]))
        _active_or_archived_product_companion(room.primary_companion_id)
        participants = list(s.execute(
            select(CoPresenceParticipant).where(CoPresenceParticipant.co_presence_session_id == room.id).with_for_update()
        ).scalars().all())
        restorable = [item for item in participants if item.join_status != "revoked"]
        if not any(item.participant_companion_id == room.primary_companion_id for item in restorable):
            raise CompanionRoomError("COMPANION_ROOM_RESTORE_PRIMARY_MISSING", "主伙伴已不可恢复，聊天室保持归档。")
        room.session_status = "active"
        room.ended_at = None
        for participant in restorable:
            from_status = participant.join_status
            participant.join_status = "active"
            participant.left_at = None
            participant.rejoined_at = now
            participant.membership_revision += 1
            if participant.participant_type == "companion":
                participant.can_speak = participant.participant_role in {"primary_companion", "active_companion"} and participant.muted_at is None
                room.roster_revision += 1
                _append_membership_event(
                    s, room, participant, "room_restored", from_status=from_status, to_status="active",
                    from_role=participant.participant_role, to_role=participant.participant_role,
                    reason=payload.get("reason"), now=now,
                )
        _sync_room_awareness(s, room, restorable)
        for scene in s.execute(select(SharedScene).where(SharedScene.co_presence_session_id == room.id)).scalars():
            scene.scene_status = "active"
            scene.closed_at = None
        for conversation in s.execute(select(Conversation).where(Conversation.co_presence_session_id == room.id)).scalars():
            conversation.status = "active"
        policy = s.execute(select(CoPresenceSessionPolicy).where(CoPresenceSessionPolicy.co_presence_session_id == room.id)).scalar_one()
        co_presence_service._refresh_session_summaries(s, room, policy)
        s.commit()
    return get_companion_room(session_id)


def _locked_product_room(s, session_id: uuid.UUID) -> CoPresenceSession:
    room = s.execute(select(CoPresenceSession).where(CoPresenceSession.id == session_id).with_for_update()).scalar_one_or_none()
    if room is None or room.session_source != "companion_home":
        raise CompanionRoomError("COMPANION_ROOM_NOT_FOUND", "聊天室不存在或已不可访问。")
    return room


def _require_active_room(room: CoPresenceSession) -> None:
    if room.session_status != "active":
        raise CompanionRoomError("COMPANION_ROOM_NOT_ACTIVE", "已归档聊天室不能修改成员。")


def _require_roster_revision(room: CoPresenceSession, expected: int) -> None:
    if room.roster_revision != expected:
        raise CompanionRoomError(
            "COMPANION_ROOM_REVISION_CONFLICT", "聊天室成员已经变化，请刷新后重试。",
            {"current_revision": room.roster_revision},
        )


def _apply_member_action(participant: CoPresenceParticipant, action: str, now: datetime) -> str:
    if action == "speaker":
        participant.join_status = "active"; participant.participant_role = "active_companion"
        participant.can_speak = True; participant.left_at = None; participant.muted_at = None
        return "speaker"
    if action == "observer":
        participant.join_status = "active"; participant.participant_role = "observing_companion"
        participant.can_speak = False; participant.left_at = None; participant.muted_at = None
        return "observer"
    if action == "mute":
        participant.join_status = "active"; participant.can_speak = False; participant.muted_at = now
        return "muted"
    if action == "inactivate":
        participant.join_status = "inactive"; participant.can_speak = False; participant.left_at = now
        return "inactivated"
    if action == "reactivate":
        participant.join_status = "active"; participant.left_at = None; participant.rejoined_at = now
        participant.can_speak = participant.participant_role in {"primary_companion", "active_companion"} and participant.muted_at is None
        metadata = dict(participant.metadata_ or {}); metadata["joined_context_from"] = now.isoformat(); participant.metadata_ = metadata
        return "reactivated"
    if action == "revoke":
        participant.join_status = "revoked"; participant.can_speak = False
        participant.left_at = now; participant.revoked_at = now
        return "revoked"
    raise CompanionRoomError("COMPANION_ROOM_MEMBER_ACTION_INVALID", "不支持的成员操作。")


def _sync_room_awareness(s, room: CoPresenceSession, participants: list[CoPresenceParticipant]) -> None:
    for participant in participants:
        participant_awareness_service.ensure_self_awareness_state(
            s,
            co_presence_session=room,
            participant=participant,
            overrides={
                "awareness_status": participant_awareness_service.awareness_status_for_join_status(
                    participant.join_status
                )
            },
        )
    for participant in participants:
        participant_awareness_service.sync_participant_awareness_links(
            s,
            co_presence_session=room,
            participant=participant,
            updated_by_source="user",
        )


def _append_membership_event(s, room, participant, event_type: str, *, from_status, to_status, from_role, to_role, reason, now) -> None:
    s.add(CompanionRoomMembershipEvent(
        user_id=room.user_id,
        co_presence_session_id=room.id,
        participant_id=participant.id,
        companion_id=participant.participant_companion_id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        from_role=from_role,
        to_role=to_role,
        roster_revision=room.roster_revision,
        participant_revision=participant.membership_revision,
        reason=reason,
        evidence_json={"source": "web", "raw_history_shared": False},
        occurred_at=now,
        metadata_={"implementation_origin": "companion_room_binding"},
    ))


def _bootstrap_membership_events(session_id: uuid.UUID) -> None:
    now = datetime.now(timezone.utc)
    with co_presence_service.get_session() as s:
        room = s.get(CoPresenceSession, session_id)
        if room is None:
            return
        existing = s.execute(select(CompanionRoomMembershipEvent.id).where(CompanionRoomMembershipEvent.co_presence_session_id == room.id).limit(1)).first()
        if existing:
            return
        participants = s.execute(select(CoPresenceParticipant).where(
            CoPresenceParticipant.co_presence_session_id == room.id,
            CoPresenceParticipant.participant_type == "companion",
        )).scalars().all()
        for participant in participants:
            _append_membership_event(
                s, room, participant, "invited", from_status=None, to_status=participant.join_status,
                from_role=None, to_role=participant.participant_role, reason="room_created", now=now,
            )
        s.commit()


def _pause_conflicting_channel_binding(s, room: CoPresenceSession, reason: str) -> None:
    from app.db.models import DiscordChannelDelivery, DiscordChannelRoomBinding
    binding = s.execute(select(DiscordChannelRoomBinding).where(
        DiscordChannelRoomBinding.co_presence_session_id == room.id,
        DiscordChannelRoomBinding.binding_status == "active",
    ).with_for_update()).scalar_one_or_none()
    if binding is not None:
        now = datetime.now(timezone.utc)
        binding.binding_status = "conflict_paused"
        binding.paused_at = now
        binding.revision += 1
        binding.evidence_json = {**(binding.evidence_json or {}), "paused_reason": reason, "room_roster_revision": room.roster_revision}
        deliveries = s.execute(select(DiscordChannelDelivery).where(
            DiscordChannelDelivery.discord_channel_room_binding_id == binding.id,
            DiscordChannelDelivery.delivery_status.in_(["queued", "retry_scheduled"]),
        ).with_for_update()).scalars().all()
        for delivery in deliveries:
            delivery.delivery_status = "cancelled"
            delivery.cancelled_at = now
            delivery.next_attempt_at = None
            delivery.lease_owner = None
            delivery.lease_expires_at = None
            delivery.last_error_json = {"code": reason, "message": "Room roster changed before delivery."}


def _membership_event_to_dict(row: CompanionRoomMembershipEvent) -> dict[str, Any]:
    return {
        "id": str(row.id), "participant_id": str(row.participant_id) if row.participant_id else None,
        "companion_id": str(row.companion_id), "event_type": row.event_type,
        "from_status": row.from_status, "to_status": row.to_status,
        "from_role": row.from_role, "to_role": row.to_role,
        "roster_revision": row.roster_revision, "participant_revision": row.participant_revision,
        "reason": row.reason, "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _validate_participants(owner_id: uuid.UUID, primary_id: uuid.UUID, participants: list[dict[str, Any]]) -> None:
    seen = {primary_id}
    for item in participants:
        companion_id = _uuid(item["companion_id"])
        if companion_id in seen:
            raise CompanionRoomError("COMPANION_ROOM_DUPLICATE_PARTICIPANT", "同一位伙伴不能重复加入聊天室。")
        seen.add(companion_id)
        companion = _active_product_companion(companion_id)
        if _uuid(companion["user_id"]) != owner_id:
            raise CompanionRoomError("COMPANION_ROOM_SCOPE_MISMATCH", "所有伙伴必须属于同一位关系创建者。")


def _active_product_companion(companion_id: uuid.UUID) -> dict[str, Any]:
    companion = _active_or_archived_product_companion(companion_id)
    if companion.get("identity_profile_status") != "active":
        raise CompanionRoomError("COMPANION_ROOM_COMPANION_ARCHIVED", "已归档伙伴不能加入新的聊天室。")
    return companion


def _active_or_archived_product_companion(companion_id: uuid.UUID) -> dict[str, Any]:
    companion = companion_roster_service.get_companion_bundle(companion_id)
    if not companion or companion.get("companion_environment") != "product":
        raise CompanionRoomError("COMPANION_ROOM_COMPANION_NOT_FOUND", "未找到可用的产品伙伴。")
    return companion


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
