"""Deterministic companion-scoped memory retrieval and calibrated reranking."""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select, text

from app.core.algorithm_contract import (
    MEMORY_RETRIEVAL_CONTRACT,
    clamp01,
    contract_trace,
)
from app.core.config import settings
from app.db.models import Memory, OutdatedMemoryFlag
from app.memory.embedding import embed_text, get_embedding_provider
from app.memory.learned_reranker import shadow_rank
from app.services.memory_selection_policy_service import resolve_for_retrieval
from app.services.memory_graph_service import (
    activate_memory_graph,
    resolve_memory_layer,
)
from app.services.memory_service import get_session
from app.services.memory_usage_service import create_memory_usage_event

_engine = None
_TOKEN_RE = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]", re.IGNORECASE)
_CONSENT_DENY = {"denied", "revoked", "blocked", "pending_review"}
_ALLOWED_STATES = {"active", "dormant"}
_ALLOWED_SCOPES = {
    "legacy_private",
    "private_companion",
    "relationship",
    "shared_episodic",
}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def retrieve_memories(
    companion_id: uuid.UUID,
    query_text: str,
    current_mode: str = "project",
    top_k: int = 8,
    top_n: int = 30,
    *,
    context: dict[str, Any] | None = None,
    record_usage: bool = True,
) -> dict:
    """Retrieve only boundary-safe memories and rerank them with calibration.

    Unsafe candidates are filtered before scoring. Their content and identifiers
    are not returned in trace output.
    """
    provider = get_embedding_provider()
    query_vec = embed_text(query_text)
    retrieval_context = _normalize_context(context, current_mode)

    db_scored = _db_vector_search(companion_id, query_vec, top_n)
    used_db = db_scored is not None
    if not used_db:
        db_scored = _python_fallback_search(companion_id, query_vec, top_n)

    candidates = _merge_forced_corrections(
        companion_id,
        query_text,
        query_vec,
        db_scored or [],
        top_n,
    )
    candidates.sort(key=lambda item: item[2], reverse=True)

    safe_candidates: list[dict[str, Any]] = []
    boundary_exclusion_counts: dict[str, int] = {}
    for rank_before, (_, memory, semantic_sim, source) in enumerate(candidates, start=1):
        exclusion_reason = _boundary_exclusion_reason(memory, companion_id)
        if exclusion_reason:
            boundary_exclusion_counts[exclusion_reason] = (
                boundary_exclusion_counts.get(exclusion_reason, 0) + 1
            )
            continue
        safe_candidates.append(
            {
                "memory": memory,
                "semantic_similarity": clamp01(semantic_sim),
                "rank_before": rank_before,
                "candidate_source": source,
            }
        )

    flag_map = _load_open_outdated_flags(
        companion_id,
        [item["memory"].id for item in safe_candidates],
    )
    now = datetime.now(timezone.utc)
    for item in safe_candidates:
        score = _rerank_score_details(
            item["memory"],
            item["semantic_similarity"],
            query_text,
            retrieval_context,
            now,
            flag_map.get(item["memory"].id, []),
        )
        item.update(score)

    graph_result = _apply_graph_activation(
        companion_id,
        safe_candidates,
        query_text,
        retrieval_context,
        now,
        flag_map,
    )

    safe_candidates.sort(
        key=lambda item: (
            item["retrieval_score"],
            item["semantic_similarity"],
            str(item["memory"].id),
        ),
        reverse=True,
    )
    for rank_after, item in enumerate(safe_candidates, start=1):
        item["rank_after"] = rank_after
        item["heuristic_rank"] = rank_after
        item["selected"] = rank_after <= top_k
        item["exclusion_reason"] = None if item["selected"] else "below_top_k"

    learned_shadow = shadow_rank(
        companion_id,
        safe_candidates,
        top_k=top_k,
        context=retrieval_context,
    )
    learned_rank_map = {
        item["memory_id"]: item for item in learned_shadow["rank_comparison"]
    }
    for item in safe_candidates:
        comparison = learned_rank_map.get(str(item["memory"].id), {})
        item["learned_shadow_score"] = comparison.get("learned_score")
        item["learned_shadow_rank"] = comparison.get("learned_rank")

    learned_policy = resolve_for_retrieval(companion_id, learned_shadow)
    if learned_policy["applied"]:
        _apply_assistive_order(safe_candidates, top_k)

    selected = [item for item in safe_candidates if item["selected"]]
    excluded = [item for item in safe_candidates if not item["selected"]]
    usage_event_ids = (
        _record_usage_events(
            selected + excluded,
            companion_id,
            retrieval_context,
            query_text,
        )
        if record_usage
        else []
    )

    trace = {
        "candidate_count": len(candidates),
        "safe_candidate_count": len(safe_candidates),
        "selected_count": len(selected),
        "excluded_count": len(excluded),
        "selected_memory_ids": [str(item["memory"].id) for item in selected],
        "excluded": [
            {
                "memory_id": str(item["memory"].id),
                "reason": item["exclusion_reason"],
                "rank_before": item["rank_before"],
                "rank_after": item["rank_after"],
            }
            for item in excluded
        ],
        "boundary_exclusion_counts": boundary_exclusion_counts,
        "method": "pgvector_db" if used_db else "python_cosine_fallback",
        "embedding_provider": provider.provider_name,
        "uses_fallback_embedding": provider.is_fallback,
        "context_summary": _context_summary(retrieval_context),
        "usage_event_ids": usage_event_ids,
        "algorithm": contract_trace(
            MEMORY_RETRIEVAL_CONTRACT,
            feature_sources={
                "feedback_score": "memory.feedback_score and calibrated counts",
                "outdated_score": "age, flags, contradiction, correction, goal mismatch",
                "context_match": "mode, conversation, project, scene metadata",
                "topic_overlap": "deterministic lexical overlap",
                "graph_activation": "bounded same-Companion memory edges after boundary filtering",
            },
        ),
        "learned_shadow": learned_shadow,
        "learned_policy": learned_policy,
        "memory_graph": graph_result,
    }

    return {
        "retrieved": [_candidate_summary(item, include_context=False) for item in safe_candidates],
        "selected": [_candidate_summary(item, include_context=True) for item in selected],
        "trace": trace,
    }


