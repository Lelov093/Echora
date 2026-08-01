"""Evidence-grounded Companion context document API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok
from app.schemas.product_crud import (
    ContextDocumentCorrectionRequest,
    ContextDocumentRefreshRequest,
    ContextDocumentVersionRequest,
)
from app.services import context_document_service


router = APIRouter(prefix="/companions/{companion_id}/context-documents", tags=["Context Documents"])


def _error(exc: context_document_service.ContextDocumentError):
    return err(exc.code, exc.message, exc.details)


@router.get("")
def list_context_documents(
    companion_id: str,
    kind: str | None = Query(None),
    include_history: bool = Query(False),
):
    try:
        return ok(context_document_service.list_context_documents(
            uuid.UUID(companion_id), kind=kind, include_history=include_history,
        ))
    except context_document_service.ContextDocumentError as exc:
        return _error(exc)


@router.post("/refresh")
def refresh_context_documents(companion_id: str, body: ContextDocumentRefreshRequest):
    try:
        return ok(context_document_service.refresh_context_documents(
            user_id=body.user_id,
            companion_id=uuid.UUID(companion_id),
            conversation_id=body.conversation_id,
            force=body.force,
            reason=body.reason,
        ))
    except context_document_service.ContextDocumentError as exc:
        return _error(exc)


@router.patch("/{document_id}")
def correct_context_document(
    companion_id: str,
    document_id: str,
    body: ContextDocumentCorrectionRequest,
):
    try:
        return ok(context_document_service.correct_context_document(
            uuid.UUID(document_id), uuid.UUID(companion_id),
            expected_version=body.expected_version,
            content=body.content,
            reason=body.reason,
        ))
    except context_document_service.ContextDocumentError as exc:
        return _error(exc)


@router.post("/{document_id}/restore")
def restore_context_document(
    companion_id: str,
    document_id: str,
    body: ContextDocumentVersionRequest,
):
    try:
        return ok(context_document_service.restore_context_document(
            uuid.UUID(document_id), uuid.UUID(companion_id),
            expected_version=body.expected_version,
            reason=body.reason,
        ))
    except context_document_service.ContextDocumentError as exc:
        return _error(exc)


@router.post("/{document_id}/invalidate")
def invalidate_context_document(
    companion_id: str,
    document_id: str,
    body: ContextDocumentVersionRequest,
):
    try:
        return ok(context_document_service.invalidate_context_document(
            uuid.UUID(document_id), uuid.UUID(companion_id),
            expected_version=body.expected_version,
            reason=body.reason,
        ))
    except context_document_service.ContextDocumentError as exc:
        return _error(exc)
