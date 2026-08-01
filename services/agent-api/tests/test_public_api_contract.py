import json
import re

from app.api.routes import system
from app.main import app


def test_public_openapi_uses_product_language_and_hides_deferred_contracts():
    schema = app.openapi()
    serialized = json.dumps(schema, ensure_ascii=False)

    assert re.search(r"\bPhase\s+\d+\b", serialized) is None
    assert re.search(r"\bP\d+-B\d+\b", serialized) is None
    assert re.search(r"\bWB\d+\b", serialized) is None
    assert "/api/v1/channel-simulation/inbound" not in schema["paths"]
    assert "/api/v1/realtime/sessions" not in schema["paths"]
    assert "/api/v1/companion-voice-profiles" not in schema["paths"]
    assert "/api/v1/companions/{companion_id}/memory-selection-policy" in schema["paths"]
    assert "/api/v1/companions/{companion_id}/presence-timing-policy" in schema["paths"]
    assert "/api/v1/traces/{trace_run_id}/signals" in schema["paths"]
    assert "/api/v1/traces/{trace_run_id}/companion-context" in schema["paths"]
    assert "/api/v1/traces/{trace_run_id}/v3" not in schema["paths"]
    assert "/api/v1/traces/{trace_run_id}/v4" not in schema["paths"]


def test_health_contract_uses_stable_public_version():
    response = system.health_check()

    assert response["error"] is None
    assert response["data"]["capability_version"] == "echora-local-v1"
