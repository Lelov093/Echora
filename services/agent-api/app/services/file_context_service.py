"""Agent execution file context API service."""

import uuid

from sqlalchemy import select

from app.db.models import FileChunk, FileContextUsage, FileDocument, FileSource
from app.services.persistence_helpers import create_row, default_ids, get_session, list_rows, row_to_dict, update_row


def list_file_sources(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, FileSource, filters, page, page_size)


def create_file_source(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        return create_row(session, FileSource, data)


def list_file_documents(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, FileDocument, filters, page, page_size)


def create_file_document(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        return create_row(session, FileDocument, data)


def get_file_document(document_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(FileDocument, document_id)
        return row_to_dict(row) if row else None


def process_file_document(document_id: uuid.UUID, data: dict | None = None) -> dict | None:
    with get_session() as session:
        doc = session.get(FileDocument, document_id)
        if doc is None:
            return None
        content = (data or {}).get("content") or doc.summary or doc.title
        existing = session.execute(select(FileChunk).where(FileChunk.file_document_id == doc.id)).scalars().first()
        if existing is None and content:
            session.add(FileChunk(
                file_document_id=doc.id,
                user_id=doc.user_id,
                companion_id=doc.companion_id,
                chunk_index=0,
                status="ready",
                content=content,
                summary=(data or {}).get("summary"),
            ))
            doc.chunk_count = 1
        doc.status = "ready"
        doc.processing_error = None
        if (data or {}).get("summary"):
            doc.summary = data["summary"]
        session.commit()
        session.refresh(doc)
        return row_to_dict(doc)


def list_file_chunks(document_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as session:
        return list_rows(session, FileChunk, {"file_document_id": document_id}, page, page_size)


def search_file_chunks(query: str | None = None, companion_id: uuid.UUID | None = None, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as session:
        stmt = select(FileChunk)
        if companion_id:
            stmt = stmt.where(FileChunk.companion_id == companion_id)
        if query:
            stmt = stmt.where(FileChunk.content.ilike(f"%{query}%"))
        total = len(session.execute(stmt).scalars().all())
        items = session.execute(
            stmt.order_by(FileChunk.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        ).scalars().all()
        return {"items": [row_to_dict(item) for item in items], "total": total}


def list_file_context_usages(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, FileContextUsage, filters, page, page_size)


def get_file_context_usage(usage_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(FileContextUsage, usage_id)
        return row_to_dict(row) if row else None
