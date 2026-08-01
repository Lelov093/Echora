"""Agent execution provider, prompt, LLM call, and fallback services."""

import uuid

from app.db.models import FallbackEvent, LlmCallRecord, LlmModelConfig, LlmProviderConfig, PromptVersion
from app.services.persistence_helpers import create_row, default_ids, get_session, list_rows, update_row

SECRET_KEYS = {"api_key", "apikey", "secret", "token", "access_token", "refresh_token"}


def _scrub_provider_payload(data: dict) -> dict:
    cleaned = {k: v for k, v in data.items() if k.lower() not in SECRET_KEYS and k != "priority"}
    config = dict(cleaned.get("config_json") or {})
    cleaned["config_json"] = {k: v for k, v in config.items() if k.lower() not in SECRET_KEYS}
    return cleaned


def create_provider(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        payload = _scrub_provider_payload(data)
        payload.setdefault("user_id", uid)
        payload.setdefault("companion_id", cid)
        payload.setdefault("provider_type", "llm")
        payload.setdefault("status", "enabled")
        return create_row(session, LlmProviderConfig, payload)


def list_providers(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, LlmProviderConfig, filters, page, page_size)


def update_provider(provider_id: uuid.UUID, data: dict) -> dict | None:
    with get_session() as session:
        return update_row(session, LlmProviderConfig, provider_id, _scrub_provider_payload(data))


def create_model(data: dict) -> dict:
    with get_session() as session:
        data.setdefault("model_role", "response_generation")
        data.setdefault("status", "enabled")
        return create_row(session, LlmModelConfig, data)


def list_models(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, LlmModelConfig, filters, page, page_size)


def create_prompt_version(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        data.setdefault("status", "draft")
        return create_row(session, PromptVersion, data)


def list_prompt_versions(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, PromptVersion, filters, page, page_size)


def activate_prompt_version(prompt_version_id: uuid.UUID) -> dict | None:
    with get_session() as session:
        row = session.get(PromptVersion, prompt_version_id)
        if row is None:
            return None
        for prompt in session.query(PromptVersion).filter(PromptVersion.prompt_key == row.prompt_key).all():
            prompt.status = "archived" if prompt.id != row.id and prompt.status == "active" else prompt.status
        row.status = "active"
        session.commit()
        session.refresh(row)
        from app.services.persistence_helpers import row_to_dict

        return row_to_dict(row)


def create_llm_call(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        data.setdefault("status", "queued")
        data.setdefault("purpose", "response_generation")
        data.pop("request_json", None)
        data.pop("response_json", None)
        data.pop("cost_estimate", None)
        return create_row(session, LlmCallRecord, data)


def list_llm_calls(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, LlmCallRecord, filters, page, page_size)


def create_fallback_event(data: dict) -> dict:
    with get_session() as session:
        uid, cid = default_ids(session)
        data.setdefault("user_id", uid)
        data.setdefault("companion_id", cid)
        data.setdefault("status", "recorded")
        data.pop("fallback_chain_json", None)
        data.pop("resolved_at", None)
        return create_row(session, FallbackEvent, data)


def list_fallback_events(page: int = 1, page_size: int = 20, **filters) -> dict:
    with get_session() as session:
        return list_rows(session, FallbackEvent, filters, page, page_size)
