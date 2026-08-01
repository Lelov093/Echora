"""File context API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import file_context_service

router = APIRouter(tags=["Files"])


@router.get("/file-sources")
def list_file_sources(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), companion_id: str | None = None):
    result = file_context_service.list_file_sources(page, page_size, companion_id=uuid.UUID(companion_id) if companion_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/file-sources")
def create_file_source(body: dict):
    return ok(file_context_service.create_file_source(body))


@router.get("/file-documents")
def list_file_documents(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), companion_id: str | None = None):
    result = file_context_service.list_file_documents(page, page_size, companion_id=uuid.UUID(companion_id) if companion_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/file-documents")
def create_file_document(body: dict):
    return ok(file_context_service.create_file_document(body))


@router.get("/file-documents/{document_id}")
def get_file_document(document_id: str):
    row = file_context_service.get_file_document(uuid.UUID(document_id))
    return ok(row) if row else err("NOT_FOUND", "File document not found")


@router.post("/file-documents/{document_id}/process")
def process_file_document(document_id: str, body: dict | None = None):
    row = file_context_service.process_file_document(uuid.UUID(document_id), body)
    return ok(row) if row else err("NOT_FOUND", "File document not found")


@router.get("/file-documents/{document_id}/chunks")
def list_file_chunks(document_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = file_context_service.list_file_chunks(uuid.UUID(document_id), page, page_size)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/file-chunks/search")
def search_file_chunks(q: str | None = None, companion_id: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = file_context_service.search_file_chunks(q, uuid.UUID(companion_id) if companion_id else None, page, page_size)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/file-context-usages")
def list_file_context_usages(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), trace_run_id: str | None = None):
    result = file_context_service.list_file_context_usages(page, page_size, trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/file-context-usages/{usage_id}")
def get_file_context_usage(usage_id: str):
    row = file_context_service.get_file_context_usage(uuid.UUID(usage_id))
    return ok(row) if row else err("NOT_FOUND", "File context usage not found")
