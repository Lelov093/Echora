"""Provider, prompt, LLM call, and fallback API routes."""

import uuid

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.schemas.common import err, ok, paginated_ok
from app.services import provider_service

router = APIRouter(tags=["Providers"])


@router.get("/llm-provider-configs")
def list_provider_configs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str | None = None):
    result = provider_service.list_providers(page, page_size, status=status)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/llm-provider-configs")
def create_provider_config(body: dict):
    return JSONResponse(
        status_code=409,
        content=err(
            "PROVIDER_METADATA_WRITE_RETIRED",
            "Provider runtime configuration is owned by /runtime-configuration.",
        ),
    )


@router.patch("/llm-provider-configs/{provider_id}")
def update_provider_config(provider_id: str, body: dict):
    return JSONResponse(
        status_code=409,
        content=err(
            "PROVIDER_METADATA_WRITE_RETIRED",
            "Provider runtime configuration is owned by /runtime-configuration.",
        ),
    )


@router.get("/llm-model-configs")
def list_model_configs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), provider_config_id: str | None = None):
    result = provider_service.list_models(page, page_size, provider_config_id=uuid.UUID(provider_config_id) if provider_config_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/llm-model-configs")
def create_model_config(body: dict):
    return JSONResponse(
        status_code=409,
        content=err(
            "PROVIDER_METADATA_WRITE_RETIRED",
            "Model runtime configuration is owned by /runtime-configuration.",
        ),
    )


@router.get("/prompt-versions")
def list_prompt_versions(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), prompt_key: str | None = None):
    result = provider_service.list_prompt_versions(page, page_size, prompt_key=prompt_key)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/prompt-versions")
def create_prompt_version(body: dict):
    return ok(provider_service.create_prompt_version(body))


@router.post("/prompt-versions/{prompt_version_id}/activate")
def activate_prompt_version(prompt_version_id: str):
    row = provider_service.activate_prompt_version(uuid.UUID(prompt_version_id))
    return ok(row) if row else err("NOT_FOUND", "Prompt version not found")


@router.get("/llm-call-records")
def list_llm_call_records(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), trace_run_id: str | None = None):
    result = provider_service.list_llm_calls(page, page_size, trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/llm-call-records")
def create_llm_call_record(body: dict):
    return ok(provider_service.create_llm_call(body))


@router.get("/fallback-events")
def list_fallback_events(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), trace_run_id: str | None = None):
    result = provider_service.list_fallback_events(page, page_size, trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/fallback-events")
def create_fallback_event(body: dict):
    return ok(provider_service.create_fallback_event(body))
