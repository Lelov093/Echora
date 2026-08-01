"""Mutual Presence service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CompanionPresenceFeedbackEvent,
    CompanionPresenceOpportunity,
    CoPresenceOpportunity,
    FeedbackEvent,
    MutualPresencePolicyRun,
    PresenceOpportunity,
)
from app.presence.scoring import personalize_presence_priority
from app.presence.contextual_bandit import evaluate_shadow_policy
from app.services.presence_service import (
    evaluate_presence_suppression,
    get_presence_feedback_profile,
)
from app.services.presence_timing_policy_service import resolve_for_presence

_engine = None
_COMPAT_PRESENCE_TYPE_KEY = "phase4_type"
_COMPAT_PRESENCE_SURFACE_KEY = "phase4_surface"


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def select_presence_surface(payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    interruption_risk = float(payload.get("interruption_risk", 0.0))
    co_presence_session_id = payload.get("co_presence_session_id")
    shared_scene_id = payload.get("shared_scene_id")
    prefers_silence = bool(payload.get("prefers_silence", False))
    prefer_session_surface = bool(payload.get("prefer_session_surface", False))
    prefer_scene_surface = bool(payload.get("prefer_scene_surface", False))
    if prefers_silence or interruption_risk >= 0.8:
        return "silent"
    if shared_scene_id and prefer_scene_surface:
        return "scene_panel"
    if co_presence_session_id and prefer_session_surface:
        return "session_surface"
    return "hub_queue"


def apply_meaningful_silence(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    interruption_risk = float(payload.get("interruption_risk", 0.0))
    user_focus = str(payload.get("user_focus_state", "normal")).lower()
    boundary = str(payload.get("presence_interrupt_policy", "respect_existing_boundary")).lower()
    should_silence = interruption_risk >= 0.8 or user_focus in {"deep_work", "resting"} or "silence" in boundary
    return {
        "should_silence": should_silence,
        "recommended_surface": "silent" if should_silence else select_presence_surface(payload),
        "reason": "high_interruption_risk" if interruption_risk >= 0.8 else ("user_focus_state" if user_focus in {"deep_work", "resting"} else ("boundary_policy" if should_silence else None)),
    }


def create_companion_presence_opportunity(companion_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    silence = apply_meaningful_silence(payload)
    user_id = _to_uuid(payload.get("user_id"))
    if user_id is None:
        return None
    presence_type = payload.get("type", "co_presence_invite")
    initial_surface = silence["recommended_surface"] if silence["should_silence"] else select_presence_surface(payload)
    suppression = evaluate_presence_suppression(
        user_id,
        companion_id,
        presence_type,
        min_interval_seconds=int(payload.get("min_interval_seconds", 1800)),
        realtime_session_id=_to_uuid(payload.get("realtime_session_id")),
    )
    if suppression["hard_block"]:
        shadow_policy = _evaluate_shadow_policy_safe(
            companion_id,
            presence_type,
            "no_show",
            context={
                **payload,
                "feedback_profile": {},
                "surface": "none",
            },
            suppression=suppression,
        )
        return {
            "base_presence_opportunity": None,
            "policy_run": None,
            "companion_presence_opportunity": None,
            "co_presence_opportunity": None,
            "meaningful_silence": {
                "should_silence": True,
                "recommended_surface": "silent",
                "reason": suppression["reason"],
            },
            "suppression": suppression,
            "shadow_policy": shadow_policy,
        }
    persisted_silence = suppression["suppress"]
    if persisted_silence:
        silence = {
            "should_silence": True,
            "recommended_surface": "silent",
            "reason": suppression["reason"],
        }

    feedback_profile = get_presence_feedback_profile(
        companion_id,
        presence_type,
        initial_surface,
    )
    policy_context = _enrich_policy_context(
        user_id,
        companion_id,
        payload,
        feedback_profile,
    )
    personalized = personalize_presence_priority(
        {
            "score": float(payload.get("priority", 0.5)),
            "decision": "create_queue",
            "create_opportunity": True,
            "recommended_surface": initial_surface,
            "reason": payload.get("reason") or "Companion presence opportunity",
            "factors": {},
            "algorithm": {"policy_mode": "heuristic"},
        },
        acceptance_rate=feedback_profile["acceptance_rate"],
        recent_dismissal_penalty=feedback_profile["recent_dismissal_penalty"],
    )
    surface = silence["recommended_surface"] if silence["should_silence"] else select_presence_surface(payload)
    persisted_silence = persisted_silence or bool(silence["should_silence"])
    heuristic_action = _selected_action_from_surface(surface)
    shadow_suppression = dict(suppression)
    if silence["should_silence"] and not shadow_suppression.get("suppress"):
        shadow_suppression.update(
            {
                "suppress": True,
                "hard_block": False,
                "reason": silence["reason"] or "meaningful_silence",
            }
        )
    shadow_policy = _evaluate_shadow_policy_safe(
        companion_id,
        presence_type,
        heuristic_action,
        context={
            **policy_context,
            "surface": surface,
        },
        suppression=shadow_suppression,
    )
    policy_surface = "hub" if heuristic_action == "hub" else "queue"
    assistive_policy = resolve_for_presence(
        companion_id,
        surface=policy_surface,
        heuristic_action=heuristic_action,
        shadow_policy=shadow_policy,
        suppression=shadow_suppression,
    )
    effective_action = (
        str(assistive_policy.get("selected_action"))
        if assistive_policy.get("applied")
        else heuristic_action
    )
    if assistive_policy.get("applied"):
        surface, silence, persisted_silence = _apply_presence_action(
            effective_action,
            original_surface=surface,
            silence=silence,
            persisted_silence=persisted_silence,
        )
    with get_session() as s:
        if effective_action == "no_show":
            policy_run = MutualPresencePolicyRun(
                user_id=user_id,
                primary_companion_id=companion_id,
                co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
                shared_scene_id=_to_uuid(payload.get("shared_scene_id")),
                trace_run_id=_to_uuid(payload.get("trace_run_id")),
                source_presence_policy_run_id=_to_uuid(shadow_policy.get("id")),
                presence_opportunity_id=None,
                policy_scope="co_presence"
                if payload.get("co_presence_session_id")
                else "companion_presence",
                learning_mode="assistive",
                selected_action="no_show",
                policy_status="completed",
                reward_prediction=shadow_policy.get("reward_prediction"),
                mutuality_score=float(payload.get("mutuality_score", 0.5)),
                interruption_risk=float(payload.get("interruption_risk", 0.0)),
                presence_value=float(payload.get("presence_value", 0.5)),
                explanation_json={
                    "selected_surface": "none",
                    "meaningful_silence": silence,
                    "feedback_profile": feedback_profile,
                    "personalization": personalized["personalization"],
                    "suppression": suppression,
                    "shadow_policy": _shadow_summary(shadow_policy),
                    "assistive_policy": assistive_policy,
                    "user_visible_policy": "presence_assistive",
                },
                boundary_json=payload.get("boundary_json") or {},
                signal_json=payload.get("signal_json") or {},
                metadata_={"implementation_origin": "presence_policy"},
            )
            s.add(policy_run)
            s.commit()
            s.refresh(policy_run)
            return {
                "base_presence_opportunity": None,
                "policy_run": policy_run_to_dict(policy_run),
                "companion_presence_opportunity": None,
                "co_presence_opportunity": None,
                "meaningful_silence": {
                    "should_silence": True,
                    "recommended_surface": "none",
                    "reason": "assistive_no_show",
                },
                "suppression": suppression,
                "feedback_profile": feedback_profile,
                "personalization": personalized["personalization"],
                "shadow_policy": shadow_policy,
                "assistive_policy": assistive_policy,
            }
        base_surface = _base_presence_surface(surface)
        base_type = _base_presence_type(presence_type)
        base = PresenceOpportunity(
            user_id=user_id,
            companion_id=companion_id,
            conversation_id=_to_uuid(payload.get("conversation_id")),
            co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
            type=base_type,
            title=payload.get("title", "Companion presence opportunity"),
            message=payload.get("message"),
            reason=payload.get("reason"),
            evidence_memory_ids=[_to_uuid(x) for x in payload.get("evidence_memory_ids", []) if _to_uuid(x)],
            evidence_message_ids=[_to_uuid(x) for x in payload.get("evidence_message_ids", []) if _to_uuid(x)],
            evidence_growth_ids=[_to_uuid(x) for x in payload.get("evidence_growth_ids", []) if _to_uuid(x)],
            priority=personalized["score"],
            urgency=float(payload.get("urgency", 0.4)),
            sensitivity=float(payload.get("sensitivity", 0.2)),
            interruption_risk=float(payload.get("interruption_risk", 0.0)),
            recommended_surface=base_surface,
            status="suppressed" if persisted_silence else "queued",
            meaningful_silence_reason=silence["reason"],
            calibration_json={
                "implementation_origin": "presence_and_persona",
                "meaningful_silence": silence,
                "presence_surface": surface,
                "base_surface": base_surface,
                "presence_type": presence_type,
                "base_type": base_type,
                "feedback_profile": feedback_profile,
                "personalization": personalized["personalization"],
                "suppression": suppression,
                "policy_mode": assistive_policy["policy_mode"],
                "shadow_policy": _shadow_summary(shadow_policy),
                "assistive_policy": assistive_policy,
            },
            metadata_={"implementation_origin": "presence_and_persona"},
        )
        s.add(base)
        s.flush()

        policy_run = MutualPresencePolicyRun(
            user_id=user_id,
            primary_companion_id=companion_id,
            co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
            shared_scene_id=_to_uuid(payload.get("shared_scene_id")),
            trace_run_id=_to_uuid(payload.get("trace_run_id")),
            source_presence_policy_run_id=_to_uuid(shadow_policy.get("id")),
            presence_opportunity_id=base.id,
            policy_scope="co_presence" if payload.get("co_presence_session_id") else "companion_presence",
            learning_mode=assistive_policy["policy_mode"],
            selected_action=effective_action,
            policy_status="completed" if not silence["should_silence"] else "completed",
            reward_prediction=shadow_policy.get("reward_prediction"),
            mutuality_score=float(payload.get("mutuality_score", 0.5)),
            interruption_risk=float(payload.get("interruption_risk", 0.0)),
            presence_value=float(payload.get("presence_value", 0.5)),
            explanation_json={
                "selected_surface": surface,
                "meaningful_silence": silence,
                "feedback_profile": feedback_profile,
                "personalization": personalized["personalization"],
                "suppression": suppression,
                "shadow_policy": _shadow_summary(shadow_policy),
                "assistive_policy": assistive_policy,
                "user_visible_policy": assistive_policy["user_visible_policy"],
            },
            boundary_json=payload.get("boundary_json") or {},
            signal_json=payload.get("signal_json") or {},
            metadata_={"implementation_origin": "presence_and_persona"},
        )
        s.add(policy_run)
        s.flush()

        companion_presence = CompanionPresenceOpportunity(
            user_id=user_id,
            companion_id=companion_id,
            base_presence_opportunity_id=base.id,
            co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
            shared_scene_id=_to_uuid(payload.get("shared_scene_id")),
            mutual_presence_policy_run_id=policy_run.id,
            opportunity_origin=payload.get("opportunity_origin", "manual"),
            presence_mode=payload.get("presence_mode", "reflection"),
            opportunity_status="expired" if persisted_silence else "queued",
            recommended_surface=surface,
            requires_user_confirmation=bool(payload.get("requires_user_confirmation", False)),
            review_required=bool(payload.get("review_required", False)),
            rationale_summary=payload.get("rationale_summary") or ("meaningful silence applied" if silence["should_silence"] else "presence opportunity queued"),
            presence_context_json=payload.get("presence_context_json") or {},
            policy_json={
                "meaningful_silence": silence,
                "shadow_policy": _shadow_summary(shadow_policy),
                "assistive_policy": assistive_policy,
            },
            metadata_={"implementation_origin": "presence_and_persona"},
        )
        s.add(companion_presence)
        s.flush()

        co_presence_opportunity = None
        if not persisted_silence and (payload.get("co_presence_session_id") or payload.get("target_companion_id")):
            co_presence_opportunity = CoPresenceOpportunity(
                user_id=user_id,
                primary_companion_id=companion_id,
                base_presence_opportunity_id=base.id,
                co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
                shared_scene_id=_to_uuid(payload.get("shared_scene_id")),
                target_companion_id=_to_uuid(payload.get("target_companion_id")),
                mutual_presence_policy_run_id=policy_run.id,
                opportunity_type=payload.get("opportunity_type", "invite_active_companion"),
                opportunity_status="queued",
                target_role=payload.get("target_role", "active_companion"),
                recommended_surface=surface,
                requires_user_confirmation=bool(payload.get("requires_user_confirmation", True)),
                rationale_summary=payload.get("rationale_summary") or "co-presence opportunity queued",
                boundary_json=payload.get("boundary_json") or {},
                policy_json={
                    "meaningful_silence": silence,
                    "assistive_policy": assistive_policy,
                },
                metadata_={"implementation_origin": "presence_and_persona"},
            )
            s.add(co_presence_opportunity)

        s.commit()
        s.refresh(base)
        s.refresh(policy_run)
        s.refresh(companion_presence)
        if co_presence_opportunity is not None:
            s.refresh(co_presence_opportunity)

        return {
            "base_presence_opportunity": presence_to_dict(base),
            "policy_run": policy_run_to_dict(policy_run),
            "companion_presence_opportunity": companion_presence_to_dict(companion_presence),
            "co_presence_opportunity": co_presence_to_dict(co_presence_opportunity) if co_presence_opportunity else None,
            "meaningful_silence": silence,
            "suppression": suppression,
            "feedback_profile": feedback_profile,
            "personalization": personalized["personalization"],
            "shadow_policy": shadow_policy,
            "assistive_policy": assistive_policy,
        }


def record_presence_feedback(companion_id: uuid.UUID, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = payload or {}
    with get_session() as s:
        user_id = _to_uuid(payload.get("user_id"))
        if user_id is None:
            return None
        feedback_event = FeedbackEvent(
            user_id=user_id,
            companion_id=companion_id,
            conversation_id=_to_uuid(payload.get("conversation_id")),
            message_id=_to_uuid(payload.get("message_id")),
            trace_run_id=_to_uuid(payload.get("trace_run_id")),
            target_type="presence_opportunity",
            target_id=_to_uuid(payload.get("presence_opportunity_id")),
            action=payload.get("action", "feedback"),
            label=payload.get("label", "neutral"),
            reason=payload.get("reason"),
            user_note=payload.get("feedback_note"),
            score_delta=float(payload.get("score_delta", 0.0)),
            confidence_delta=float(payload.get("confidence_delta", 0.0)),
            strength_delta=float(payload.get("strength_delta", 0.0)),
            priority_delta=float(payload.get("priority_delta", 0.0)),
            applies_to_presence=True,
            applies_to_memory=False,
            applies_to_growth=False,
            applies_to_retrieval=False,
            applies_to_relationship=False,
            applies_to_boundary=False,
            calibration_status="applied",
            applied_at=datetime.now(timezone.utc),
            context_json=payload.get("context_json") or {},
            before_json=payload.get("before_json") or {},
            after_json=payload.get("after_json") or {},
            metadata_={"implementation_origin": "presence_and_persona"},
        )
        s.add(feedback_event)
        s.flush()

        presence_feedback = CompanionPresenceFeedbackEvent(
            user_id=user_id,
            companion_id=companion_id,
            base_presence_opportunity_id=_to_uuid(payload.get("presence_opportunity_id")),
            companion_presence_opportunity_id=_to_uuid(payload.get("companion_presence_opportunity_id")),
            co_presence_opportunity_id=_to_uuid(payload.get("co_presence_opportunity_id")),
            mutual_presence_policy_run_id=_to_uuid(payload.get("mutual_presence_policy_run_id")),
            feedback_event_id=feedback_event.id,
            feedback_type=payload.get("feedback_type", "accept"),
            feedback_source=payload.get("feedback_source", "user"),
            feedback_strength=float(payload.get("feedback_strength", 0.5)) if payload.get("feedback_strength") is not None else None,
            feedback_note=payload.get("feedback_note"),
            feedback_json=payload.get("feedback_json") or {},
            metadata_={"implementation_origin": "presence_and_persona"},
        )
        s.add(presence_feedback)

        base_presence = s.get(PresenceOpportunity, _to_uuid(payload.get("presence_opportunity_id"))) if payload.get("presence_opportunity_id") else None
        if base_presence is not None:
            base_presence.feedback_event_id = feedback_event.id
            base_presence.feedback_label = payload.get("label", base_presence.feedback_label)
            if payload.get("feedback_type") == "accept":
                base_presence.status = "accepted"
                base_presence.accepted_at = datetime.now(timezone.utc)
                base_presence.reward = 1.0
            elif payload.get("feedback_type") in {"dismiss", "bad_timing", "too_much"}:
                base_presence.status = "dismissed"
                base_presence.dismissed_at = datetime.now(timezone.utc)
                base_presence.reward = -0.5
            elif payload.get("feedback_type") == "snooze":
                base_presence.status = "snoozed"
            elif payload.get("feedback_type") == "suppress_type":
                base_presence.status = "dismissed"
                base_presence.suppress_type_rule_applied = True

        s.commit()
        s.refresh(feedback_event)
        s.refresh(presence_feedback)
        if base_presence is not None:
            s.refresh(base_presence)
        result = {
            "feedback_event_id": str(feedback_event.id),
            "presence_feedback": presence_feedback_to_dict(presence_feedback),
            "base_presence_opportunity": presence_to_dict(base_presence) if base_presence else None,
        }
    if base_presence is not None:
        try:
            from app.services.strategy_service import create_presence_feedback_sample

            reward = _feedback_reward(payload.get("feedback_type", "accept"))
            sample = create_presence_feedback_sample(
                {
                    "user_id": str(user_id),
                    "companion_id": str(companion_id),
                    "presence_opportunity_id": str(base_presence.id),
                    "feedback_event_id": str(feedback_event.id),
                    "action_taken": _selected_action_from_surface(
                        (base_presence.calibration_json or {}).get(
                            "presence_surface",
                            (base_presence.calibration_json or {}).get(
                                _COMPAT_PRESENCE_SURFACE_KEY,
                                base_presence.recommended_surface,
                            ),
                        )
                    ),
                    "reward": reward,
                    "feature_json": {
                        "opportunity_type": str(
                            (base_presence.calibration_json or {}).get("presence_type")
                            or (base_presence.calibration_json or {}).get(
                                _COMPAT_PRESENCE_TYPE_KEY
                            )
                            or base_presence.type
                        ),
                        "surface": str(
                            (base_presence.calibration_json or {}).get("presence_surface")
                            or (base_presence.calibration_json or {}).get(
                                _COMPAT_PRESENCE_SURFACE_KEY
                            )
                            or base_presence.recommended_surface
                        ),
                        "interruption_risk": float(
                            base_presence.interruption_risk or 0.0
                        ),
                        "feedback_type": payload.get("feedback_type"),
                    },
                }
            )
            result["presence_policy_feedback_sample_id"] = sample["id"]
        except Exception:
            result["presence_policy_feedback_sample_id"] = None
    return result


def presence_to_dict(opportunity: PresenceOpportunity | None) -> dict[str, Any] | None:
    if opportunity is None:
        return None
    return {
        "id": str(opportunity.id),
        "companion_id": str(opportunity.companion_id),
        "type": (
            (opportunity.calibration_json or {}).get("presence_type")
            or (opportunity.calibration_json or {}).get(_COMPAT_PRESENCE_TYPE_KEY)
            or opportunity.type
        ),
        "base_type": opportunity.type,
        "title": opportunity.title,
        "recommended_surface": (
            (opportunity.calibration_json or {}).get("presence_surface")
            or (opportunity.calibration_json or {}).get(_COMPAT_PRESENCE_SURFACE_KEY)
            or opportunity.recommended_surface
        ),
        "base_surface": opportunity.recommended_surface,
        "status": opportunity.status,
        "meaningful_silence_reason": opportunity.meaningful_silence_reason,
        "priority": opportunity.priority,
        "interruption_risk": opportunity.interruption_risk,
    }


def policy_run_to_dict(run: MutualPresencePolicyRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "source_presence_policy_run_id": (
            str(run.source_presence_policy_run_id)
            if run.source_presence_policy_run_id
            else None
        ),
        "policy_scope": run.policy_scope,
        "learning_mode": run.learning_mode,
        "selected_action": run.selected_action,
        "policy_status": run.policy_status,
        "reward_prediction": run.reward_prediction,
        "mutuality_score": run.mutuality_score,
        "interruption_risk": run.interruption_risk,
        "presence_value": run.presence_value,
        "explanation_json": run.explanation_json or {},
    }


def companion_presence_to_dict(opportunity: CompanionPresenceOpportunity) -> dict[str, Any]:
    return {
        "id": str(opportunity.id),
        "opportunity_origin": opportunity.opportunity_origin,
        "presence_mode": opportunity.presence_mode,
        "opportunity_status": opportunity.opportunity_status,
        "recommended_surface": opportunity.recommended_surface,
        "review_required": opportunity.review_required,
        "rationale_summary": opportunity.rationale_summary,
        "policy_json": opportunity.policy_json or {},
    }


def co_presence_to_dict(opportunity: CoPresenceOpportunity) -> dict[str, Any]:
    return {
        "id": str(opportunity.id),
        "opportunity_type": opportunity.opportunity_type,
        "opportunity_status": opportunity.opportunity_status,
        "target_role": opportunity.target_role,
        "recommended_surface": opportunity.recommended_surface,
        "requires_user_confirmation": opportunity.requires_user_confirmation,
    }


def presence_feedback_to_dict(feedback: CompanionPresenceFeedbackEvent) -> dict[str, Any]:
    return {
        "id": str(feedback.id),
        "feedback_type": feedback.feedback_type,
        "feedback_source": feedback.feedback_source,
        "feedback_strength": feedback.feedback_strength,
        "feedback_note": feedback.feedback_note,
        "feedback_json": feedback.feedback_json or {},
    }


def _selected_action_from_surface(surface: str) -> str:
    if surface == "scene_panel":
        return "hub"
    if surface == "session_surface":
        return "hub"
    if surface == "silent":
        return "silence"
    if surface == "none":
        return "no_show"
    return "queue"


def _apply_presence_action(
    action: str,
    *,
    original_surface: str,
    silence: dict[str, Any],
    persisted_silence: bool,
) -> tuple[str, dict[str, Any], bool]:
    if action == "silence":
        return (
            "silent",
            {
                "should_silence": True,
                "recommended_surface": "silent",
                "reason": "assistive_meaningful_silence",
            },
            True,
        )
    if action == "queue":
        return (
            "hub_queue",
            {
                "should_silence": False,
                "recommended_surface": "hub_queue",
                "reason": None,
            },
            False,
        )
    if action == "hub":
        return original_surface, silence, persisted_silence
    if action == "no_show":
        return "none", silence, True
    return original_surface, silence, persisted_silence


def _shadow_summary(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": policy.get("id"),
        "policy_mode": policy.get("policy_mode"),
        "heuristic_action": policy.get("heuristic_action"),
        "shadow_action": policy.get("shadow_action"),
        "reward_prediction": policy.get("reward_prediction"),
        "selected_propensity": policy.get("selected_propensity"),
        "actual_action_changed": policy.get("actual_action_changed"),
        "safety_forced_action": policy.get("safety_forced_action"),
        "fallback_reason": policy.get("fallback_reason"),
    }


def _feedback_reward(feedback_type: str) -> float:
    return {
        "accept": 1.0,
        "good_timing": 1.0,
        "continued": 0.8,
        "useful": 1.0,
        "snooze": -0.25,
        "ignored": -0.35,
        "dismiss": -0.8,
        "bad_timing": -0.8,
        "too_much": -1.0,
        "suppress_type": -1.0,
        "disabled": -1.0,
    }.get(str(feedback_type), 0.0)


def _enrich_policy_context(
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    payload: dict[str, Any],
    feedback_profile: dict[str, Any],
) -> dict[str, Any]:
    context = {**payload, "feedback_profile": feedback_profile}
    try:
        from app.services.relationship_service import get_relationship_state

        context["relationship"] = get_relationship_state(companion_id) or {}
    except Exception:
        context["relationship"] = {}
    try:
        from app.services.user_state_service import get_current_state

        current = get_current_state(user_id, companion_id)
        context["user_state"] = {
            key: value.get("value")
            for key, value in current.get("signals", {}).items()
        }
    except Exception:
        context["user_state"] = {}
    context.setdefault("goal_progress", payload.get("presence_value", 0.0))
    context.setdefault(
        "continuity_importance",
        payload.get("continuity_importance", payload.get("presence_value", 0.0)),
    )
    return context


def _evaluate_shadow_policy_safe(
    companion_id: uuid.UUID,
    opportunity_type: str,
    heuristic_action: str,
    *,
    context: dict[str, Any],
    suppression: dict[str, Any],
) -> dict[str, Any]:
    try:
        return evaluate_shadow_policy(
            companion_id,
            opportunity_type,
            heuristic_action,
            context=context,
            suppression=suppression,
        )
    except Exception as exc:
        return {
            "id": None,
            "policy_mode": "shadow",
            "heuristic_action": heuristic_action,
            "shadow_action": heuristic_action,
            "reward_prediction": None,
            "selected_propensity": 1.0,
            "actual_action_changed": False,
            "safety_forced_action": None,
            "fallback_reason": f"shadow_evaluation_failed:{type(exc).__name__}",
        }


def _base_presence_surface(surface: str) -> str:
    if surface == "scene_panel":
        return "inline"
    if surface == "session_surface":
        return "inline"
    if surface == "silent":
        return "queue"
    if surface == "hub_queue":
        return "queue"
    return "queue"


def _base_presence_type(presence_type: str) -> str:
    mapping = {
        "co_presence_invite": "check_in",
        "shared_reflection": "reflection",
        "observer_support": "boundary",
        "delegation_followup": "progress",
        "repair": "boundary",
    }
    return mapping.get(presence_type, "reflection")


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