def _apply_assistive_order(
    safe_candidates: list[dict[str, Any]], top_k: int
) -> None:
    safe_candidates.sort(
        key=lambda item: (
            item.get("learned_shadow_rank") or 10**9,
            item["heuristic_rank"],
            str(item["memory"].id),
        )
    )
    for rank_after, item in enumerate(safe_candidates, start=1):
        item["rank_after"] = rank_after
        item["selected"] = rank_after <= top_k
        item["exclusion_reason"] = (
            None if item["selected"] else "below_top_k"
        )


def _db_vector_search(
    companion_id: uuid.UUID,
    query_vec: list[float],
    top_n: int,
) -> list[tuple[str, Memory, float, str]] | None:
    """Use pgvector cosine distance and keep companion isolation in SQL."""
    try:
        vec_str = "[" + ",".join(str(value) for value in query_vec) + "]"
        sql = text(
            """
            SELECT id, 1 - (embedding <=> :qv) AS similarity
            FROM memories
            WHERE companion_id = :cid
              AND state IN ('active', 'dormant')
              AND deleted_at IS NULL
              AND embedding IS NOT NULL
            ORDER BY embedding <=> :qv
            LIMIT :lim
            """
        )
        with _get_engine().connect() as connection:
            rows = connection.execute(
                sql,
                {"qv": vec_str, "cid": str(companion_id), "lim": top_n},
            ).fetchall()
        if not rows:
            return []

        with get_session() as session:
            results = []
            for row in rows:
                memory = session.get(Memory, uuid.UUID(str(row[0])))
                if memory is not None:
                    similarity = float(row[1]) if row[1] is not None else 0.0
                    results.append(
                        (str(memory.id), memory, clamp01(similarity), "vector")
                    )
            session.expunge_all()
            return results
    except Exception:
        return None


