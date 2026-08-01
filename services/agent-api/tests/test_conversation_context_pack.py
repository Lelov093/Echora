from __future__ import annotations

import uuid
from types import SimpleNamespace

from app.agents.nodes import memory_retrieval_node, working_memory_node
from app.agents.prompts.conversation_prompt import build_prompt
from app.services.conversation_context_assembler import ConversationContextAssembler
from app.tools.selection import _selection_context
from app.tools.weather_runtime import build_location_queries


def _message(role: str, content: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        role=role,
        content=content,
        content_format="text",
        created_at=None,
    )


def test_working_memory_loads_latest_page_then_restores_chronological_order(
    monkeypatch,
) -> None:
    newest = _message("user", "third")
    middle = _message("assistant", "second")
    oldest = _message("user", "first")
    captured = {}
    monkeypatch.setattr(working_memory_node, "_room_visible_messages", lambda *_args: None)

    def list_latest(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return {"items": [newest, middle, oldest], "total": 3}

    monkeypatch.setattr(working_memory_node, "list_messages", list_latest)
    state = {
        "conversation_id": str(uuid.uuid4()),
        "trace_steps": [],
    }

    working_memory_node.working_memory_node(state)

    assert captured["kwargs"] == {
        "page": 1,
        "page_size": 10,
        "descending": True,
    }
    assert [item["content"] for item in state["recent_messages"]] == [
        "first",
        "second",
        "third",
    ]


def test_context_pack_includes_prior_turns_and_excludes_current_user_message() -> None:
    previous_id = str(uuid.uuid4())
    current_id = str(uuid.uuid4())
    state = {
        "companion_id": str(uuid.uuid4()),
        "conversation_id": str(uuid.uuid4()),
        "user_message_id": current_id,
        "user_input": "今天的天气",
        "current_mode": "daily",
        "companion_profile": {"name": "小E"},
        "recent_messages": [
            {
                "id": previous_id,
                "role": "user",
                "content": "华盛顿特区",
            },
            {
                "id": str(uuid.uuid4()),
                "role": "assistant",
                "content": "你想查询哪里的天气？",
            },
            {
                "id": current_id,
                "role": "user",
                "content": "今天的天气",
            },
        ],
    }

    system, user = build_prompt(state)

    assert "Recent same-Conversation messages" in system
    assert "华盛顿特区" in system
    assert "你想查询哪里的天气？" in system
    assert "User says: 今天的天气" in user
    assert system.count("今天的天气") == 0
    manifest = state["context_pack_manifest"]
    assert manifest["contract_version"] == "conversation_context_pack_v3"
    assert manifest["recent_conversation"]["message_ids"] == [
        previous_id,
        state["recent_messages"][1]["id"],
    ]


def test_retrieval_query_augments_elliptical_turn_with_recent_user_context() -> None:
    current_id = str(uuid.uuid4())
    query, mode = memory_retrieval_node.build_retrieval_query({
        "user_message_id": current_id,
        "user_input": "今天的天气",
        "recent_messages": [
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": "查询美国华盛顿今天的天气",
            },
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": "华盛顿特区",
            },
            {
                "id": current_id,
                "role": "user",
                "content": "今天的天气",
            },
        ],
    })

    assert mode == "conversation_aware_query_v1"
    assert "查询美国华盛顿今天的天气" in query
    assert "华盛顿特区" in query
    assert query.endswith("今天的天气")


def test_tool_selection_context_uses_recent_tool_intent_but_not_normal_chat() -> None:
    weather_context = _selection_context(
        "华盛顿特区",
        [
            {"role": "user", "content": "查询美国华盛顿今天的天气"},
            {"role": "assistant", "content": "地点没有找到"},
        ],
    )
    normal_context = _selection_context(
        "继续",
        [
            {"role": "user", "content": "介绍一下你自己"},
            {"role": "assistant", "content": "我是小E"},
        ],
    )

    assert weather_context
    assert normal_context == []


def test_context_manifest_records_scope_budget_selection_and_fingerprint() -> None:
    state = {
        "user_id": str(uuid.uuid4()),
        "companion_id": str(uuid.uuid4()),
        "conversation_id": str(uuid.uuid4()),
        "recent_messages": [],
    }
    _blocks, manifest = ConversationContextAssembler().assemble(
        state,
        [
            ("safety", "Safety boundaries"),
            ("recent_conversation", ""),
        ],
        recent_manifest={
            "message_head_id": None,
            "message_head_created_at": None,
        },
    )

    safety = manifest["sections"][0]
    assert safety["section"] == "safety"
    assert safety["priority"] == "non_bypassable_safety"
    assert safety["selection"] == "included"
    assert safety["budget"]["character_used"] > 0
    assert safety["budget"]["token_estimate"] > 0
    assert safety["llm_allowed"] is True
    assert len(manifest["fingerprint"]) == 64
    assert manifest["cross_companion_content_included"] is False


def test_context_assembler_excludes_cross_companion_section() -> None:
    companion_id = str(uuid.uuid4())
    state = {
        "user_id": str(uuid.uuid4()),
        "companion_id": companion_id,
        "conversation_id": str(uuid.uuid4()),
        "companion_context_snapshot": {
            "memories": {
                "availability": "available",
                "source": {"type": "memory", "version": "1"},
                "scope": {
                    "companion_id": str(uuid.uuid4()),
                    "cross_companion_content_included": True,
                },
            }
        },
    }
    blocks, manifest = ConversationContextAssembler().assemble(
        state,
        [("memories", "private memory")],
        recent_manifest={},
    )

    assert blocks == ""
    assert manifest["sections"][0]["selection"] == "excluded"
    assert (
        manifest["sections"][0]["reason"]
        == "scope_mismatch_or_not_llm_allowed"
    )


def test_weather_location_candidates_use_general_syntax_rules() -> None:
    assert "Washington" in {
        item.value for item in build_location_queries("Washington D.C.")
    }
    assert "海淀" in {
        item.value for item in build_location_queries("北京市海淀区")
    }
    assert "巴黎" in {
        item.value for item in build_location_queries("法国巴黎")
    }
