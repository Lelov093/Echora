"""Conversation & Message API routes."""

import uuid

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.schemas.common import ok, paginated_ok, err
from app.schemas.conversation_crud import (
    ConversationCreateRequest,
    ConversationUpdateRequest,
    ConversationTurnRetryRequest,
    ConversationTurnStartRequest,
    ConversationTurnCancelRequest,
    ConversationPermanentDeleteRequest,
    LifecycleReasonRequest,
    MessageCorrectionRequest,
    MessageCreateRequest,
)
from app.services import (
    conversation_application_service,
    conversation_deletion_service,
    conversation_evidence_service,
    conversation_service,
    conversation_turn_event_service,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("")
def list_conversations(companion_id: str = Query(...), status: str | None = Query(None),
                       page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = conversation_service.list_conversations(
        uuid.UUID(companion_id), status, page, page_size,
    )
    items = [conversation_service._conv_dict(c) for c in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("")
def create_conversation(body: ConversationCreateRequest):
    try:
        conv = conversation_service.create_conversation(body.model_dump())
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(conversation_service._conv_dict(conv))


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str, companion_id: str = Query(...)):
    c = conversation_service.get_conversation(uuid.UUID(conversation_id), uuid.UUID(companion_id))
    if not c:
        return err("CONVERSATION_NOT_FOUND", "Conversation not found")
    return ok(conversation_service._conv_dict(c))


@router.get("/{conversation_id}/messages/{message_id}/evidence")
def get_conversation_message_evidence(
    conversation_id: str,
    message_id: str,
    companion_id: str = Query(...),
):
    """Return a bounded, refresh-recoverable evidence projection for one assistant message."""
    try:
        result = conversation_evidence_service.get_message_evidence(
            uuid.UUID(conversation_id),
            uuid.UUID(message_id),
            uuid.UUID(companion_id),
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.patch("/{conversation_id}")
def update_conversation(
    conversation_id: str,
    body: ConversationUpdateRequest,
    companion_id: str = Query(...),
):
    try:
        c = conversation_service.update_conversation(
            uuid.UUID(conversation_id), uuid.UUID(companion_id), body.model_dump(exclude_none=True)
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    if not c:
        return err("CONVERSATION_NOT_FOUND", "Conversation not found")
    return ok(conversation_service._conv_dict(c))


@router.post("/{conversation_id}/archive")
def archive_conversation(conversation_id: str, companion_id: str = Query(...)):
    c = conversation_service.set_conversation_archived(
        uuid.UUID(conversation_id), uuid.UUID(companion_id), True,
    )
    if not c:
        return err("CONVERSATION_NOT_FOUND", "Conversation not found")
    return ok(conversation_service._conv_dict(c))


@router.post("/{conversation_id}/restore")
def restore_conversation(conversation_id: str, companion_id: str = Query(...)):
    c = conversation_service.set_conversation_archived(
        uuid.UUID(conversation_id), uuid.UUID(companion_id), False,
    )
    if not c:
        return err("CONVERSATION_NOT_FOUND", "Conversation not found")
    return ok(conversation_service._conv_dict(c))


@router.get("/{conversation_id}/deletion-preview")
def preview_conversation_deletion(
    conversation_id: str,
    companion_id: str = Query(...),
):
    try:
        result = conversation_deletion_service.preview_conversation_deletion(
            uuid.UUID(conversation_id),
            uuid.UUID(companion_id),
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.delete("/{conversation_id}")
def permanently_delete_conversation(
    conversation_id: str,
    body: ConversationPermanentDeleteRequest,
    companion_id: str = Query(...),
):
    try:
        result = conversation_deletion_service.permanently_delete_conversation(
            uuid.UUID(conversation_id),
            uuid.UUID(companion_id),
            confirmation_phrase=body.confirmation_phrase,
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.get("/{conversation_id}/messages")
def list_messages(
    conversation_id: str,
    companion_id: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    order: str = Query("asc", pattern="^(asc|desc)$"),
):
    if not conversation_service.get_conversation(uuid.UUID(conversation_id), uuid.UUID(companion_id)):
        return err("CONVERSATION_NOT_FOUND", "Conversation not found")
    result = conversation_service.list_messages(
        uuid.UUID(conversation_id),
        uuid.UUID(companion_id),
        page,
        page_size,
        descending=order == "desc",
    )
    items = [conversation_service._msg_dict(m) for m in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/{conversation_id}/messages")
def create_message(
    conversation_id: str,
    body: MessageCreateRequest,
    companion_id: str = Query(...),
):
    conversation = conversation_service.get_conversation(
        uuid.UUID(conversation_id), uuid.UUID(companion_id), include_archived=False,
    )
    if not conversation:
        return err("CONVERSATION_NOT_FOUND", "Active Conversation not found")
    payload = body.model_dump()
    payload.update({
        "user_id": conversation.user_id,
        "companion_id": conversation.companion_id,
        "conversation_id": conversation.id,
        "role": "user",
    })
    try:
        m = conversation_service.create_message(payload)
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(conversation_service._msg_dict(m))


@router.get("/{conversation_id}/messages/{message_id}")
def get_message(conversation_id: str, message_id: str, companion_id: str = Query(...)):
    message = conversation_service.get_message(
        uuid.UUID(conversation_id), uuid.UUID(message_id), uuid.UUID(companion_id),
    )
    if not message:
        return err("MESSAGE_NOT_FOUND", "Message not found")
    return ok(conversation_service._msg_dict(message))


@router.patch("/{conversation_id}/messages/{message_id}")
def correct_message(
    conversation_id: str,
    message_id: str,
    body: MessageCorrectionRequest,
    companion_id: str = Query(...),
):
    message = conversation_service.correct_user_message(
        uuid.UUID(conversation_id), uuid.UUID(message_id), uuid.UUID(companion_id),
        body.content.strip(), body.reason,
    )
    if not message:
        return err("MESSAGE_NOT_CORRECTABLE", "Only an existing user message can be corrected")
    return ok(conversation_service._msg_dict(message))


@router.post("/{conversation_id}/messages/{message_id}/withdraw")
def withdraw_message(
    conversation_id: str,
    message_id: str,
    body: LifecycleReasonRequest | None = None,
    companion_id: str = Query(...),
):
    message = conversation_service.withdraw_user_message(
        uuid.UUID(conversation_id), uuid.UUID(message_id), uuid.UUID(companion_id),
        body.reason if body else None,
    )
    if not message:
        return err("MESSAGE_NOT_WITHDRAWABLE", "Only an existing user message can be withdrawn")
    return ok({"id": str(message.id), "withdrawn": True})


@router.post("/{conversation_id}/run")
def run_conversation(conversation_id: str, body: dict):
    """Run one validated Companion turn through the application service."""
    companion_id = body.get("companion_id")
    content = body.get("content", "")
    mode_key = body.get("mode_key")
    idempotency_key = body.get("idempotency_key")
    reasoning_mode = body.get("reasoning_mode")
    try:
        result = conversation_service.run_conversation(
            uuid.UUID(conversation_id),
            uuid.UUID(companion_id) if companion_id else None,
            None,
            content,
            mode_key,
            idempotency_key,
            reasoning_mode,
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    run_errors = result.pop("_run_errors", [])
    provider_error = next(
        (item for item in run_errors if item.get("step") == "response_generation"),
        None,
    )
    if provider_error:
        details = provider_error.get("details") or {}
        return err(
            "CONVERSATION_PROVIDER_UNAVAILABLE",
            "真实模型暂时无法回应。本次没有生成或保存模拟回复，你的输入已保留。",
            {
                "trace_run_id": result.get("trace", {}).get("trace_run_id"),
                "user_message_persisted": bool(result.get("user_message")),
                "provider_mode": result.get("provider_mode"),
                "provider_error_code": details.get("provider_error_code") or provider_error.get("code"),
                "status_code": details.get("status_code"),
                "retryable": True,
            },
        )
    return ok(result)


@router.post("/{conversation_id}/turns", status_code=202)
def start_conversation_turn(conversation_id: str, body: ConversationTurnStartRequest):
    """Durably accept one Web turn without blocking on Provider generation."""
    try:
        result = conversation_application_service.accept_conversation_turn(
            conversation_application_service.ConversationTurnCommand(
                conversation_id=uuid.UUID(conversation_id),
                requested_companion_id=body.companion_id,
                content=body.content,
                mode_key=body.mode_key,
                reasoning_mode=body.reasoning_mode,
                idempotency_key=body.idempotency_key,
                continuation_of_trace_run_id=body.continuation_of_trace_run_id,
                transport_mode="async_web",
            )
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.get("/{conversation_id}/turns/current")
def get_latest_conversation_turn_status(
    conversation_id: str,
    companion_id: str = Query(...),
):
    """Recover the latest async Web turn after a page refresh."""
    try:
        result = conversation_application_service.get_latest_conversation_turn_status(
            uuid.UUID(conversation_id),
            uuid.UUID(companion_id),
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.get("/{conversation_id}/turns/{trace_run_id}")
def get_conversation_turn_status(
    conversation_id: str,
    trace_run_id: str,
    companion_id: str = Query(...),
):
    """Poll one accepted Web turn inside its Companion scope."""
    try:
        result = conversation_application_service.get_conversation_turn_status(
            uuid.UUID(conversation_id),
            uuid.UUID(trace_run_id),
            uuid.UUID(companion_id),
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.get("/{conversation_id}/turns/{trace_run_id}/events")
def stream_conversation_turn_events(
    conversation_id: str,
    trace_run_id: str,
    companion_id: str = Query(...),
):
    """Stream transient generated text and lifecycle events for one scoped Web turn."""
    try:
        status = conversation_application_service.get_conversation_turn_status(
            uuid.UUID(conversation_id),
            uuid.UUID(trace_run_id),
            uuid.UUID(companion_id),
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return StreamingResponse(
        conversation_turn_event_service.iter_sse_events(uuid.UUID(trace_run_id), status),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{conversation_id}/turns/{trace_run_id}/cancel")
def cancel_conversation_turn(
    conversation_id: str,
    trace_run_id: str,
    body: ConversationTurnCancelRequest,
):
    """Request a durable stop without overwriting an already persisted response."""
    try:
        result = conversation_application_service.cancel_conversation_turn(
            uuid.UUID(conversation_id),
            uuid.UUID(trace_run_id),
            body.companion_id,
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.post("/{conversation_id}/turns/{trace_run_id}/recover-effects")
def recover_conversation_effects(conversation_id: str, trace_run_id: str, body: dict | None = None):
    """Recover failed no-ref Post-turn Effects without rerunning the Provider response."""
    payload = body or {}
    companion_id = payload.get("companion_id")
    try:
        result = conversation_application_service.recover_conversation_turn_effects(
            uuid.UUID(conversation_id),
            uuid.UUID(trace_run_id),
            uuid.UUID(companion_id) if companion_id else None,
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.post("/{conversation_id}/turns/{trace_run_id}/retry-provider")
def retry_conversation_provider(
    conversation_id: str,
    trace_run_id: str,
    body: ConversationTurnRetryRequest,
):
    """Retry a failed Provider attempt without persisting another user message."""
    try:
        result = conversation_application_service.retry_failed_provider_turn(
            uuid.UUID(conversation_id),
            uuid.UUID(trace_run_id),
            body.companion_id,
        )
    except conversation_service.ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    run_errors = result.pop("_run_errors", [])
    provider_error = next(
        (item for item in run_errors if item.get("step") == "response_generation"),
        None,
    )
    if provider_error:
        details = provider_error.get("details") or {}
        return err(
            "CONVERSATION_PROVIDER_UNAVAILABLE",
            "真实模型仍然无法回应。没有创建重复用户消息，你可以稍后再次重试。",
            {
                "trace_run_id": result.get("trace", {}).get("trace_run_id"),
                "user_message_persisted": True,
                "provider_mode": result.get("provider_mode"),
                "provider_error_code": details.get("provider_error_code") or provider_error.get("code"),
                "status_code": details.get("status_code"),
                "retryable": True,
            },
        )
    return ok(result)