def _python_fallback_search(
    companion_id: uuid.UUID,
    query_vec: list[float],
    top_n: int,
) -> list[tuple[str, Memory, float, str]]:
    """Compute cosine similarity in Python when pgvector is unavailable."""
    with get_session() as session:
        memories = list(
            session.execute(
                select(Memory)
                .where(
                    Memory.companion_id == companion_id,
                    Memory.state.in_(tuple(_ALLOWED_STATES)),
                    Memory.deleted_at.is_(None),
                )
                .order_by(Memory.updated_at.desc())
                .limit(max(top_n * 10, 100))
            ).scalars()
        )
        results = [
            (
                str(memory.id),
                memory,
                clamp01(_cosine_sim_python(query_vec, memory)),
                "vector",
            )
            for memory in memories
        ]
        results.sort(key=lambda item: item[2], reverse=True)
        session.expunge_all()
        return results[:top_n]


def _merge_forced_corrections(
    companion_id: uuid.UUID,
    query_text: str,
    query_vec: list[float],
    candidates: list[tuple[str, Memory, float, str]],
    top_n: int,
) -> list[tuple[str, Memory, float, str]]:
    """Add topic-relevant correction memories even when vector recall missed them."""
    merged = list(candidates)
    existing_ids = {item[0] for item in merged}
    with get_session() as session:
        corrections = list(
            session.execute(
                select(Memory)
                .where(
                    Memory.companion_id == companion_id,
                    Memory.owner_companion_id == companion_id,
                    Memory.type == "correction",
                    Memory.state.in_(tuple(_ALLOWED_STATES)),
                    Memory.deleted_at.is_(None),
                )
                .order_by(Memory.updated_at.desc())
                .limit(max(top_n * 4, 40))
            ).scalars()
        )
        for memory in corrections:
            if str(memory.id) in existing_ids:
                continue
            overlap = _topic_overlap(query_text, _memory_text(memory))
            if overlap < 0.20:
                continue
            similarity = clamp01(_cosine_sim_python(query_vec, memory))
            merged.append(
                (str(memory.id), memory, similarity, "forced_correction_overlap")
            )
            existing_ids.add(str(memory.id))
        session.expunge_all()
    return merged


def _boundary_exclusion_reason(
    memory: Memory,
    companion_id: uuid.UUID,
) -> str | None:
    if memory.companion_id != companion_id:
        return "companion_scope_mismatch"
    if memory.owner_companion_id != companion_id:
        return "owner_scope_mismatch"
    if memory.memory_scope_type not in _ALLOWED_SCOPES:
        return "memory_scope_not_injectable"
    if memory.visibility == "sensitive":
        return "sensitive_memory_not_injectable"
    if memory.consent_status in _CONSENT_DENY:
        return "consent_not_granted"
    if memory.state not in _ALLOWED_STATES or memory.deleted_at is not None:
        return "memory_state_not_retrievable"
    policy = memory.visibility_policy_json or {}
    if policy.get("retrieval") in {"blocked", "deny"}:
        return "visibility_policy_blocked"
    return None


def _load_open_outdated_flags(
    companion_id: uuid.UUID,
    memory_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[OutdatedMemoryFlag]]:
    if not memory_ids:
        return {}
    with get_session() as session:
        flags = list(
            session.execute(
                select(OutdatedMemoryFlag).where(
                    OutdatedMemoryFlag.companion_id == companion_id,
                    OutdatedMemoryFlag.memory_id.in_(memory_ids),
                    OutdatedMemoryFlag.status == "open",
                    OutdatedMemoryFlag.deleted_at.is_(None),
                )
            ).scalars()
        )
        result: dict[uuid.UUID, list[OutdatedMemoryFlag]] = {}
        for flag in flags:
            result.setdefault(flag.memory_id, []).append(flag)
        session.expunge_all()
        return result


