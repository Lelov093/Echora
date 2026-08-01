"""Echora Agent API - Application Entry Point"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.logging import setup_logging

# ── Import settings singleton first ────────────────────────────────────
from app.core.config import settings as app_settings

# ── Import all route modules ─────────────────────────────────────────
from app.api.routes import (
    system,
    companions,
    companion_workspace,
    companion_identity,
    companion_memories,
    co_presence,
    conversations,
    conversation_tasks,
    delegated_execution,
    memories,
    memory_candidates,
    growth,
    presence,
    presence_schedule,
    traces,
    settings as settings_routes,
    bad_cases,
    contexts,
    context_documents,
    relationships,
    feedback_events,
    memory_usage_events,
    memory_lifecycle_events,
    memory_timeline,
    memory_impact,
    continuity,
    memory_abstraction,
    review_batches,
    shared_memories,
    cross_companion_reviews,
    relationship_explanations,
    user_state,
    tools,
    files,
    projects,
    replays,
    bad_case_inbox,
    evaluation,
    regression,
    providers,
    runtime_configuration,
    strategy,
    evidence,
    outdated_memory,
    growth_consistency,
    shared_scenes,
    realtime_copresence,
    realtime_channel,
    companion_voice,
    realtime_multimodal_context,
    realtime_memory,
    resident_presence as resident_presence_routes,
    hard_stop,
    channel_gateway,
    companion_channel_identity,
    companion_room_channels,
    channel_message,
    channel_memory,
    channel_presence,
    channel_simulation,
    discord_bot_identities,
    channel_continuity,
    channel_trace_audit_revoke,
    affect,
    quality_feedback,
    reliability,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    setup_logging()
    from app.services import tool_runtime_service

    database_ready = True
    try:
        await asyncio.to_thread(tool_runtime_service.ensure_builtin_definitions)
    except (SQLAlchemyError, OSError) as exc:
        database_ready = False
        logging.getLogger(__name__).warning(
            "Database bootstrap is unavailable; starting the local configuration recovery surface only (%s).",
            type(exc).__name__,
        )
    scheduler_task = None
    tool_scheduler_task = None
    quality_feedback_task = None
    conversation_turn_task = None
    conversation_post_turn_task = None
    data_retention_task = None
    if database_ready and app_settings.PRESENCE_ENABLED and app_settings.PRESENCE_SCHEDULER_ENABLED:
        scheduler_task = asyncio.create_task(_run_presence_scheduler())
    if database_ready and app_settings.TOOL_SCHEDULER_ENABLED:
        tool_scheduler_task = asyncio.create_task(_run_tool_scheduler())
    if database_ready and app_settings.QUALITY_FEEDBACK_SCHEDULER_ENABLED:
        quality_feedback_task = asyncio.create_task(_run_quality_feedback_scheduler())
    if database_ready and app_settings.CONVERSATION_TURN_SCHEDULER_ENABLED:
        conversation_turn_task = asyncio.create_task(_run_conversation_turn_scheduler())
        conversation_post_turn_task = asyncio.create_task(
            _run_conversation_post_turn_scheduler()
        )
    if database_ready and app_settings.DATA_RETENTION_SCHEDULER_ENABLED:
        data_retention_task = asyncio.create_task(_run_data_retention_scheduler())
    try:
        yield
    finally:
        if scheduler_task is not None:
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        if tool_scheduler_task is not None:
            tool_scheduler_task.cancel()
            try:
                await tool_scheduler_task
            except asyncio.CancelledError:
                pass
        if quality_feedback_task is not None:
            quality_feedback_task.cancel()
            try:
                await quality_feedback_task
            except asyncio.CancelledError:
                pass
        if conversation_turn_task is not None:
            conversation_turn_task.cancel()
            try:
                await conversation_turn_task
            except asyncio.CancelledError:
                pass
        if conversation_post_turn_task is not None:
            conversation_post_turn_task.cancel()
            try:
                await conversation_post_turn_task
            except asyncio.CancelledError:
                pass
        if data_retention_task is not None:
            data_retention_task.cancel()
            try:
                await data_retention_task
            except asyncio.CancelledError:
                pass


async def _run_presence_scheduler() -> None:
    from app.services import presence_schedule_service

    while True:
        try:
            await asyncio.to_thread(presence_schedule_service.run_scheduler_tick)
        except Exception:
            # The next poll retries durable work; API startup must remain available.
            import logging

            logging.getLogger(__name__).exception("Presence scheduler tick failed")
        await asyncio.sleep(max(1, app_settings.PRESENCE_SCHEDULER_POLL_SECONDS))


async def _run_tool_scheduler() -> None:
    from app.services import (
        conversation_task_runtime_service,
        tool_runtime_service,
    )

    worker_id = f"tool-worker:{os.getpid()}"
    while True:
        try:
            await asyncio.to_thread(tool_runtime_service.execute_due_retries, worker_id=worker_id)
            await asyncio.to_thread(
                conversation_task_runtime_service.reconcile_active_tasks
            )
            await asyncio.to_thread(tool_runtime_service.deliver_due_reminders)
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Tool scheduler tick failed")
        await asyncio.sleep(max(1, app_settings.TOOL_SCHEDULER_POLL_SECONDS))


async def _run_quality_feedback_scheduler() -> None:
    from app.services import quality_feedback_service

    worker_id = f"quality-feedback-worker:{os.getpid()}"
    while True:
        try:
            await asyncio.to_thread(
                quality_feedback_service.run_scheduler_tick,
                worker_id=worker_id,
            )
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Quality feedback scheduler tick failed")
        await asyncio.sleep(max(1, app_settings.QUALITY_FEEDBACK_SCHEDULER_POLL_SECONDS))


async def _run_conversation_turn_scheduler() -> None:
    from app.services import conversation_turn_runtime_service

    worker_id = f"conversation-turn-worker:{os.getpid()}"
    while True:
        try:
            await asyncio.to_thread(
                conversation_turn_runtime_service.run_scheduler_tick,
                worker_id=worker_id,
                max_items=app_settings.CONVERSATION_TURN_SCHEDULER_BATCH_SIZE,
                lease_seconds=app_settings.CONVERSATION_TURN_SCHEDULER_LEASE_SECONDS,
            )
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Conversation turn scheduler tick failed")
        await asyncio.sleep(max(1, app_settings.CONVERSATION_TURN_SCHEDULER_POLL_SECONDS))


async def _run_conversation_post_turn_scheduler() -> None:
    from app.services import conversation_post_turn_runtime_service

    worker_id = f"conversation-post-turn-worker:{os.getpid()}"
    while True:
        try:
            await asyncio.to_thread(
                conversation_post_turn_runtime_service.run_scheduler_tick,
                worker_id=worker_id,
                max_items=app_settings.CONVERSATION_POST_TURN_SCHEDULER_BATCH_SIZE,
                lease_seconds=app_settings.CONVERSATION_POST_TURN_SCHEDULER_LEASE_SECONDS,
                max_attempts=app_settings.CONVERSATION_POST_TURN_MAX_ATTEMPTS,
            )
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Conversation Post-turn scheduler tick failed"
            )
        await asyncio.sleep(
            max(1, app_settings.CONVERSATION_POST_TURN_SCHEDULER_POLL_SECONDS)
        )


async def _run_data_retention_scheduler() -> None:
    from app.services import data_rights_deletion_service

    while True:
        try:
            await asyncio.to_thread(
                data_rights_deletion_service.process_due_deletions,
                limit=app_settings.DATA_RETENTION_SCHEDULER_BATCH_SIZE,
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Data retention scheduler tick failed"
            )
        await asyncio.sleep(
            max(60, app_settings.DATA_RETENTION_SCHEDULER_POLL_SECONDS)
        )


app = FastAPI(
    title="Echora Agent API",
    description="A Persistent Companion Agent with Cognitive Memory",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in app_settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register all routes under /api/v1 ────────────────────────────────
app.include_router(system.router, prefix="/api/v1")
app.include_router(companions.router, prefix="/api/v1")
app.include_router(companion_workspace.router, prefix="/api/v1")
app.include_router(companion_identity.router, prefix="/api/v1")
app.include_router(companion_memories.router, prefix="/api/v1")
app.include_router(co_presence.router, prefix="/api/v1")
app.include_router(delegated_execution.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(conversation_tasks.router, prefix="/api/v1")
app.include_router(context_documents.router, prefix="/api/v1")
# Continuity memory sub-routes must be registered BEFORE memories.router
# to avoid /memories/timeline being caught by /memories/{memory_id}
app.include_router(memory_timeline.router, prefix="/api/v1")
app.include_router(memory_usage_events.router, prefix="/api/v1")
app.include_router(memory_lifecycle_events.router, prefix="/api/v1")
app.include_router(memory_impact.router, prefix="/api/v1")
app.include_router(continuity.router, prefix="/api/v1")
app.include_router(memory_abstraction.router, prefix="/api/v1")
app.include_router(review_batches.router, prefix="/api/v1")
app.include_router(shared_memories.router, prefix="/api/v1")
app.include_router(cross_companion_reviews.router, prefix="/api/v1")
app.include_router(relationship_explanations.router, prefix="/api/v1")
app.include_router(user_state.router, prefix="/api/v1")
app.include_router(memories.router, prefix="/api/v1")
app.include_router(memory_candidates.router, prefix="/api/v1")
app.include_router(growth.router, prefix="/api/v1")
app.include_router(presence.router, prefix="/api/v1")
app.include_router(presence_schedule.router, prefix="/api/v1")
app.include_router(traces.router, prefix="/api/v1")
app.include_router(settings_routes.router, prefix="/api/v1")
app.include_router(bad_cases.router, prefix="/api/v1")
app.include_router(contexts.router, prefix="/api/v1")
app.include_router(relationships.router, prefix="/api/v1")
app.include_router(feedback_events.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(files.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(replays.router, prefix="/api/v1")
app.include_router(bad_case_inbox.router, prefix="/api/v1")
app.include_router(evaluation.router, prefix="/api/v1")
app.include_router(regression.router, prefix="/api/v1")
app.include_router(providers.router, prefix="/api/v1")
app.include_router(runtime_configuration.router, prefix="/api/v1")
app.include_router(strategy.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(outdated_memory.router, prefix="/api/v1")
app.include_router(growth_consistency.router, prefix="/api/v1")
app.include_router(shared_scenes.router, prefix="/api/v1")
# Deferred realtime and voice contracts remain callable for compatibility, but
# they are intentionally omitted from the public OpenAPI surface until the
# corresponding product runtime is authorized and implemented.
app.include_router(realtime_copresence.router, prefix="/api/v1", include_in_schema=False)
app.include_router(realtime_channel.router, prefix="/api/v1", include_in_schema=False)
app.include_router(companion_voice.router, prefix="/api/v1", include_in_schema=False)
app.include_router(realtime_multimodal_context.router, prefix="/api/v1", include_in_schema=False)
app.include_router(realtime_memory.router, prefix="/api/v1", include_in_schema=False)
app.include_router(resident_presence_routes.router, prefix="/api/v1", include_in_schema=False)
app.include_router(hard_stop.router, prefix="/api/v1")
app.include_router(channel_gateway.router, prefix="/api/v1")
app.include_router(companion_channel_identity.router, prefix="/api/v1")
app.include_router(companion_room_channels.router, prefix="/api/v1")
app.include_router(channel_message.router, prefix="/api/v1")
app.include_router(channel_memory.router, prefix="/api/v1")
app.include_router(channel_presence.router, prefix="/api/v1")
if app_settings.APP_ENV == "test":
    app.include_router(channel_simulation.router, prefix="/api/v1", include_in_schema=False)
app.include_router(discord_bot_identities.router, prefix="/api/v1")
app.include_router(channel_continuity.router, prefix="/api/v1")
app.include_router(channel_trace_audit_revoke.router, prefix="/api/v1")
app.include_router(affect.router, prefix="/api/v1")
app.include_router(quality_feedback.router, prefix="/api/v1")
app.include_router(reliability.router, prefix="/api/v1")
