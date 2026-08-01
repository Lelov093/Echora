"""Agent execution file context schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


FileSourceType = Literal["upload", "local_path", "url", "manual_note", "tool_artifact"]
FileStatus = Literal["created", "processing", "ready", "failed", "archived", "deleted"]


class FileSourceCreate(BaseModel):
    source_type: FileSourceType
    name: str
    uri: str | None = None


class FileSourceRead(FileSourceCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    status: Literal["active", "archived", "deleted", "disabled"] = "active"
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FileDocumentCreate(BaseModel):
    file_source_id: uuid.UUID | None = None
    title: str
    document_type: str = "unknown"
    mime_type: str | None = None
    uri: str | None = None


class FileDocumentRead(FileDocumentCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    status: FileStatus = "created"
    summary: str | None = None
    processing_error: str | None = None
    chunk_count: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class FileChunkRead(BaseModel):
    id: uuid.UUID
    file_document_id: uuid.UUID
    chunk_index: int
    status: Literal["ready", "suppressed", "outdated", "deleted"] = "ready"
    content: str
    summary: str | None = None
    token_count: int | None = None

    model_config = {"from_attributes": True}


class FileContextUsageRead(BaseModel):
    id: uuid.UUID
    trace_run_id: uuid.UUID | None = None
    file_document_id: uuid.UUID | None = None
    file_chunk_ids: list[uuid.UUID] = Field(default_factory=list)
    usage_purpose: str = "response_generation"
    selected_for_context: bool = False
    used_in_response: bool = False
    evidence_score: float = Field(default=0.0, ge=0, le=1)
    citation_json: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"from_attributes": True}