def _rerank_score_details(
    memory: Memory,
    semantic_sim: float,
    query_text: str,
    context: dict[str, Any],
    now: datetime,
    outdated_flags: list[OutdatedMemoryFlag],
) -> dict[str, Any]:
    age_days = _age_days(memory, now)
    recency = max(0.0, 1.0 - age_days / 180.0)
    topic_overlap = _topic_overlap(query_text, _memory_text(memory))
    context_details = _context_match(memory, context)
    outdated_details = _outdated_score(
        memory,
        query_text,
        context,
        age_days,
        outdated_flags,
    )
    feedback = _feedback_calibration(memory)

    correction_priority = 0.0
    if memory.type == "correction":
        correction_priority = max(
            clamp01(memory.correction_value or 0.0),
            topic_overlap,
        )

    values = {
        "semantic_similarity": clamp01(semantic_sim),
        "memory_strength": clamp01(memory.memory_strength or 0.5),
        "goal_relevance": clamp01(memory.goal_relevance or 0.0),
        "recency_score": clamp01(recency),
        "relationship_impact": clamp01(memory.relationship_impact or 0.0),
        "correction_priority": clamp01(correction_priority),
        "mode_match": clamp01(context_details["mode_match"]),
        "outdated_penalty": clamp01(outdated_details["outdated_score"]),
        "sensitivity_penalty": 0.0,
    }
    base_score = sum(
        MEMORY_RETRIEVAL_CONTRACT["weights"][name] * value
        for name, value in values.items()
    )
    feedback_adjustment = 0.16 * feedback["feedback_signal"]
    context_adjustment = 0.12 * (context_details["context_match"] - 0.5)
    correction_force_adjustment = (
        0.18 * topic_overlap if memory.type == "correction" else 0.0
    )
    retrieval_score = clamp01(
        base_score
        + feedback_adjustment
        + context_adjustment
        + correction_force_adjustment
    )
    return {
        "retrieval_score": retrieval_score,
        "score_json": {
            "base_score": round(base_score, 6),
            "factors": {key: round(value, 6) for key, value in values.items()},
            "feedback": feedback,
            "feedback_adjustment": round(feedback_adjustment, 6),
            "context": context_details,
            "context_adjustment": round(context_adjustment, 6),
            "topic_overlap": round(topic_overlap, 6),
            "correction_force_adjustment": round(correction_force_adjustment, 6),
            "outdated": outdated_details,
        },
    }


def _rerank_score(
    memory: Memory,
    semantic_sim: float,
    current_mode: str,
    now: datetime,
) -> float:
    """Compatibility wrapper used by focused tests and callers."""
    return _rerank_score_details(
        memory,
        semantic_sim,
        "",
        _normalize_context(None, current_mode),
        now,
        [],
    )["retrieval_score"]


