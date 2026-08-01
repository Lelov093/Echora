"""Agent execution replay service."""

import uuid

from sqlalchemy import select

from app.db.models import AgentRunReplay, BadCaseInboxItem, RegressionCase, ReplayAnnotation, TraceRun, TraceStep
from app.services.persistence_helpers import create_row, default_ids, get_session, list_rows, row_to_dict


def list_replays(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, AgentRunReplay, filters, page, page_size)


def create_static_replay_from_trace(trace_run_id: uuid.UUID, data: dict | None = None) -> dict | None:
    with get_session() as session:
        trace = session.get(TraceRun, trace_run_id)
        if trace is None:
            return None
        steps = session.execute(select(TraceStep).where(TraceStep.trace_run_id == trace_run_id).order_by(TraceStep.step_order)).scalars().all()
        payload = data or {}
        replay = AgentRunReplay(
            user_id=trace.user_id,
            companion_id=trace.companion_id,
            conversation_id=trace.conversation_id,
            trace_run_id=trace.id,
            replay_type="static",
            status="ready",
            title=payload.get("title") or f"Static replay for trace {trace.id}",
            input_snapshot_json={"input_summary": trace.input_summary, **payload.get("input_snapshot_json", {})},
            trace_snapshot_json={"trace": row_to_dict(trace), "steps": [row_to_dict(step) for step in steps]},
            output_snapshot_json={"output_summary": trace.output_summary, **payload.get("output_snapshot_json", {})},
        )
        session.add(replay)
        session.commit()
        session.refresh(replay)
        return row_to_dict(replay)


def get_replay(replay_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(AgentRunReplay, replay_id)
        return row_to_dict(row) if row else None


def create_annotation(replay_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        replay = session.get(AgentRunReplay, replay_id)
        if replay is None:
            return None
        data.pop("severity", None)
        data["agent_run_replay_id"] = replay_id
        data.setdefault("user_id", replay.user_id)
        return create_row(session, ReplayAnnotation, data)


def replay_to_bad_case(replay_id: uuid.UUID, data: dict | None = None) -> dict | None:
    with get_session() as session:
        replay = session.get(AgentRunReplay, replay_id)
        if replay is None:
            return None
        payload = data or {}
        item = BadCaseInboxItem(
            user_id=replay.user_id,
            companion_id=replay.companion_id,
            source_type="replay",
            case_type=payload.get("case_type", "other"),
            severity=payload.get("severity", "medium"),
            status="open",
            title=payload.get("title") or f"Replay bad case: {replay.id}",
            description=payload.get("description"),
            trace_run_id=replay.trace_run_id,
            replay_id=replay.id,
            evidence_summary=f"replay:{replay.id}",
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return row_to_dict(item)


def replay_to_regression_case(replay_id: uuid.UUID, data: dict | None = None) -> dict | None:
    with get_session() as session:
        replay = session.get(AgentRunReplay, replay_id)
        if replay is None:
            return None
        payload = data or {}
        case = RegressionCase(
            user_id=replay.user_id,
            companion_id=replay.companion_id,
            source_replay_id=replay.id,
            title=payload.get("title") or f"Regression from replay {replay.id}",
            case_type=payload.get("case_type", "replay"),
            input_json=replay.input_snapshot_json,
            expected_behavior=payload.get("expected_behavior") or "Preserve expected behavior captured in replay.",
            expected_json=payload.get("expected_json", replay.output_snapshot_json),
            status="active",
        )
        session.add(case)
        session.commit()
        session.refresh(case)
        return row_to_dict(case)
