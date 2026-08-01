import base64
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import providers, runtime_configuration
from app.services import local_configuration_security_service as security
from app.services import runtime_configuration_service as configuration
from app.services import discord_gateway_client


def _client() -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def loopback_test_client(request, call_next):
        request.scope["client"] = ("127.0.0.1", 50100)
        return await call_next(request)

    app.include_router(runtime_configuration.router, prefix="/api/v1")
    app.include_router(providers.router, prefix="/api/v1")
    return TestClient(app)


def _configure_test_storage(monkeypatch, tmp_path: Path) -> None:
    public = tmp_path / "data" / "runtime-configuration.json"
    secret = tmp_path / "secrets" / "runtime-configuration.local.json"
    monkeypatch.setattr(configuration, "_paths", lambda: (public, secret))
    monkeypatch.setattr(
        configuration,
        "_protect",
        lambda value: base64.b64encode(value.encode()).decode(),
    )
    monkeypatch.setattr(
        configuration,
        "_unprotect",
        lambda value: base64.b64decode(value).decode(),
    )


def _session(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/runtime-configuration/session",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    return response.json()["data"]


def _headers(session: dict) -> dict:
    return {
        "Origin": "http://localhost:3000",
        "X-Echora-Config-Session": session["session_token"],
        "X-Echora-CSRF": session["csrf_token"],
    }


def test_control_plane_rejects_untrusted_origin(monkeypatch, tmp_path):
    _configure_test_storage(monkeypatch, tmp_path)
    response = _client().post(
        "/api/v1/runtime-configuration/session",
        headers={"Origin": "http://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_CONFIGURATION_ORIGIN_REJECTED"


def test_configuration_requires_session_and_csrf(monkeypatch, tmp_path):
    _configure_test_storage(monkeypatch, tmp_path)
    response = _client().get(
        "/api/v1/runtime-configuration",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_CONFIGURATION_SESSION_INVALID"


def test_write_only_secrets_are_protected_and_never_returned(monkeypatch, tmp_path):
    _configure_test_storage(monkeypatch, tmp_path)
    client = _client()
    session = _session(client)
    response = client.put(
        "/api/v1/runtime-configuration",
        headers=_headers(session),
        json={
            "expected_revision": 0,
            "llm": {
                "provider": "openai_compatible",
                "base_url": "https://provider.example/v1",
                "model": "model-a",
            },
            "embedding": {
                "provider": "volcengine_ark",
                "base_url": "https://ark.example/v3",
                "model": "embedding-a",
                "dimensions": 1024,
            },
            "discord": {
                "bots": [
                    {
                        "bot_key": "echora-a",
                        "display_name": "Echora A",
                        "app_id": "123456789012345678",
                        "guild_id": "223456789012345678",
                        "default_channel_id": "323456789012345678",
                    }
                ]
            },
            "secret_replacements": {
                "database_url": "postgresql+psycopg://user:database-secret@127.0.0.1:5432/echora",
                "llm_api_key": "llm-secret-value",
                "embedding_api_key": "embedding-secret-value",
                "discord_bot_tokens": {"echora-a": "discord-secret-value"},
                "discord_client_secrets": {"echora-a": "discord-client-secret-value"},
            },
        },
    )
    assert response.status_code == 200
    text = response.text
    assert "llm-secret-value" not in text
    assert "embedding-secret-value" not in text
    assert "discord-secret-value" not in text
    assert "database-secret" not in text
    assert "discord-client-secret-value" not in text
    assert response.json()["data"]["database"]["connection"]["source"] == "local_protected"
    assert response.json()["data"]["discord"]["bots"][0]["client_secret"]["source"] == "local_protected"
    assert response.json()["data"]["llm"]["api_key"]["source"] == "local_protected"
    assert response.json()["data"]["llm"]["api_key"]["updated_at"]
    _, secret_path = configuration._paths()
    raw = secret_path.read_text(encoding="utf-8")
    assert "llm-secret-value" not in raw
    assert "discord-secret-value" not in raw
    assert "database-secret" not in raw
    assert "discord-client-secret-value" not in raw
    public_path, _ = configuration._paths()
    public_raw = public_path.read_text(encoding="utf-8")
    assert "llm-secret-value" not in public_raw
    assert "discord-secret-value" not in public_raw
    assert "database-secret" not in public_raw
    assert "discord-client-secret-value" not in public_raw

    cleared = client.put(
        "/api/v1/runtime-configuration",
        headers=_headers(session),
        json={
            "expected_revision": 1,
            "secret_removals": {
                "database_url": True,
                "discord_client_secrets": ["echora-a"],
            },
        },
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["discord"]["bots"][0]["client_secret"]["configured"] is False
    cleared_raw = secret_path.read_text(encoding="utf-8")
    assert "discord-client-secret:echora-a" not in cleared_raw


def test_database_connection_reports_migration_readiness_without_exposing_url(monkeypatch, tmp_path):
    import sqlalchemy
    from alembic.script import ScriptDirectory

    _configure_test_storage(monkeypatch, tmp_path)
    configuration.update_configuration(
        {
            "expected_revision": 0,
            "secret_replacements": {
                "database_url": "postgresql+psycopg://user:private-password@127.0.0.1:5432/echora"
            },
        }
    )

    class Result:
        def __init__(self, rows=(), scalar_value=None):
            self.rows = rows
            self.scalar_value = scalar_value

        def __iter__(self):
            return iter(self.rows)

        def scalar(self):
            return self.scalar_value

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, statement):
            sql = str(statement)
            if "to_regclass" in sql:
                return Result(scalar_value="alembic_version")
            if "version_num" in sql:
                return Result(rows=[("head-revision",)])
            return Result()

    class Engine:
        def connect(self):
            return Connection()

        def dispose(self):
            return None

    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *_args, **_kwargs: Engine())
    monkeypatch.setattr(
        ScriptDirectory,
        "from_config",
        classmethod(lambda _cls, _config: SimpleNamespace(get_heads=lambda: ["head-revision"])),
    )

    result = configuration.test_connection("database")
    assert result["status"] == "connected"
    assert result["migration_status"] == "current"
    assert result["probe_scope"] == "database_and_migrations"
    assert "private-password" not in str(result)


def test_secret_named_public_fields_are_discarded(monkeypatch, tmp_path):
    _configure_test_storage(monkeypatch, tmp_path)
    client = _client()
    session = _session(client)
    response = client.put(
        "/api/v1/runtime-configuration",
        headers=_headers(session),
        json={
            "expected_revision": 0,
            "llm": {"api_key": "public-leak-attempt", "model": "safe-model"},
            "discord": {
                "bots": [
                    {
                        "bot_key": "safe-bot",
                        "token": "discord-public-leak-attempt",
                        "token_secret_ref": "unsafe-ref",
                    }
                ]
            },
        },
    )
    assert response.status_code == 200
    public_path, _ = configuration._paths()
    public_raw = public_path.read_text(encoding="utf-8")
    assert "public-leak-attempt" not in public_raw
    assert "token_secret_ref" not in public_raw


def test_environment_embedding_auto_resolves_ark_credential(monkeypatch, tmp_path):
    _configure_test_storage(monkeypatch, tmp_path)
    monkeypatch.setattr(configuration.settings, "EMBEDDING_PROVIDER", "auto")
    monkeypatch.setattr(configuration.settings, "EMBEDDING_MODEL", "doubao-embedding-vision-251215")
    monkeypatch.setattr(configuration.settings, "ARK_API_KEY", "synthetic-ark-secret")
    monkeypatch.setattr(configuration.settings, "EMBEDDING_API_KEY", "")
    safe = configuration.read_configuration()
    effective = configuration.effective_embedding_configuration()
    assert safe["embedding"]["provider"] == "auto"
    assert safe["embedding"]["api_key"]["source"] == "environment"
    assert effective["provider"] == "volcengine_ark"
    assert effective["api_key"] == "synthetic-ark-secret"


def test_revision_and_embedding_dimension_fail_closed(monkeypatch, tmp_path):
    _configure_test_storage(monkeypatch, tmp_path)
    client = _client()
    session = _session(client)
    headers = _headers(session)
    conflict = client.put(
        "/api/v1/runtime-configuration",
        headers=headers,
        json={"expected_revision": 4},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "RUNTIME_CONFIGURATION_REVISION_CONFLICT"
    dimension = client.put(
        "/api/v1/runtime-configuration",
        headers=headers,
        json={"expected_revision": 0, "embedding": {"dimensions": 768}},
    )
    assert dimension.status_code == 422
    assert dimension.json()["error"]["code"] == "EMBEDDING_DIMENSION_CHANGE_REQUIRES_SEPARATE_APPROVAL"
    discord_id = client.put(
        "/api/v1/runtime-configuration",
        headers=headers,
        json={
            "expected_revision": 0,
            "discord": {"bots": [{"bot_key": "safe-bot", "guild_id": "not-a-snowflake"}]},
        },
    )
    assert discord_id.status_code == 422
    assert discord_id.json()["error"]["code"] == "DISCORD_SNOWFLAKE_INVALID"
    unsupported_secret = client.put(
        "/api/v1/runtime-configuration",
        headers=headers,
        json={
            "expected_revision": 0,
            "secret_replacements": {"unexpected_secret": "must-not-return"},
        },
    )
    assert unsupported_secret.status_code == 422
    assert unsupported_secret.json()["error"]["code"] == "RUNTIME_CONFIGURATION_SECRET_FIELD_INVALID"
    assert "must-not-return" not in unsupported_secret.text
    invalid_database = client.put(
        "/api/v1/runtime-configuration",
        headers=headers,
        json={
            "expected_revision": 0,
            "secret_replacements": {"database_url": "sqlite:///not-supported.db"},
        },
    )
    assert invalid_database.status_code == 422
    assert invalid_database.json()["error"]["code"] == "RUNTIME_CONFIGURATION_DATABASE_URL_INVALID"


def test_atomic_pair_failure_preserves_previous_configuration(monkeypatch, tmp_path):
    _configure_test_storage(monkeypatch, tmp_path)
    configuration.update_configuration(
        {
            "expected_revision": 0,
            "llm": {"base_url": "https://stable.example/v1", "model": "stable"},
            "secret_replacements": {"llm_api_key": "stable-secret"},
        }
    )
    public_path, secret_path = configuration._paths()
    previous_public = public_path.read_bytes()
    previous_secret = secret_path.read_bytes()
    original_writer = configuration._atomic_json_write

    def fail_public_write(path, value, *, secret):
        if not secret:
            raise OSError("synthetic public replace failure")
        return original_writer(path, value, secret=secret)

    monkeypatch.setattr(configuration, "_atomic_json_write", fail_public_write)
    with pytest.raises(configuration.RuntimeConfigurationError) as failure:
        configuration.update_configuration(
            {
                "expected_revision": 1,
                "llm": {"model": "must-not-stick"},
                "secret_replacements": {"llm_api_key": "must-not-stick-secret"},
            }
        )
    assert failure.value.code == "RUNTIME_CONFIGURATION_ATOMIC_WRITE_FAILED"
    assert public_path.read_bytes() == previous_public
    assert secret_path.read_bytes() == previous_secret


def test_connection_test_returns_safe_status_without_credential(monkeypatch, tmp_path):
    _configure_test_storage(monkeypatch, tmp_path)
    configuration.update_configuration(
        {
            "expected_revision": 0,
            "llm": {"base_url": "https://provider.example/v1", "model": "model-a"},
            "secret_replacements": {"llm_api_key": "connection-secret"},
        }
    )
    captured = {}

    def fake_get(url, *, headers, timeout):
        captured.update({"url": url, "headers": headers, "timeout": timeout})
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    result = configuration.test_connection("llm")
    assert result["target"] == "llm"
    assert result["status"] == "connected"
    assert result["status_code"] == 200
    assert result["real_provider_call"] is True
    assert result["probe_scope"] == "endpoint_and_credential_only"
    assert result["selected_capability_validated"] is False
    assert result["tested_at"]
    assert result["configuration_revision"] == 1
    assert captured["url"] == "https://provider.example/v1/models"
    assert captured["headers"]["Authorization"] == "Bearer connection-secret"
    assert "connection-secret" not in str(result)
    safe = configuration.read_configuration()
    assert safe["verification"]["llm"]["status"] == "connected"
    assert safe["verification"]["llm"]["configuration_revision"] == 1
    changed = configuration.update_configuration(
        {"expected_revision": 1, "llm": {"model": "model-b"}}
    )
    assert changed["verification"]["llm"] is None


def test_discord_gateway_resolves_protected_runtime_token(monkeypatch):
    registry = {
        "status": "loaded",
        "bots": [
            SimpleNamespace(
                bot_key="protected-bot",
                bot_display_name="Protected Bot",
                token_secret_ref="runtime:protected-bot",
                enabled=True,
                app_id="app",
                application_id=None,
                public_key="public",
                guild_id="guild",
                default_channel_id="channel",
            )
        ],
        "secrets": {"runtime:protected-bot": "synthetic-protected-token"},
    }
    captured = {}

    class FakeGatewayBot:
        def __init__(self, *, bot_key, bot_meta, token):
            captured.update({"bot_key": bot_key, "bot_meta": bot_meta, "token": token})

    monkeypatch.setattr(discord_gateway_client, "_load_registry", lambda: registry)
    monkeypatch.setattr(discord_gateway_client, "DiscordGatewayBot", FakeGatewayBot)
    bots = discord_gateway_client.DiscordGatewayRuntime().load_bots()
    assert list(bots) == ["protected-bot"]
    assert captured["token"] == "synthetic-protected-token"


def test_retired_provider_metadata_writers_are_rejected():
    response = _client().post("/api/v1/llm-provider-configs", json={"provider_name": "unsafe"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROVIDER_METADATA_WRITE_RETIRED"