def _apply_graph_activation(
    companion_id: uuid.UUID,
    safe_candidates: list[dict[str, Any]],
    query_text: str,
    context: dict[str, Any],
    now: datetime,
    flag_map: dict[uuid.UUID, list[OutdatedMemoryFlag]],
) -> dict[str, Any]:
    seed_scores = {
        item["memory"].id: item["retrieval_score"] for item in safe_candidates
    }
    try:
        graph = activate_memory_graph(
            companion_id,
            seed_scores,
            max_hops=context.get("memory_graph_max_hops", 2),
            max_nodes=context.get("memory_graph_max_nodes", 40),
            edge_budget=context.get("memory_graph_edge_budget", 80),
            enabled=context.get("memory_graph_enabled", True),
        )
    except Exception as exc:
        return {
            "enabled": False,
            "nodes": [],
            "paths": [],
            "truncated": False,
            "truncated_reasons": [],
            "fallback_reason": f"graph_error:{type(exc).__name__}",
        }

    existing = {item["memory"].id: item for item in safe_candidates}
    introduced = [
        node["memory"].id
        for node in graph["nodes"]
        if node["memory"].id not in existing
    ]
    introduced_flags = _load_open_outdated_flags(companion_id, introduced)
    flag_map.update(introduced_flags)

    next_rank_before = len(safe_candidates) + 1
    for node in graph["nodes"]:
        memory = node["memory"]
        item = existing.get(memory.id)
        if item is None:
            item = {
                "memory": memory,
                "semantic_similarity": 0.0,
                "rank_before": next_rank_before,
                "candidate_source": "graph_activation",
            }
            next_rank_before += 1
            item.update(
                _rerank_score_details(
                    memory,
                    0.0,
                    query_text,
                    context,
                    now,
                    flag_map.get(memory.id, []),
                )
            )
            safe_candidates.append(item)
            existing[memory.id] = item

        base_score = float(node["base_score"])
        activation = float(node["activation"])
        propagated = max(0.0, activation - base_score)
        graph_adjustment = 0.12 * propagated
        item["retrieval_score"] = clamp01(
            item["retrieval_score"] + graph_adjustment
        )
        item["memory_layer"] = node["memory_layer"]
        item["graph_activation"] = round(activation, 6)
        item["graph_adjustment"] = round(graph_adjustment, 6)
        item["score_json"]["graph"] = {
            "base_score": round(base_score, 6),
            "activation": round(activation, 6),
            "propagated_activation": round(propagated, 6),
            "adjustment": round(graph_adjustment, 6),
            "memory_layer": node["memory_layer"],
            "introduced_by_graph": node["introduced_by_graph"],
        }

    return {
        key: value
        for key, value in graph.items()
        if key != "nodes"
    } | {
        "nodes": [
            {
                key: value
                for key, value in node.items()
                if key != "memory"
            }
            for node in graph["nodes"]
        ]
    }


def _feedback_calibration(memory: Memory) -> dict[str, Any]:
    helpful = int(memory.calibrated_helpful_count or memory.helpful_count or 0)
    irrelevant = int(
        memory.calibrated_irrelevant_count or memory.irrelevant_count or 0
    )
    outdated = int(memory.calibrated_outdated_count or memory.outdated_count or 0)
    wrong = int(memory.calibrated_wrong_count or memory.wrong_count or 0)
    total = helpful + irrelevant + outdated + wrong
    count_signal = (
        (helpful - 0.8 * irrelevant - 1.0 * outdated - 1.4 * wrong)
        / (total + 2.0)
    )
    stored_signal = max(-1.0, min(1.0, float(memory.feedback_score or 0.0)))
    feedback_signal = max(
        -1.0,
        min(1.0, 0.65 * stored_signal + 0.35 * count_signal),
    )
    return {
        "feedback_signal": round(feedback_signal, 6),
        "stored_feedback_score": round(stored_signal, 6),
        "helpful_count": helpful,
        "irrelevant_count": irrelevant,
        "outdated_count": outdated,
        "wrong_count": wrong,
    }


