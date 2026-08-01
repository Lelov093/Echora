"""Canonical local runtime configuration with write-only DPAPI secrets."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.core.config import database_url_from_environment, settings
from app.core.local_protected_store import (
    LocalProtectedStoreError,
    protect_local_secret,
    unprotect_local_secret,
)


class RuntimeConfigurationError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


_lock = threading.RLock()
_PUBLIC_DEFAULTS = {
    "revision": 0,
    "llm": {"provider": "openai_compatible", "base_url": "", "model": "", "model_fallbacks": []},
    "embedding": {
        "provider": "",
        "base_url": "",
        "model": "",
        "model_fallbacks": [],
        "dimensions": 1024,
    },
    "discord": {"bots": []},
    "verification": {"database": None, "llm": None, "embedding": None, "discord": {}},
}
_PUBLIC_DOMAIN_FIELDS = {
    "llm": {"provider", "base_url", "model", "model_fallbacks"},
    "embedding": {"provider", "base_url", "model", "model_fallbacks", "dimensions"},
}
_PUBLIC_DISCORD_FIELDS = {
    "bot_key",
    "display_name",
    "enabled",
    "app_id",
    "application_id",
    "public_key",
    "oauth2_url",
    "guild_id",
    "default_channel_id",
}
_BOT_KEY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_DISCORD_SNOWFLAKE_PATTERN = re.compile(r"^\d{15,22}$")
_DISCORD_PUBLIC_KEY_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")


def _paths() -> tuple[Path, Path]:
    return (
        settings.DATA_DIR / "runtime-configuration.json",
        settings.PROJECT_ROOT / ".secrets" / "runtime-configuration.local.json",
    )


def _read_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return json.loads(json.dumps(fallback))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeConfigurationError(
            "RUNTIME_CONFIGURATION_INVALID_FILE",
            "A runtime configuration file is unreadable or invalid.",
            {"file_kind": "secret" if ".secrets" in path.parts else "public"},
        ) from exc
    if not isinstance(value, dict):
        raise RuntimeConfigurationError("RUNTIME_CONFIGURATION_INVALID_FILE", "Runtime configuration must be an object.")
    return value


def _public() -> dict:
    public_path, _ = _paths()
    value = _read_json(public_path, _PUBLIC_DEFAULTS)
    merged = json.loads(json.dumps(_PUBLIC_DEFAULTS))
    merged.update({key: item for key, item in value.items() if key in merged})
    for domain in ("llm", "embedding", "discord"):
        if isinstance(value.get(domain), dict):
            merged[domain].update(value[domain])
    return merged


def _secret_ciphertexts() -> dict:
    _, secret_path = _paths()
    value = _read_json(secret_path, {"version": 1, "values": {}})
    return value.get("values") if isinstance(value.get("values"), dict) else {}


def _secret_updated_at() -> dict[str, str]:
    _, secret_path = _paths()
    value = _read_json(secret_path, {"version": 1, "values": {}, "updated_at": {}})
    metadata = value.get("updated_at")
    return metadata if isinstance(metadata, dict) else {}


def _secret_values() -> dict[str, str]:
    result: dict[str, str] = {}
    for key, ciphertext in _secret_ciphertexts().items():
        if isinstance(key, str) and isinstance(ciphertext, str):
            result[key] = _unprotect(ciphertext)
    return result


def _env_secret(name: str) -> str:
    if name == "DATABASE_URL":
        return str(database_url_from_environment or "")
    return str(getattr(settings, name, "") or os.getenv(name, "") or "")


def _secret_status(local: dict[str, str], local_key: str, env_name: str) -> dict:
    if local.get(local_key):
        return {
            "configured": True,
            "source": "local_protected",
            "updated_at": _secret_updated_at().get(local_key),
            "last_four": None,
        }
    if _env_secret(env_name):
        return {"configured": True, "source": "environment", "updated_at": None, "last_four": None}
    return {"configured": False, "source": "missing", "updated_at": None, "last_four": None}


def _discord_env_name(bot_key: str) -> str:
    normalized = "".join(character if character.isalnum() else "_" for character in bot_key.upper())
    return f"DISCORD_SECRET_{normalized}_TOKEN"


def _discord_client_secret_env_name(bot_key: str) -> str:
    normalized = "".join(character if character.isalnum() else "_" for character in bot_key.upper())
    return f"DISCORD_SECRET_{normalized}_CLIENT_SECRET"


def _resolved_embedding_provider(provider: Any, model: Any) -> str:
    configured = str(provider or "").strip().lower()
    if configured in {"openai_compatible", "dashscope_multimodal", "volcengine_ark"}:
        return configured
    model_name = str(model or "").strip().lower()
    if model_name.startswith("doubao-embedding-vision"):
        return "volcengine_ark"
    if model_name.startswith(("tongyi-embedding-vision", "qwen3-vl-embedding", "qwen2.5-vl-embedding")):
        return "dashscope_multimodal"
    return "openai_compatible"


def _safe_verification_entry(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    status = value.get("status")
    tested_at = value.get("tested_at")
    if not isinstance(status, str) or not isinstance(tested_at, str):
        return None
    return {
        "status": status,
        "status_code": value.get("status_code") if isinstance(value.get("status_code"), int) else None,
        "real_provider_call": value.get("real_provider_call") is True,
        "probe_scope": (
            value.get("probe_scope")
            if value.get("probe_scope") in {"database_and_migrations", "endpoint_and_credential_only", "discord_bot_identity"}
            else "unknown"
        ),
        "selected_capability_validated": value.get("selected_capability_validated") is True,
        "tested_at": tested_at,
        "configuration_revision": (
            value.get("configuration_revision")
            if isinstance(value.get("configuration_revision"), int)
            else None
        ),
        **(
            {"migration_status": value["migration_status"]}
            if value.get("migration_status") in {"current", "outdated", "uninitialized", "unknown"}
            else {}
        ),
    }


def _safe_verification(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    raw_discord = raw.get("discord") if isinstance(raw.get("discord"), dict) else {}
    return {
        "database": _safe_verification_entry(raw.get("database")),
        "llm": _safe_verification_entry(raw.get("llm")),
        "embedding": _safe_verification_entry(raw.get("embedding")),
        "discord": {
            str(bot_key): entry
            for bot_key, raw_entry in raw_discord.items()
            if (entry := _safe_verification_entry(raw_entry)) is not None
        },
    }


def read_configuration() -> dict:
    with _lock:
        public = _public()
        local = _secret_values()
        llm = public["llm"]
        embedding = public["embedding"]
        embedding_provider = embedding.get("provider") or settings.EMBEDDING_PROVIDER
        effective_embedding_provider = _resolved_embedding_provider(
            embedding_provider,
            embedding.get("model") or settings.EMBEDDING_MODEL,
        )
        bots = []
        for item in public["discord"].get("bots") or []:
            if not isinstance(item, dict) or not item.get("bot_key"):
                continue
            safe = {key: value for key, value in item.items() if "token" not in key.lower() and "secret" not in key.lower()}
            safe["token"] = _secret_status(
                local,
                f"discord:{item['bot_key']}",
                _discord_env_name(str(item["bot_key"])),
            )
            safe["client_secret"] = _secret_status(
                local,
                f"discord-client-secret:{item['bot_key']}",
                _discord_client_secret_env_name(str(item["bot_key"])),
            )
            bots.append(safe)
        return {
            "contract_version": "runtime-configuration.v1",
            "revision": int(public.get("revision") or 0),
            "security_mode": "loopback_origin_session_csrf",
            "database": {
                "connection": _secret_status(local, "database_url", "DATABASE_URL"),
                "effective_source": "local" if local.get("database_url") else "environment",
                "reload_mode": "agent_api_restart_required",
            },
            "llm": {
                **llm,
                "base_url": llm.get("base_url") or settings.OPENAI_BASE_URL,
                "model": llm.get("model") or settings.OPENAI_MODEL,
                "api_key": _secret_status(local, "llm_api_key", "OPENAI_API_KEY"),
                "effective_source": "local" if any(llm.get(key) for key in ("base_url", "model")) else "environment",
                "reload_mode": "hot_on_next_turn",
            },
            "embedding": {
                **embedding,
                "base_url": embedding.get("base_url") or settings.EMBEDDING_BASE_URL or settings.ARK_BASE_URL,
                "model": embedding.get("model") or settings.EMBEDDING_MODEL,
                "provider": embedding_provider,
                "dimensions": int(embedding.get("dimensions") or settings.EMBEDDING_DIMENSIONS),
                "api_key": _secret_status(
                    local,
                    "embedding_api_key",
                    "ARK_API_KEY" if effective_embedding_provider == "volcengine_ark" else "EMBEDDING_API_KEY",
                ),
                "effective_source": "local" if any(embedding.get(key) for key in ("base_url", "model")) else "environment",
                "reload_mode": "hot_provider_refresh",
            },
            "discord": {
                "bots": bots,
                "file_registry_detected": bool(os.getenv("DISCORD_BOT_REGISTRY_PATH", "")),
                "reload_mode": "discord_runtime_restart_required",
            },
            "verification": _safe_verification(public.get("verification")),
            "secret_values_returned": False,
        }


def effective_llm_configuration() -> dict[str, Any]:
    with _lock:
        root = _public()
        public = root["llm"]
        local = _secret_values()
        return {
            "provider": public.get("provider") or "openai_compatible",
            "base_url": public.get("base_url") or settings.OPENAI_BASE_URL,
            "model": public.get("model") or settings.OPENAI_MODEL or "gpt-4o-mini",
            "model_fallbacks": (
                public.get("model_fallbacks")
                or _comma_separated_values(settings.OPENAI_MODEL_FALLBACKS)
            ),
            "api_key": local.get("llm_api_key") or settings.OPENAI_API_KEY,
            "revision": root.get("revision", 0),
        }


def _comma_separated_values(value: str) -> list[str]:
    return list(dict.fromkeys(
        item.strip()
        for item in str(value or "").split(",")
        if item.strip()
    ))


def effective_embedding_configuration() -> dict[str, Any]:
    with _lock:
        root = _public()
        public = root["embedding"]
        local = _secret_values()
        configured_provider = public.get("provider") or settings.EMBEDDING_PROVIDER
        model = public.get("model") or settings.EMBEDDING_MODEL
        provider = _resolved_embedding_provider(configured_provider, model)
        return {
            "provider": provider,
            "base_url": public.get("base_url") or settings.EMBEDDING_BASE_URL or settings.ARK_BASE_URL,
            "model": model,
            "model_fallbacks": public.get("model_fallbacks") or [],
            "dimensions": int(public.get("dimensions") or settings.EMBEDDING_DIMENSIONS),
            "api_key": local.get("embedding_api_key") or (
                settings.ARK_API_KEY if provider == "volcengine_ark" else settings.EMBEDDING_API_KEY
            ),
            "revision": root.get("revision", 0),
        }


def effective_discord_registry() -> dict[str, Any] | None:
    with _lock:
        bots = _public()["discord"].get("bots") or []
        if not bots:
            return None
        local = _secret_values()
        safe_bots = []
        secrets_map: dict[str, str] = {}
        for raw in bots:
            if not isinstance(raw, dict) or not raw.get("bot_key"):
                continue
            item = dict(raw)
            secret_ref = f"runtime:{item['bot_key']}"
            item["token_secret_ref"] = secret_ref
            token = local.get(f"discord:{item['bot_key']}")
            if token:
                secrets_map[secret_ref] = token
            safe_bots.append(item)
        return {"path": "protected_runtime_configuration", "status": "loaded", "bots": safe_bots, "secrets": secrets_map}


def _test_database_connection() -> dict[str, Any]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from alembic.util.exc import CommandError
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError

    local = _secret_values()
    database_url = local.get("database_url") or database_url_from_environment
    if not database_url:
        return _finish_connection_test(
            "database",
            None,
            {
                "target": "database",
                "status": "not_configured",
                "migration_status": "unknown",
                "real_provider_call": False,
            },
        )
    engine = None
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 5},
        )
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            table_exists = connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
            current_revisions = set()
            if table_exists:
                current_revisions = {
                    str(row[0])
                    for row in connection.execute(text("SELECT version_num FROM alembic_version"))
                    if row[0]
                }
        alembic_config = Config(str(settings.PROJECT_ROOT / "services" / "agent-api" / "alembic.ini"))
        expected_heads = set(ScriptDirectory.from_config(alembic_config).get_heads())
        migration_status = (
            "uninitialized"
            if not current_revisions
            else "current"
            if current_revisions == expected_heads
            else "outdated"
        )
        return _finish_connection_test(
            "database",
            None,
            {
                "target": "database",
                "status": "connected",
                "migration_status": migration_status,
                "real_provider_call": True,
            },
        )
    except (SQLAlchemyError, CommandError, OSError, ValueError):
        return _finish_connection_test(
            "database",
            None,
            {
                "target": "database",
                "status": "unreachable",
                "migration_status": "unknown",
                "real_provider_call": True,
            },
        )
    finally:
        if engine is not None:
            engine.dispose()


def test_connection(target: str, bot_key: str | None = None) -> dict[str, Any]:
    import httpx

    if target == "database":
        return _test_database_connection()
    if target == "llm":
        config = effective_llm_configuration()
        base_url = str(config["base_url"] or "").rstrip("/")
        url = f"{base_url}/models" if base_url else ""
        token = config["api_key"]
    elif target == "embedding":
        config = effective_embedding_configuration()
        base_url = str(config["base_url"] or "").rstrip("/")
        url = f"{base_url}/models" if base_url else ""
        token = config["api_key"]
    elif target == "discord":
        if not bot_key:
            raise RuntimeConfigurationError("DISCORD_BOT_KEY_REQUIRED", "Choose a Discord bot before testing.")
        registry = effective_discord_registry()
        token = (registry or {}).get("secrets", {}).get(f"runtime:{bot_key}")
        if not token:
            token = os.getenv(_discord_env_name(bot_key), "")
        url = "https://discord.com/api/v10/users/@me"
    else:
        raise RuntimeConfigurationError("RUNTIME_CONFIGURATION_TEST_TARGET_INVALID", "Unsupported connection test target.")
    if not url or not token:
        return _finish_connection_test(
            target,
            bot_key,
            {"target": target, "status": "not_configured", "real_provider_call": False},
        )
    headers = {"Authorization": f"{'Bot' if target == 'discord' else 'Bearer'} {token}"}
    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()
        return _finish_connection_test(
            target,
            bot_key,
            {
                "target": target,
                "status": "connected",
                "status_code": response.status_code,
                "real_provider_call": True,
            },
        )
    except httpx.HTTPStatusError as exc:
        return _finish_connection_test(
            target,
            bot_key,
            {
                "target": target,
                "status": "rejected",
                "status_code": exc.response.status_code,
                "real_provider_call": True,
            },
        )
    except httpx.HTTPError as exc:
        return _finish_connection_test(
            target,
            bot_key,
            {
                "target": target,
                "status": "unreachable",
                "failure_type": type(exc).__name__,
                "real_provider_call": True,
            },
        )


def _finish_connection_test(target: str, bot_key: str | None, result: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        public = _public()
        evidence = {
            "status": result["status"],
            "status_code": result.get("status_code"),
            "real_provider_call": result.get("real_provider_call") is True,
            "probe_scope": (
                "database_and_migrations"
                if target == "database"
                else "discord_bot_identity"
                if target == "discord"
                else "endpoint_and_credential_only"
            ),
            "selected_capability_validated": False,
            "tested_at": datetime.now(timezone.utc).isoformat(),
            "configuration_revision": int(public.get("revision") or 0),
            **(
                {"migration_status": result["migration_status"]}
                if result.get("migration_status")
                else {}
            ),
        }
        verification = _safe_verification(public.get("verification"))
        if target == "discord":
            if not bot_key:
                raise RuntimeConfigurationError("DISCORD_BOT_KEY_REQUIRED", "Choose a Discord bot before testing.")
            verification["discord"][bot_key] = evidence
        else:
            verification[target] = evidence
        public["verification"] = verification
        public_path, _ = _paths()
        _atomic_json_write(public_path, public, secret=False)
    return {**result, **evidence}


def update_configuration(payload: dict[str, Any]) -> dict:
    with _lock:
        current = _public()
        expected = payload.get("expected_revision")
        if isinstance(expected, bool) or not isinstance(expected, int):
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_REVISION_INVALID",
                "A numeric expected revision is required.",
            )
        if expected != int(current.get("revision") or 0):
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_REVISION_CONFLICT",
                "Runtime configuration changed; refresh before saving.",
                {"current_revision": int(current.get("revision") or 0)},
            )
        next_public = json.loads(json.dumps(current))
        for domain in ("llm", "embedding"):
            if isinstance(payload.get(domain), dict):
                next_public[domain].update(
                    {
                        key: value
                        for key, value in payload[domain].items()
                        if key in _PUBLIC_DOMAIN_FIELDS[domain]
                    }
                )
        if isinstance(payload.get("discord"), dict):
            raw_bots = payload["discord"].get("bots") or []
            next_public["discord"]["bots"] = [
                {key: value for key, value in bot.items() if key in _PUBLIC_DISCORD_FIELDS}
                for bot in raw_bots
                if isinstance(bot, dict)
            ]
        _validate(next_public)
        secrets_payload = payload.get("secret_replacements") if isinstance(payload.get("secret_replacements"), dict) else {}
        _validate_secret_replacements(secrets_payload)
        removals_payload = payload.get("secret_removals") if isinstance(payload.get("secret_removals"), dict) else {}
        _validate_secret_removals(removals_payload)
        next_secrets = _secret_values()
        next_secret_updated_at = _secret_updated_at()
        updated_at = datetime.now(timezone.utc).isoformat()
        for key in ("database_url", "llm_api_key", "embedding_api_key"):
            if isinstance(secrets_payload.get(key), str) and secrets_payload[key]:
                next_secrets[key] = secrets_payload[key]
                next_secret_updated_at[key] = updated_at
        discord_tokens = secrets_payload.get("discord_bot_tokens")
        if isinstance(discord_tokens, dict):
            for bot_key, token in discord_tokens.items():
                if isinstance(bot_key, str) and isinstance(token, str) and token:
                    next_secrets[f"discord:{bot_key}"] = token
                    next_secret_updated_at[f"discord:{bot_key}"] = updated_at
        discord_client_secrets = secrets_payload.get("discord_client_secrets")
        if isinstance(discord_client_secrets, dict):
            for bot_key, client_secret in discord_client_secrets.items():
                if isinstance(bot_key, str) and isinstance(client_secret, str) and client_secret:
                    next_secrets[f"discord-client-secret:{bot_key}"] = client_secret
                    next_secret_updated_at[f"discord-client-secret:{bot_key}"] = updated_at
        for key in ("database_url", "llm_api_key", "embedding_api_key"):
            if removals_payload.get(key) is True:
                next_secrets.pop(key, None)
                next_secret_updated_at.pop(key, None)
        for bot_key in removals_payload.get("discord_bot_tokens") or []:
            next_secrets.pop(f"discord:{bot_key}", None)
            next_secret_updated_at.pop(f"discord:{bot_key}", None)
        for bot_key in removals_payload.get("discord_client_secrets") or []:
            next_secrets.pop(f"discord-client-secret:{bot_key}", None)
            next_secret_updated_at.pop(f"discord-client-secret:{bot_key}", None)
        active_bot_keys = {
            str(bot["bot_key"])
            for bot in next_public["discord"]["bots"]
            if isinstance(bot, dict) and bot.get("bot_key")
        }
        next_secrets = {
            key: value
            for key, value in next_secrets.items()
            if (
                (not key.startswith("discord:") or key.removeprefix("discord:") in active_bot_keys)
                and (
                    not key.startswith("discord-client-secret:")
                    or key.removeprefix("discord-client-secret:") in active_bot_keys
                )
            )
        }
        next_secret_updated_at = {
            key: value
            for key, value in next_secret_updated_at.items()
            if key in next_secrets
        }
        existing_database_verification = _safe_verification(current.get("verification")).get("database")
        next_public["verification"] = {
            "database": (
                None
                if secrets_payload.get("database_url") or removals_payload.get("database_url")
                else existing_database_verification
            ),
            "llm": None,
            "embedding": None,
            "discord": {},
        }
        next_public["revision"] = int(current.get("revision") or 0) + 1
        _atomic_pair_write(next_public, next_secrets, next_secret_updated_at)
        return read_configuration()


def _validate(value: dict) -> None:
    for domain in ("llm", "embedding"):
        provider = str(value[domain].get("provider") or "")
        allowed_providers = (
            {"openai_compatible"}
            if domain == "llm"
            else {"", "auto", "openai_compatible", "dashscope_multimodal", "volcengine_ark"}
        )
        if provider not in allowed_providers:
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_PROVIDER_INVALID",
                f"{domain} provider is not supported.",
            )
        base_url = str(value[domain].get("base_url") or "")
        model = str(value[domain].get("model") or "")
        if len(base_url) > 2048 or len(model) > 256:
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_FIELD_TOO_LONG",
                f"{domain} configuration exceeds the allowed length.",
            )
        if base_url:
            parsed = urlparse(base_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise RuntimeConfigurationError("RUNTIME_CONFIGURATION_BASE_URL_INVALID", f"{domain} base URL must use http or https.")
        fallbacks = value[domain].get("model_fallbacks") or []
        if not isinstance(fallbacks, list) or len(fallbacks) > 10 or any(
            not isinstance(item, str) or not item or len(item) > 256 for item in fallbacks
        ):
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_MODEL_FALLBACKS_INVALID",
                f"{domain} model fallbacks are invalid.",
            )
    dimensions = int(value["embedding"].get("dimensions") or settings.EMBEDDING_DIMENSIONS)
    if dimensions != settings.EMBEDDING_DIMENSIONS:
        raise RuntimeConfigurationError(
            "EMBEDDING_DIMENSION_CHANGE_REQUIRES_SEPARATE_APPROVAL",
            "Embedding dimensions cannot change without a separately approved reindex.",
            {"current_dimensions": settings.EMBEDDING_DIMENSIONS},
        )
    seen: set[str] = set()
    bots = value["discord"].get("bots") or []
    if not isinstance(bots, list) or len(bots) > 50:
        raise RuntimeConfigurationError("DISCORD_BOT_COUNT_INVALID", "Discord configuration supports at most 50 bots.")
    for bot in bots:
        bot_key = str(bot.get("bot_key") or "") if isinstance(bot, dict) else ""
        if not _BOT_KEY_PATTERN.fullmatch(bot_key) or bot_key in seen:
            raise RuntimeConfigurationError("DISCORD_BOT_KEY_INVALID", "Every Discord bot needs a unique bot key.")
        seen.add(bot_key)
        if len(str(bot.get("display_name") or "")) > 120:
            raise RuntimeConfigurationError("DISCORD_BOT_DISPLAY_NAME_INVALID", "Discord bot display name is too long.")
        for field in ("app_id", "application_id", "guild_id", "default_channel_id"):
            field_value = str(bot.get(field) or "")
            if field_value and not _DISCORD_SNOWFLAKE_PATTERN.fullmatch(field_value):
                raise RuntimeConfigurationError(
                    "DISCORD_SNOWFLAKE_INVALID",
                    f"Discord {field} must be a numeric snowflake.",
                )
        public_key = str(bot.get("public_key") or "")
        if public_key and not _DISCORD_PUBLIC_KEY_PATTERN.fullmatch(public_key):
            raise RuntimeConfigurationError(
                "DISCORD_PUBLIC_KEY_INVALID",
                "Discord Public Key must contain 64 hexadecimal characters.",
            )
        oauth2_url = str(bot.get("oauth2_url") or "")
        if oauth2_url:
            parsed_oauth = urlparse(oauth2_url)
            if parsed_oauth.scheme != "https" or parsed_oauth.hostname not in {"discord.com", "discordapp.com"}:
                raise RuntimeConfigurationError(
                    "DISCORD_OAUTH_URL_INVALID",
                    "Discord OAuth2 URL must use an official Discord HTTPS host.",
                )


def _validate_secret_replacements(value: dict[str, Any]) -> None:
    allowed = {
        "database_url",
        "llm_api_key",
        "embedding_api_key",
        "discord_bot_tokens",
        "discord_client_secrets",
    }
    if any(key not in allowed for key in value):
        raise RuntimeConfigurationError(
            "RUNTIME_CONFIGURATION_SECRET_FIELD_INVALID",
            "Secret replacement contains an unsupported field.",
        )
    for key in ("database_url", "llm_api_key", "embedding_api_key"):
        secret = value.get(key)
        if secret is not None and (not isinstance(secret, str) or not secret or len(secret) > 8192):
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_SECRET_INVALID",
                "Secret replacement is empty or exceeds the allowed length.",
            )
    database_url = value.get("database_url")
    if isinstance(database_url, str):
        from sqlalchemy.engine import make_url
        from sqlalchemy.exc import ArgumentError

        try:
            parsed_database_url = make_url(database_url)
        except ArgumentError as exc:
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_DATABASE_URL_INVALID",
                "Database URL must be a valid PostgreSQL psycopg connection.",
            ) from exc
        if (
            parsed_database_url.drivername != "postgresql+psycopg"
            or not parsed_database_url.host
            or not parsed_database_url.database
            or not parsed_database_url.username
        ):
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_DATABASE_URL_INVALID",
                "Database URL must include PostgreSQL psycopg driver, host, database, and user.",
            )
    for field in ("discord_bot_tokens", "discord_client_secrets"):
        replacements = value.get(field)
        if replacements is None:
            continue
        if not isinstance(replacements, dict) or len(replacements) > 50:
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_SECRET_INVALID",
                "Discord secret replacements are invalid.",
            )
        for bot_key, secret in replacements.items():
            if (
                not isinstance(bot_key, str)
                or not _BOT_KEY_PATTERN.fullmatch(bot_key)
                or not isinstance(secret, str)
                or not secret
                or len(secret) > 8192
            ):
                raise RuntimeConfigurationError(
                    "RUNTIME_CONFIGURATION_SECRET_INVALID",
                    "Discord secret replacement is invalid.",
                )


def _validate_secret_removals(value: dict[str, Any]) -> None:
    allowed = {
        "database_url",
        "llm_api_key",
        "embedding_api_key",
        "discord_bot_tokens",
        "discord_client_secrets",
    }
    if any(key not in allowed for key in value):
        raise RuntimeConfigurationError(
            "RUNTIME_CONFIGURATION_SECRET_FIELD_INVALID",
            "Secret removal contains an unsupported field.",
        )
    for key in ("database_url", "llm_api_key", "embedding_api_key"):
        if key in value and value[key] is not True:
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_SECRET_INVALID",
                "Secret removal flags must be true.",
            )
    for key in ("discord_bot_tokens", "discord_client_secrets"):
        bot_keys = value.get(key)
        if bot_keys is None:
            continue
        if not isinstance(bot_keys, list) or len(bot_keys) > 50 or any(
            not isinstance(bot_key, str) or not _BOT_KEY_PATTERN.fullmatch(bot_key)
            for bot_key in bot_keys
        ):
            raise RuntimeConfigurationError(
                "RUNTIME_CONFIGURATION_SECRET_INVALID",
                "Discord secret removals are invalid.",
            )


def _atomic_pair_write(public: dict, secrets: dict[str, str], secret_updated_at: dict[str, str]) -> None:
    public_path, secret_path = _paths()
    previous_secret = secret_path.read_bytes() if secret_path.exists() else None
    protected = {
        "version": 1,
        "values": {key: _protect(value) for key, value in secrets.items()},
        "updated_at": secret_updated_at,
    }
    try:
        _atomic_json_write(secret_path, protected, secret=True)
        _atomic_json_write(public_path, public, secret=False)
    except Exception as exc:
        if previous_secret is None:
            secret_path.unlink(missing_ok=True)
        else:
            secret_path.write_bytes(previous_secret)
        if isinstance(exc, RuntimeConfigurationError):
            raise
        raise RuntimeConfigurationError("RUNTIME_CONFIGURATION_ATOMIC_WRITE_FAILED", "Runtime configuration was not saved.") from exc


def _atomic_json_write(path: Path, value: dict, *, secret: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        os.chmod(path, 0o600 if secret else 0o640)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _protect(value: str) -> str:
    try:
        return protect_local_secret(value)
    except LocalProtectedStoreError as exc:
        raise RuntimeConfigurationError(exc.code, str(exc)) from exc


def _unprotect(value: str) -> str:
    try:
        return unprotect_local_secret(value)
    except LocalProtectedStoreError as exc:
        raise RuntimeConfigurationError(exc.code, str(exc)) from exc
