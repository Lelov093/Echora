"""Generate and govern versioned summaries derived from confirmed Chronicle events."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import settings
from app.db.models.chronicle_summary import CompanionChronicleSummary
from app.db.models.companion import Companion


SUMMARY_VERSION = "chronicle-summary.v1"
_engine = None
_provider: OpenAICompatibleProvider | None = None


class ChronicleSummaryError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def _get_provider() -> OpenAICompatibleProvider:
    global _provider
    if _provider is None:
        _provider = OpenAICompatibleProvider()
    return _provider


def generate_summary(companion_id: uuid.UUID, events: list[dict[str, Any]], correction_note: str | None = None) -> dict:
    confirmed = [item for item in events if _eligible(item)]
    if len(confirmed) < 3:
        raise ChronicleSummaryError("CHRONICLE_EVIDENCE_INSUFFICIENT", "At least three confirmed Chronicle events are required.")
    confirmed = confirmed[:60]
    provider = _get_provider()
    system = """Write a concise Chinese phase summary of one AI Companion and user's shared history.
Use only supplied confirmed event summaries. Return exactly one JSON object with title, summary, highlights.
highlights is an array of 2 to 5 short strings. Do not invent intimacy, dependency, consent, identity,
private message text, or facts. Preserve corrections and reversals instead of smoothing them away.
Do not mention another Companion, shared/channel payload, numeric relationship scores, or implementation details."""
    prompt = json.dumps({
        "events": [{"ref": item["id"], "kind": item["kind"], "status": item.get("review_status"), "date": str(item.get("occurred_at")), "summary": item["summary"][:500]} for item in confirmed],
        "correction_note": (correction_note or "")[:500],
    }, ensure_ascii=False)
    try:
        result = provider.generate(system, prompt, context={"temperature": 0.1, "max_tokens": 900})
        payload = _parse(result.get("content", ""))
    except LLMProviderError as exc:
        raise ChronicleSummaryError(exc.code, "Chronicle summary provider is unavailable.") from exc
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ChronicleSummaryError("CHRONICLE_SUMMARY_INVALID_RESPONSE", "Chronicle summary response failed validation.") from exc
    dates = [_aware(item["occurred_at"]) for item in confirmed]
    with Session(_get_engine()) as session:
        companion = session.execute(select(Companion).where(Companion.id == companion_id, Companion.deleted_at.is_(None)).with_for_update()).scalar_one_or_none()
        if companion is None:
            raise ChronicleSummaryError("COMPANION_NOT_FOUND", "Companion not found.")
        previous = session.execute(select(CompanionChronicleSummary).where(
            CompanionChronicleSummary.companion_id == companion_id,
            CompanionChronicleSummary.status == "active",
        ).order_by(CompanionChronicleSummary.version.desc()).with_for_update()).scalars().first()
        next_version = int(session.execute(select(func.max(CompanionChronicleSummary.version)).where(CompanionChronicleSummary.companion_id == companion_id)).scalar() or 0) + 1
        if previous:
            previous.status = "superseded"
        row = CompanionChronicleSummary(
            user_id=companion.user_id, companion_id=companion.id, version=next_version, status="active",
            title=payload["title"], summary=payload["summary"], highlights_json=payload["highlights"],
            source_event_refs=[str(item["id"]) for item in confirmed], period_start=min(dates), period_end=max(dates),
            generated_by_provider=result.get("provider", provider.provider_name), generated_by_model=result.get("model"),
            supersedes_summary_id=previous.id if previous else None,
            metadata_={"contract_version": SUMMARY_VERSION, "correction_note_supplied": bool(correction_note)},
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _dict(row)


def list_summaries(companion_id: uuid.UUID, limit: int = 20) -> list[dict]:
    with Session(_get_engine()) as session:
        rows = session.execute(select(CompanionChronicleSummary).where(
            CompanionChronicleSummary.companion_id == companion_id,
        ).order_by(CompanionChronicleSummary.version.desc()).limit(limit)).scalars()
        return [_dict(row) for row in rows]


def invalidate_summary(companion_id: uuid.UUID, summary_id: uuid.UUID, reason: str) -> dict:
    with Session(_get_engine()) as session:
        row = session.execute(select(CompanionChronicleSummary).where(
            CompanionChronicleSummary.id == summary_id,
            CompanionChronicleSummary.companion_id == companion_id,
        ).with_for_update()).scalar_one_or_none()
        if row is None:
            raise ChronicleSummaryError("CHRONICLE_SUMMARY_NOT_FOUND", "Chronicle summary not found.")
        if row.status == "invalidated":
            return _dict(row)
        row.status = "invalidated"
        row.invalidated_at = datetime.now(timezone.utc)
        row.invalidation_reason = reason[:500]
        session.commit(); session.refresh(row)
        return _dict(row)


def _eligible(item: dict[str, Any]) -> bool:
    if item.get("kind") == "relationship_pending":
        return False
    status = item.get("review_status")
    if item.get("kind") == "relationship":
        return status in {"committed", "corrected", "reverted"}
    if item.get("kind") == "growth":
        return status in {"committed", "reverted"}
    return status not in {"pending_review", "candidate", "rejected"}


def _parse(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("summary did not return JSON")
    data = json.loads(cleaned[start:end + 1])
    if not isinstance(data, dict) or set(data) != {"title", "summary", "highlights"}:
        raise ValueError("invalid summary contract")
    highlights = data.get("highlights")
    if not isinstance(highlights, list) or not 2 <= len(highlights) <= 5:
        raise ValueError("invalid summary highlights")
    return {"title": str(data["title"])[:240], "summary": str(data["summary"])[:3000], "highlights": [str(item)[:300] for item in highlights]}


def _dict(row: CompanionChronicleSummary) -> dict:
    return {"id": str(row.id), "version": row.version, "status": row.status, "title": row.title, "summary": row.summary,
            "highlights": row.highlights_json or [], "source_event_refs": row.source_event_refs or [],
            "period_start": row.period_start.isoformat(), "period_end": row.period_end.isoformat(),
            "provider": row.generated_by_provider, "model": row.generated_by_model,
            "invalidated_at": row.invalidated_at.isoformat() if row.invalidated_at else None,
            "invalidation_reason": row.invalidation_reason, "created_at": row.created_at.isoformat() if row.created_at else None}


def _aware(value: Any) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