def _outdated_score(
    memory: Memory,
    query_text: str,
    context: dict[str, Any],
    age_days: int,
    flags: list[OutdatedMemoryFlag],
) -> dict[str, Any]:
    age_risk = clamp01(age_days / 730.0)
    flag_confidence = max(
        (clamp01(flag.confidence or 0.0) for flag in flags),
        default=0.0,
    )
    negative_total = int(memory.wrong_count or 0) + int(memory.outdated_count or 0)
    positive_total = int(memory.helpful_count or 0) + int(
        memory.positive_confirmations or 0
    )
    contradiction_risk = clamp01(
        max(
            flag_confidence,
            negative_total / (negative_total + positive_total + 1.0),
        )
    )
    correction_risk = (
        0.0
        if memory.type == "correction"
        else clamp01((memory.correction_count or 0) / 3.0)
    )
    current_goal = str(context.get("current_goal") or "")
    goal_overlap = (
        _topic_overlap(current_goal or query_text, _memory_text(memory))
        if (current_goal or query_text)
        else 0.5
    )
    goal_mismatch = (
        clamp01(1.0 - goal_overlap)
        if (memory.goal_relevance or 0.0) >= 0.5
        else 0.0
    )
    outdated_score = clamp01(
        0.25 * age_risk
        + 0.35 * contradiction_risk
        + 0.25 * correction_risk
        + 0.15 * goal_mismatch
    )
    return {
        "outdated_score": round(outdated_score, 6),
        "age_days": age_days,
        "age_risk": round(age_risk, 6),
        "contradiction_risk": round(contradiction_risk, 6),
        "correction_risk": round(correction_risk, 6),
        "goal_mismatch": round(goal_mismatch, 6),
        "open_flag_count": len(flags),
        "open_flag_confidence": round(flag_confidence, 6),
    }


def _context_match(memory: Memory, context: dict[str, Any]) -> dict[str, Any]:
    metadata = memory.metadata_ or {}
    declared_mode = _first_value(metadata, "mode_key", "current_mode")
    mode_feedback = memory.mode_specific_feedback or {}
    if declared_mode is None and mode_feedback:
        declared_mode = list(mode_feedback)
    mode_match = _match_value(declared_mode, context.get("mode"), neutral=0.5)

    components = {"mode": mode_match}
    declared_conversation = str(memory.conversation_id) if memory.conversation_id else None
    components["conversation"] = _match_value(
        declared_conversation,
        context.get("conversation_id"),
        neutral=0.5,
    )
    components["project"] = _match_value(
        _first_value(metadata, "project_id"),
        context.get("project_id"),
        neutral=0.5,
    )
    components["scene"] = _match_value(
        _first_value(metadata, "shared_scene_id", "scene_id"),
        context.get("shared_scene_id"),
        neutral=0.5,
    )
    components["session"] = _match_value(
        _first_value(metadata, "co_presence_session_id", "session_id"),
        context.get("co_presence_session_id"),
        neutral=0.5,
    )
    return {
        "mode_match": round(mode_match, 6),
        "context_match": round(sum(components.values()) / len(components), 6),
        "components": {key: round(value, 6) for key, value in components.items()},
    }


def _normalize_context(
    context: dict[str, Any] | None,
    current_mode: str,
) -> dict[str, Any]:
    normalized = dict(context or {})
    normalized["mode"] = normalized.get("mode") or current_mode
    for key in (
        "conversation_id",
        "project_id",
        "shared_scene_id",
        "co_presence_session_id",
        "current_goal",
    ):
        normalized.setdefault(key, None)
    return normalized


def _context_summary(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": context.get("mode"),
        "has_conversation": bool(context.get("conversation_id")),
        "has_project": bool(context.get("project_id")),
        "has_scene": bool(context.get("shared_scene_id")),
        "has_co_presence_session": bool(context.get("co_presence_session_id")),
        "has_goal": bool(context.get("current_goal")),
    }


def _candidate_summary(
    item: dict[str, Any],
    *,
    include_context: bool,
) -> dict[str, Any]:
    memory = item["memory"]
    result = {
        "id": str(memory.id),
        "type": memory.type,
        "summary": memory.summary,
        "memory_strength": memory.memory_strength,
        "state": memory.state,
        "semantic_similarity": round(item["semantic_similarity"], 6),
        "retrieval_score": round(item["retrieval_score"], 6),
        "rank_before": item["rank_before"],
        "rank_after": item["rank_after"],
        "candidate_source": item["candidate_source"],
        "score_json": item["score_json"],
        "memory_layer": item.get("memory_layer") or resolve_memory_layer(memory),
        "graph_activation": item.get("graph_activation", 0.0),
        "graph_adjustment": item.get("graph_adjustment", 0.0),
        "learned_shadow_score": item.get("learned_shadow_score"),
        "learned_shadow_rank": item.get("learned_shadow_rank"),
    }
    if include_context:
        result["content"] = _minimal_context(memory)
    return result


