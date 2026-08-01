"""Bounded, boundary-first memory graph activation."""

from __future__ import annotations

import uuid
from collections import deque
from typing import Any

from sqlalchemy import select

from app.core.algorithm_contract import clamp01
from app.db.models import Memory, MemoryEdge
from app.services.persistence_helpers import get_session


ALGORITHM_VERSION = "core-r11-memory-graph-v1"
ALLOWED_EDGE_TYPES = {
    "correction_of",
    "supports",
    "contradicts",
    "same_goal",
    "same_project",
    "shared_experience",
    "relationship_turning_point",
}
DEFAULT_MAX_HOPS = 2
DEFAULT_MAX_NODES = 40
DEFAULT_EDGE_BUDGET = 80
DISTANCE_DECAY = 0.65
_CONSENT_DENY = {"denied", "revoked", "blocked", "pending_review"}
_ALLOWED_STATES = {"active", "dormant"}
_ALLOWED_SCOPES = {
    "legacy_private",
    "private_companion",
    "relationship",
    "shared_episodic",
}


def create_memory_edge(
    companion_id: uuid.UUID,
    source_memory_id: uuid.UUID,
    target_memory_id: uuid.UUID,
    *,
    edge_type: str,
    edge_weight: float,
    reason: str,
    edge_source: str,
    confidence: float,
) -> MemoryEdge:
    if edge_type not in ALLOWED_EDGE_TYPES:
        raise ValueError(f"Unsupported memory edge type: {edge_type}")
    if not reason.strip() or not edge_source.strip():
        raise ValueError("Memory edge requires reason and source")
    if source_memory_id == target_memory_id:
        raise ValueError("Memory graph self-edge is not allowed")
    with get_session() as session:
        source = session.get(Memory, source_memory_id)
        target = session.get(Memory, target_memory_id)
        if source is None or target is None:
            raise ValueError("Memory edge endpoint not found")
        if (
            source.user_id != target.user_id
            or source.companion_id != companion_id
            or target.companion_id != companion_id
            or source.owner_companion_id != companion_id
            or target.owner_companion_id != companion_id
        ):
            raise ValueError("Memory edge violates Companion ownership boundary")
        edge = MemoryEdge(
            user_id=source.user_id,
            companion_id=companion_id,
            source_memory_id=source.id,
            target_memory_id=target.id,
            edge_type=edge_type,
            edge_weight=clamp01(edge_weight, 0.5),
            reason=reason,
            edge_source=edge_source,
            confidence=clamp01(confidence, 0.5),
            metadata_={"algorithm_version": ALGORITHM_VERSION},
        )
        session.add(edge)
        session.commit()
        session.refresh(edge)
        return edge


