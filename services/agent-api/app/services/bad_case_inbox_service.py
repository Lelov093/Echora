"""Agent execution bad case inbox service."""

import uuid

from app.db.models import BadCase, BadCaseInboxItem, BadCaseLink, BadCaseTriageEvent, RegressionCase
from app.services.persistence_helpers import create_row, default_ids, get_session, list_rows, row_to_dict, update_row


def list_items(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, BadCaseInboxItem, filters, page, page_size)


def create_item(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        data.setdefault("status", "open")
        return create_row(session, BadCaseInboxItem, data)


def get_item(item_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(BadCaseInboxItem, item_id)
        return row_to_dict(row) if row else None


def update_item(item_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        return update_row(session, BadCaseInboxItem, item_id, data)


def triage_item(item_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        item = session.get(BadCaseInboxItem, item_id)
        if item is None:
            return None
        previous = item.status
        item.status = data.get("new_status", item.status)
        event = BadCaseTriageEvent(
            bad_case_inbox_item_id=item.id,
            user_id=item.user_id,
            previous_status=previous,
            new_status=item.status,
            action=data.get("action", "triage"),
            reason=data.get("reason") or data.get("note"),
        )
        session.add(event)
        session.commit()
        session.refresh(item)
        return row_to_dict(item)


def create_link(item_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        item = session.get(BadCaseInboxItem, item_id)
        if item is None:
            return None
        data.pop("linked_uri", None)
        data["bad_case_inbox_item_id"] = item.id
        return create_row(session, BadCaseLink, data)


def convert_to_bad_case(item_id: uuid.UUID, data: dict | None = None) -> dict | None:
    with get_session() as session:
        item = session.get(BadCaseInboxItem, item_id)
        if item is None:
            return None
        payload = data or {}
        bad_case = BadCase(
            user_id=item.user_id,
            companion_id=item.companion_id,
            trace_run_id=item.trace_run_id,
            type="other",
            title=payload.get("title") or item.title,
            description=payload.get("description") or item.description,
            severity=payload.get("severity") or item.severity,
            status="open",
            bad_case_inbox_item_id=item.id,
            evidence_links=[{"type": "bad_case_inbox_item", "id": str(item.id)}],
        )
        session.add(bad_case)
        session.flush()
        item.status = "resolved"
        session.commit()
        session.refresh(bad_case)
        return row_to_dict(bad_case)


def convert_to_regression_case(item_id: uuid.UUID, data: dict | None = None) -> dict | None:
    with get_session() as session:
        item = session.get(BadCaseInboxItem, item_id)
        if item is None:
            return None
        payload = data or {}
        case = RegressionCase(
            user_id=item.user_id,
            companion_id=item.companion_id,
            source_bad_case_id=item.id,
            source_replay_id=item.replay_id,
            title=payload.get("title") or f"Regression from bad case {item.id}",
            case_type=payload.get("case_type", "bad_case"),
            input_json=payload.get("input_json", {"bad_case_inbox_item_id": str(item.id)}),
            expected_behavior=payload.get("expected_behavior") or "Do not reproduce the bad case behavior.",
            expected_json=payload.get("expected_json", {}),
            status="active",
        )
        session.add(case)
        session.flush()
        item.created_regression_case_id = case.id
        item.status = "converted_to_regression"
        session.commit()
        session.refresh(case)
        return row_to_dict(case)
