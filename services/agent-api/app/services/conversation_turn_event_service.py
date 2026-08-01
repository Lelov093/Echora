"""Transient, process-local SSE fan-out for scoped Conversation turn events."""

from __future__ import annotations

import json
import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Iterator


_lock = threading.Lock()
_subscribers: dict[uuid.UUID, set[queue.Queue]] = {}
_sequences: dict[uuid.UUID, int] = {}


def publish(trace_run_id: uuid.UUID, event_type: str, data: dict[str, Any]) -> None:
    """Publish safe lifecycle or generated-text data without persisting token chunks."""
    with _lock:
        sequence = _sequences.get(trace_run_id, 0) + 1
        _sequences[trace_run_id] = sequence
        targets = list(_subscribers.get(trace_run_id, set()))
        if event_type in {"completed", "failed", "cancelled"}:
            _sequences.pop(trace_run_id, None)
    event = {
        "id": f"turn:{trace_run_id}:{sequence}",
        "event": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "trace_run_id": str(trace_run_id),
        **data,
    }
    for target in targets:
        try:
            target.put_nowait(event)
        except queue.Full:
            try:
                target.get_nowait()
                target.put_nowait(event)
            except (queue.Empty, queue.Full):
                continue


def iter_sse_events(
    trace_run_id: uuid.UUID,
    initial_status: dict[str, Any],
) -> Iterator[str]:
    subscriber: queue.Queue = queue.Queue(maxsize=256)
    with _lock:
        _subscribers.setdefault(trace_run_id, set()).add(subscriber)
    try:
        yield _format_event({
            "id": f"turn:{trace_run_id}:snapshot",
            "event": "snapshot",
            "trace_run_id": str(trace_run_id),
            "status": _safe_status_snapshot(initial_status),
        })
        if initial_status.get("status") in {"completed", "failed", "cancelled"}:
            return
        while True:
            try:
                event = subscriber.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            yield _format_event(event)
            if event.get("event") in {"completed", "failed", "cancelled"}:
                return
    finally:
        with _lock:
            targets = _subscribers.get(trace_run_id)
            if targets is not None:
                targets.discard(subscriber)
                if not targets:
                    _subscribers.pop(trace_run_id, None)


def _format_event(event: dict[str, Any]) -> str:
    return "\n".join([
        f"id: {event.get('id', '')}",
        f"event: {event.get('event', 'message')}",
        f"data: {json.dumps(event, ensure_ascii=True, default=str)}",
        "",
        "",
    ])


def _safe_status_snapshot(status: dict[str, Any]) -> dict[str, Any]:
    """Keep the reconnect event useful without copying messages or domain payloads."""
    return {
        key: status.get(key)
        for key in (
            "contract_version",
            "trace_run_id",
            "conversation_id",
            "companion_id",
            "status",
            "accepted_at",
            "started_at",
            "updated_at",
            "completed_at",
            "attempt_count",
            "stage_timings",
            "provider_timing",
            "failure",
        )
        if key in status
    }
