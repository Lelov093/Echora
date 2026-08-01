"""Versioned typed contracts for the bounded bounded Tool tool catalog."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date as Date, datetime
from typing import Literal, Type

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchInput(ToolInput):
    query: str = Field(min_length=2, max_length=300)
    max_results: int = Field(default=5, ge=1, le=8)


class WebReadInput(ToolInput):
    url: HttpUrl
    question: str | None = Field(default=None, max_length=500)


class ReminderInput(ToolInput):
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=2000)


class CalendarInput(ToolInput):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    duration_minutes: int = Field(default=60, ge=5, le=1440)
    timezone: str = Field(default="Asia/Shanghai", min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=2000)


class WeatherInput(ToolInput):
    location: str = Field(min_length=2, max_length=160)
    date: Date | None = None


class TranslationInput(ToolInput):
    text: str = Field(min_length=1, max_length=6000)
    target_language: str = Field(min_length=2, max_length=60)
    source_language: str | None = Field(default=None, max_length=60)


class ExchangeInput(ToolInput):
    amount: float = Field(gt=0, le=1_000_000_000)
    from_currency: str = Field(pattern=r"^[A-Za-z]{3}$")
    to_currency: str = Field(pattern=r"^[A-Za-z]{3}$")
    date: Date | None = None


class NoteInput(ToolInput):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)


class FileInput(ToolInput):
    file_document_id: uuid.UUID
    action: Literal["summarize", "extract", "search", "stats", "create_text_copy"]
    query: str | None = Field(default=None, max_length=500)
    output_title: str | None = Field(default=None, max_length=200)


@dataclass(frozen=True)
class CapabilitySpec:
    key: str
    display_name: str
    description: str
    input_model: Type[ToolInput]
    risk_level: Literal["low", "medium", "high"]
    side_effect: bool
    adapter_name: str
    timeout_seconds: int = 20
    max_attempts: int = 3

    @property
    def input_schema(self) -> dict:
        return self.input_model.model_json_schema(mode="validation")


CAPABILITIES: dict[str, CapabilitySpec] = {
    "search": CapabilitySpec("search", "搜索", "检索公开网络来源并返回可追踪结果。", SearchInput, "low", False, "public_search_v1"),
    "web_read": CapabilitySpec("web_read", "网页读取", "安全读取公开网页的标题、正文摘要和来源。", WebReadInput, "low", False, "safe_web_reader_v1"),
    "reminder": CapabilitySpec("reminder", "提醒", "创建同 owner/Companion scope 的本地持久提醒。", ReminderInput, "medium", True, "local_reminder_v1"),
    "calendar": CapabilitySpec("calendar", "日程", "创建同 owner/Companion scope 的本地持久日程。", CalendarInput, "medium", True, "local_calendar_v1"),
    "weather": CapabilitySpec(
        "weather",
        "天气",
        "读取指定地点和日期的真实天气预报。",
        WeatherInput,
        "low",
        False,
        "open_meteo_v1",
        timeout_seconds=35,
    ),
    "translation": CapabilitySpec("translation", "翻译", "通过当前真实 Provider 完成有来源语言约束的翻译。", TranslationInput, "low", False, "conversation_provider_translation_v1", timeout_seconds=60, max_attempts=2),
    "exchange": CapabilitySpec("exchange", "汇率", "读取真实参考汇率并计算换算结果。", ExchangeInput, "low", False, "frankfurter_v1"),
    "note": CapabilitySpec("note", "轻量笔记", "创建同 owner/Companion scope 的轻量笔记。", NoteInput, "medium", True, "local_note_v1"),
    "file": CapabilitySpec("file", "有限文件处理", "只处理已登记且同 scope 的 FileDocument，不访问任意主机路径。", FileInput, "low", False, "bounded_file_v1", timeout_seconds=30),
}

CONTRACT_VERSION = "bounded-tools.v1"


def requires_confirmation(capability: str, payload: dict) -> bool:
    spec = CAPABILITIES[capability]
    return spec.side_effect or (
        capability == "file" and payload.get("action") == "create_text_copy"
    )
