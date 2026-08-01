"""Channel Gateway Discord multi-bot adapter contract.

This module is the Discord provider implementation boundary. It loads bot
metadata from DISCORD_BOT_REGISTRY_PATH and resolves token_secret_ref
internally, but never returns raw tokens to callers.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "api_key", "authorization", "credential", "raw")

_ENV_LOADED = False


def _ensure_env_loaded() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    try:
        from dotenv import load_dotenv
        root = _project_root()
        env_path = root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=str(env_path), override=False)
    except ImportError:
        pass


@dataclass(frozen=True)
class DiscordBotRegistryItem:
    bot_key: str
    bot_display_name: str
    token_secret_ref: str | None
    enabled: bool
    companion_id: str | None = None
    provider_bot_id: str | None = None
    bot_user_id: str | None = None
    application_id: str | None = None
    app_id: str | None = None
    public_key: str | None = None
    oauth2_url: str | None = None
    guild_id: str | None = None
    default_channel_id: str | None = None
    memory_review_channel_id: str | None = None
    audit_log_channel_id: str | None = None
    status: str | None = None
    default_channel_ref_hash: str | None = None


class DiscordMultiBotAdapter:
    provider_key = "discord"
    provider_kind = "discord"

    def registry_status(self) -> dict[str, Any]:
        registry = _load_registry()
        items = [_item_status(item, registry) for item in registry["bots"]]
        return {
            "provider_key": self.provider_key,
            "provider_kind": self.provider_kind,
            "registry_configured": bool(registry["path"]),
            "registry_status": registry["status"],
            "bot_count": len(items),
            "supports_multi_bot": True,
            "real_provider_call": False,
            "bots": items,
        }

    def normalize_inbound(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        item, registry = _resolve_item(payload.get("bot_key"))
        if item is None:
            return None
        credential = _resolve_credential(item, registry)
        return {
            "provider_key": self.provider_key,
            "normalized_event_type": payload.get("event_type") or "message_create",
            "bot_key": item.bot_key,
            "provider_bot_id": item.provider_bot_id,
            "companion_id": item.companion_id,
            "bot_user_id": item.bot_user_id,
            "credential_status": credential["status"],
            "safe_payload": _safe_json(payload.get("payload")),
            "raw_payload_storage_allowed": False,
            "real_provider_call": False,
        }

    def prepare_outbound(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        item, registry = _resolve_item(payload.get("bot_key"))
        if item is None:
            return None
        credential = _resolve_credential(item, registry)
        status = "ready" if credential["status"] == "configured" and item.enabled else credential["status"]
        return {
            "provider_key": self.provider_key,
            "delivery_abstraction": "discord_message_create",
            "bot_key": item.bot_key,
            "provider_bot_id": item.provider_bot_id,
            "companion_id": item.companion_id,
            "bot_user_id": item.bot_user_id,
            "credential_status": credential["status"],
            "delivery_status": "prepared" if status == "ready" else "blocked",
            "blocked_reason": None if status == "ready" else status,
            "safe_delivery_payload": {
                "channel_ref_hash": payload.get("channel_ref_hash") or item.default_channel_ref_hash,
                "message_summary": str(payload.get("message_summary") or "Discord outbound message")[:500],
                **_safe_json(payload.get("payload")),
            },
            "raw_payload_storage_allowed": False,
            "real_provider_call": False,
        }

    def test_connection(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        item, registry = _resolve_item(payload.get("bot_key"))
        if item is None:
            return None
        credential = _resolve_credential(item, registry)
        if not item.enabled:
            connection_status = "disabled"
        elif credential["status"] != "configured":
            connection_status = credential["status"]
        else:
            connection_status = "contract_verified"
        return {
            "provider_key": self.provider_key,
            "bot_key": item.bot_key,
            "connection_status": connection_status,
            "bot_user_id": item.bot_user_id,
            "application_id": item.application_id,
            "real_provider_call": False,
            "raw_token_returned": False,
        }

    def map_failure(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_key": self.provider_key,
            "bot_key": payload.get("bot_key"),
            "failure_type": payload.get("failure_type") or "provider_error",
            "failure_status": "recorded",
            "safe_error_summary": str(payload.get("safe_error_summary") or "Discord adapter failure")[:500],
            "safe_error_json": _safe_json(payload.get("safe_error_json")),
            "raw_token_returned": False,
        }

    def map_rate_limit(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider_key": self.provider_key,
            "bot_key": payload.get("bot_key"),
            "rate_limit_status": "active",
            "retry_after_seconds": max(0, int(payload.get("retry_after_seconds", 0))),
            "safe_rate_limit_json": _safe_json(payload.get("safe_rate_limit_json")),
            "raw_token_returned": False,
        }


def _project_root() -> Path:
    path = Path(__file__).resolve().parent.parent.parent.parent.parent
    return path


def _load_registry() -> dict[str, Any]:
    _ensure_env_loaded()
    from app.services.runtime_configuration_service import effective_discord_registry

    runtime_registry = effective_discord_registry()
    if runtime_registry is not None:
        raw_bots = runtime_registry["bots"]
        bots = [_parse_item(item) for item in raw_bots if isinstance(item, dict)]
        return {
            **runtime_registry,
            "bots": [item for item in bots if item is not None],
        }
    path_value = os.getenv("DISCORD_BOT_REGISTRY_PATH", "")
    if not path_value:
        return {"path": None, "status": "missing_registry_path", "bots": [], "secrets": {}}
    path = Path(path_value)
    if not path.is_absolute():
        path = _project_root() / path
    if not path.exists():
        return {"path": str(path), "status": "missing_registry_file", "bots": [], "secrets": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"path": str(path), "status": "invalid_registry_file", "bots": [], "secrets": {}}
    raw_bots = data.get("bots") if isinstance(data, dict) else []
    bots = [_parse_item(item) for item in raw_bots if isinstance(item, dict)]
    return {
        "path": str(path),
        "status": "loaded",
        "bots": [item for item in bots if item is not None],
        "secrets": data.get("secrets") if isinstance(data.get("secrets"), dict) else {},
    }


def _parse_item(item: dict[str, Any]) -> DiscordBotRegistryItem | None:
    bot_key = item.get("bot_key")
    if not bot_key:
        return None
    return DiscordBotRegistryItem(
        bot_key=str(bot_key),
        bot_display_name=str(item.get("display_name") or bot_key),
        token_secret_ref=item.get("token_secret_ref"),
        enabled=item.get("status") != "disabled" if "status" in item else bool(item.get("enabled", True)),
        companion_id=item.get("companion_id"),
        provider_bot_id=item.get("provider_bot_id"),
        bot_user_id=item.get("bot_user_id"),
        application_id=item.get("application_id"),
        app_id=item.get("app_id"),
        public_key=item.get("public_key"),
        oauth2_url=item.get("oauth2_url"),
        guild_id=item.get("guild_id"),
        default_channel_id=item.get("default_channel_id"),
        memory_review_channel_id=item.get("memory_review_channel_id"),
        audit_log_channel_id=item.get("audit_log_channel_id"),
        status=item.get("status"),
        default_channel_ref_hash=item.get("default_channel_ref_hash"),
    )


def _resolve_item(bot_key: Any) -> tuple[DiscordBotRegistryItem | None, dict[str, Any]]:
    registry = _load_registry()
    for item in registry["bots"]:
        if item.bot_key == bot_key:
            return item, registry
    return None, registry


def _resolve_credential(item: DiscordBotRegistryItem, registry: dict[str, Any]) -> dict[str, Any]:
    if not item.enabled:
        return {"status": "disabled", "has_token": False}
    if not item.token_secret_ref:
        return {"status": "missing_token", "has_token": False}
    token = _candidate_token(item, registry)
    if not token:
        return {"status": "missing_token", "has_token": False}
    if not isinstance(token, str) or token.lower().startswith("invalid"):
        return {"status": "invalid_token", "has_token": False}
    return {"status": "configured", "has_token": True}


def _candidate_token(item: DiscordBotRegistryItem, registry: dict[str, Any]) -> Any:
    if not item.enabled or not item.token_secret_ref:
        return None
    secrets = registry.get("secrets") if isinstance(registry.get("secrets"), dict) else {}
    token = secrets.get(item.token_secret_ref) if item.token_secret_ref else None
    if not token:
        token = os.getenv(item.token_secret_ref)
    return token


def _resolve_token(item: DiscordBotRegistryItem, registry: dict[str, Any]) -> str | None:
    token = _candidate_token(item, registry)
    return token if isinstance(token, str) and token and not token.lower().startswith("invalid") else None


def _item_status(item: DiscordBotRegistryItem, registry: dict[str, Any]) -> dict[str, Any]:
    credential = _resolve_credential(item, registry)
    return {
        "bot_key": item.bot_key,
        "bot_display_name": item.bot_display_name,
        "enabled": item.enabled,
        "status": item.status or ("active" if item.enabled else "disabled"),
        "companion_id": item.companion_id,
        "provider_bot_id": item.provider_bot_id,
        "bot_user_id": item.bot_user_id,
        "application_id": item.application_id,
        "app_id": item.app_id,
        "public_key": item.public_key,
        "oauth2_url": item.oauth2_url,
        "guild_id": item.guild_id,
        "default_channel_id": item.default_channel_id,
        "memory_review_channel_id": item.memory_review_channel_id,
        "audit_log_channel_id": item.audit_log_channel_id,
        "token_status": credential["status"],
        "token_secret_ref_configured": bool(item.token_secret_ref),
        "raw_token_returned": False,
    }


def _safe_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _scrub(value)


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower().replace("-", "_") for part in _SENSITIVE_KEY_PARTS):
                continue
            result[key_text] = _scrub(item)
        return result
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value