def activate_memory_graph(
    companion_id: uuid.UUID,
    seed_scores: dict[uuid.UUID, float],
    *,
    max_hops: int = DEFAULT_MAX_HOPS,
    max_nodes: int = DEFAULT_MAX_NODES,
    edge_budget: int = DEFAULT_EDGE_BUDGET,
    enabled: bool = True,
) -> dict[str, Any]:
    """Propagate activation only through safe, same-Companion memories."""
    if not enabled:
        return _empty_result("graph_disabled")
    max_hops = max(0, min(4, int(max_hops)))
    max_nodes = max(1, min(100, int(max_nodes)))
    edge_budget = max(1, min(250, int(edge_budget)))
    if not seed_scores:
        return _empty_result("no_safe_seed_nodes")

    with get_session() as session:
        safe_seed_ids = []
        activation: dict[uuid.UUID, float] = {}
        nodes: dict[uuid.UUID, Memory] = {}
        excluded_counts: dict[str, int] = {}
        for memory_id, score in seed_scores.items():
            memory = session.get(Memory, memory_id)
            reason = _unsafe_reason(memory, companion_id)
            if reason:
                excluded_counts[reason] = excluded_counts.get(reason, 0) + 1
                continue
            safe_seed_ids.append(memory_id)
            nodes[memory_id] = memory
            activation[memory_id] = clamp01(score)

        queue = deque((memory_id, 0) for memory_id in safe_seed_ids)
        best_distance = {memory_id: 0 for memory_id in safe_seed_ids}
        paths = []
        edges_evaluated = 0
        truncated_reasons: set[str] = set()

        while queue:
            source_id, distance = queue.popleft()
            if distance >= max_hops:
                truncated_reasons.add("hop_budget")
                continue
            if len(nodes) >= max_nodes:
                truncated_reasons.add("node_budget")
                break
            edges = list(
                session.execute(
                    select(MemoryEdge)
                    .where(
                        MemoryEdge.companion_id == companion_id,
                        MemoryEdge.source_memory_id == source_id,
                    )
                    .order_by(
                        MemoryEdge.edge_weight.desc(),
                        MemoryEdge.confidence.desc(),
                        MemoryEdge.id,
                    )
                ).scalars()
            )
            for edge in edges:
                if edges_evaluated >= edge_budget:
                    truncated_reasons.add("edge_budget")
                    break
                edges_evaluated += 1
                target = session.get(Memory, edge.target_memory_id)
                reason = _unsafe_reason(target, companion_id)
                if reason:
                    excluded_counts[reason] = excluded_counts.get(reason, 0) + 1
                    continue
                next_distance = distance + 1
                contribution = (
                    clamp01(edge.edge_weight)
                    * activation[source_id]
                    * (DISTANCE_DECAY ** next_distance)
                    * clamp01(edge.confidence, 0.5)
                )
                prior = activation.get(target.id, 0.0)
                activation[target.id] = min(1.0, prior + contribution)
                nodes[target.id] = target
                paths.append(
                    {
                        "source_memory_id": str(source_id),
                        "target_memory_id": str(target.id),
                        "edge_id": str(edge.id),
                        "edge_type": edge.edge_type,
                        "edge_weight": round(edge.edge_weight, 6),
                        "edge_confidence": round(edge.confidence, 6),
                        "edge_source": edge.edge_source,
                        "reason": edge.reason,
                        "distance": next_distance,
                        "source_activation": round(activation[source_id], 6),
                        "contribution": round(contribution, 6),
                        "target_activation": round(activation[target.id], 6),
                    }
                )
                if (
                    next_distance < max_hops
                    and next_distance < best_distance.get(target.id, max_hops + 1)
                ):
                    best_distance[target.id] = next_distance
                    queue.append((target.id, next_distance))
            if edges_evaluated >= edge_budget:
                break

        result_nodes = [
            {
                "memory": memory,
                "memory_id": str(memory_id),
                "base_score": round(clamp01(seed_scores.get(memory_id)), 6),
                "activation": round(clamp01(activation[memory_id]), 6),
                "introduced_by_graph": memory_id not in seed_scores,
                "memory_layer": resolve_memory_layer(memory),
            }
            for memory_id, memory in nodes.items()
        ]
        session.expunge_all()
    return {
        "enabled": True,
        "algorithm_version": ALGORITHM_VERSION,
        "max_hops": max_hops,
        "max_nodes": max_nodes,
        "edge_budget": edge_budget,
        "distance_decay": DISTANCE_DECAY,
        "safe_seed_count": len(safe_seed_ids),
        "activated_node_count": len(result_nodes),
        "edges_evaluated": edges_evaluated,
        "nodes": result_nodes,
        "paths": paths,
        "excluded_counts": excluded_counts,
        "truncated": bool(truncated_reasons),
        "truncated_reasons": sorted(truncated_reasons),
        "fallback_reason": None,
    }


def resolve_memory_layer(memory: Memory) -> str:
    metadata = memory.metadata_ or {}
    if memory.shared_memory_id or memory.memory_scope_type == "shared_episodic":
        return "shared_episodic"
    if memory.memory_scope_type == "relationship":
        return "relationship"
    if metadata.get("project_id") or metadata.get("task_id"):
        return "project_context"
    if memory.conversation_id or any(
        metadata.get(key)
        for key in (
            "co_presence_session_id",
            "shared_scene_id",
            "realtime_session_id",
            "channel_id",
        )
    ):
        return "session_context"
    return memory.memory_layer or "companion_private"


def _unsafe_reason(memory: Memory | None, companion_id: uuid.UUID) -> str | None:
    if memory is None:
        return "memory_not_found"
    if memory.companion_id != companion_id or memory.owner_companion_id != companion_id:
        return "companion_boundary"
    if memory.visibility == "sensitive":
        return "sensitive_memory"
    if memory.consent_status in _CONSENT_DENY:
        return "consent_not_granted"
    if memory.memory_scope_type not in _ALLOWED_SCOPES:
        return "memory_scope_not_injectable"
    if memory.state not in _ALLOWED_STATES or memory.deleted_at is not None:
        return "memory_not_retrievable"
    policy = memory.visibility_policy_json or {}
    if policy.get("retrieval") in {"blocked", "deny"}:
        return "visibility_policy_blocked"
    return None


def _empty_result(reason: str) -> dict[str, Any]:
    return {
        "enabled": False,
        "algorithm_version": ALGORITHM_VERSION,
        "nodes": [],
        "paths": [],
        "excluded_counts": {},
        "truncated": False,
        "truncated_reasons": [],
        "fallback_reason": reason,
    }