def _minimal_context(memory: Memory) -> str:
    text_value = memory.summary or memory.content or ""
    return " ".join(text_value.split())[:300]


def _record_usage_events(
    items: list[dict[str, Any]],
    companion_id: uuid.UUID,
    context: dict[str, Any],
    query_text: str,
) -> list[str]:
    event_ids = []
    query_fingerprint = hashlib.sha256(query_text.encode("utf-8")).hexdigest()[:16]
    for item in items:
        memory = item["memory"]
        selected = bool(item["selected"])
        try:
            event = create_memory_usage_event(
                {
                    "user_id": str(memory.user_id),
                    "companion_id": str(companion_id),
                    "conversation_id": context.get("conversation_id"),
                    "message_id": context.get("message_id"),
                    "trace_run_id": context.get("trace_run_id"),
                    "memory_id": str(memory.id),
                    "event_type": (
                        "selected" if selected else "not_used_after_retrieval"
                    ),
                    "semantic_similarity": item["semantic_similarity"],
                    "retrieval_score": item["retrieval_score"],
                    "memory_strength_snapshot": memory.memory_strength,
                    "confidence_snapshot": memory.confidence,
                    "goal_relevance_snapshot": memory.goal_relevance,
                    "relationship_impact_snapshot": memory.relationship_impact,
                    "rank_before_rerank": item["rank_before"],
                    "rank_after_rerank": item["rank_after"],
                    "selected_for_context": selected,
                    "why_selected": (
                        "top_k_after_calibrated_rerank" if selected else None
                    ),
                    "why_excluded": item["exclusion_reason"],
                    "score_json": item["score_json"],
                    "usage_context": {
                        **_context_summary(context),
                        "query_fingerprint": query_fingerprint,
                    },
                }
            )
            event_ids.append(event["id"])
        except Exception:
            continue
    return event_ids


def _age_days(memory: Memory, now: datetime) -> int:
    anchor = memory.last_reactivated_at or memory.updated_at or memory.created_at
    if anchor is None:
        return 365
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    return max(0, (now - anchor).days)


def _memory_text(memory: Memory) -> str:
    return " ".join(value for value in (memory.summary, memory.content) if value)


def _topic_overlap(left: str, right: str) -> float:
    left_tokens = set(_TOKEN_RE.findall((left or "").lower()))
    right_tokens = set(_TOKEN_RE.findall((right or "").lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return clamp01(len(left_tokens & right_tokens) / len(left_tokens))


def _first_value(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if metadata.get(key) not in (None, ""):
            return metadata[key]
    nested = metadata.get("context")
    if isinstance(nested, dict):
        for key in keys:
            if nested.get(key) not in (None, ""):
                return nested[key]
    return None


def _match_value(declared: Any, current: Any, *, neutral: float) -> float:
    if declared in (None, "", [], {}):
        return neutral
    if current in (None, "", [], {}):
        return neutral
    declared_values = (
        {str(value) for value in declared}
        if isinstance(declared, (list, tuple, set))
        else {str(declared)}
    )
    return 1.0 if str(current) in declared_values else 0.0


def _cosine_sim_python(query_vec: list[float], memory: Memory) -> float:
    if memory.embedding is None:
        return 0.0
    embedding = memory.embedding
    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()
    if len(embedding) != len(query_vec):
        return 0.0
    dot = sum(left * right for left, right in zip(query_vec, embedding))
    norm_query = math.sqrt(sum(value * value for value in query_vec))
    norm_memory = math.sqrt(sum(value * value for value in embedding))
    if norm_query == 0 or norm_memory == 0:
        return 0.0
    return dot / (norm_query * norm_memory)
