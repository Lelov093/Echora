"""General, bounded weather location resolution and date routing."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx


GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"
MAX_GEOCODING_QUERIES = 6
MAX_GEOCODING_RESULTS = 10
MAX_FORECAST_DAYS = 16
MAX_RECENT_PAST_DAYS = 92
EARLIEST_ARCHIVE_DATE = date(1940, 1, 1)
FORECAST_DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,precipitation_sum,wind_speed_10m_max"
)
ARCHIVE_DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_sum,wind_speed_10m_max"
)
_CJK = re.compile(r"[\u3400-\u9fff]")
_ADMIN_SUFFIX = re.compile(
    r"(?:特别行政区|壮族自治区|回族自治区|维吾尔自治区|自治区|自治州|"
    r"地区|省|市|区|县|州|盟|旗)$"
)
_ADMIN_SEGMENT = re.compile(
    r"[^省市区县州盟旗]+(?:特别行政区|自治区|自治州|地区|省|市|区|县|州|盟|旗)"
)
_LATIN_STOPWORDS = {"of", "the", "de", "la", "le", "and"}
_CAPITAL_FEATURES = {"PPLC", "PPLA", "PPLA2", "PPLA3", "PPLA4"}


class WeatherCapabilityError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class LocationQuery:
    value: str
    reason: str


def build_location_queries(location: str) -> list[LocationQuery]:
    """Generate bounded candidates from syntax, never from city-specific aliases."""
    raw = unicodedata.normalize("NFKC", location).strip()
    compact = re.sub(r"\s+", " ", raw)
    candidates: list[LocationQuery] = []

    def add(value: str, reason: str) -> None:
        cleaned = re.sub(r"\s+", " ", value).strip(" ,，。.-")
        if len(cleaned) < 2:
            return
        normalized = _match_text(cleaned)
        if normalized and all(_match_text(item.value) != normalized for item in candidates):
            candidates.append(LocationQuery(cleaned, reason))

    add(compact, "original")
    punctuation_folded = re.sub(r"[._,/，。]+", " ", compact)
    add(punctuation_folded, "punctuation_folded")

    if _CJK.search(compact):
        no_spaces = compact.replace(" ", "")
        add(_ADMIN_SUFFIX.sub("", no_spaces), "administrative_suffix_removed")
        segments = _ADMIN_SEGMENT.findall(no_spaces)
        for segment in reversed(segments):
            add(_ADMIN_SUFFIX.sub("", segment), "administrative_segment")
        # CJK country and administrative prefixes are often concatenated. Bounded
        # tail candidates recover the actual place token without maintaining a
        # country/city alias registry.
        for width in (2, 3, 4, 5):
            if len(no_spaces) > width:
                add(_ADMIN_SUFFIX.sub("", no_spaces[-width:]), "bounded_cjk_tail")
    else:
        tokens = re.findall(r"[A-Za-z0-9À-ÖØ-öø-ÿ]+", punctuation_folded)
        meaningful = [
            token for token in tokens
            if len(token) > 1 and token.casefold() not in _LATIN_STOPWORDS
        ]
        if meaningful:
            add(" ".join(meaningful), "single_letter_abbreviation_removed")
            add(meaningful[0], "leading_place_token")
            add(meaningful[-1], "trailing_place_token")

    return candidates[:MAX_GEOCODING_QUERIES]


def resolve_location(
    client: httpx.Client,
    location: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    queries = build_location_queries(location)
    attempts: list[dict[str, Any]] = []
    candidates: dict[str, tuple[float, dict[str, Any], str]] = {}
    original = unicodedata.normalize("NFKC", location).strip()

    for query in queries:
        language = "zh" if _CJK.search(query.value) else "en"
        response = client.get(
            GEOCODING_ENDPOINT,
            params={
                "name": query.value,
                "count": MAX_GEOCODING_RESULTS,
                "language": language,
                "format": "json",
            },
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        attempts.append({
            "query": query.value,
            "reason": query.reason,
            "result_count": len(results),
            "language": language,
        })
        for place in results:
            if not _valid_place(place):
                continue
            key = str(place.get("id") or f"{place['latitude']}:{place['longitude']}")
            score = _place_score(original, query.value, place)
            current = candidates.get(key)
            if current is None or score > current[0]:
                candidates[key] = (score, place, query.value)
        if candidates:
            # The first successful syntactic candidate is the most specific
            # bounded interpretation. Rank within that result set instead of
            # broadening the query and overriding it with a less specific city.
            break

    ranked = sorted(
        candidates.values(),
        key=lambda item: (
            item[0],
            int(item[1].get("population") or 0),
        ),
        reverse=True,
    )
    safe_attempts = attempts[:MAX_GEOCODING_QUERIES]
    if not ranked:
        raise WeatherCapabilityError(
            "WEATHER_LOCATION_NOT_FOUND",
            "没有找到这个地点。",
            {
                "resolution_status": "not_found",
                "original_location": original,
                "attempts": safe_attempts,
                "query_budget": MAX_GEOCODING_QUERIES,
            },
        )

    top_score, top, selected_query = ranked[0]
    exact_original_match = (
        bool(attempts)
        and attempts[0]["result_count"] == 1
        and _match_text(selected_query) == _match_text(original)
        and _match_text(top.get("name")) == _match_text(original)
    )
    ambiguous = (
        False
        if exact_original_match
        else _ambiguous(top_score, top, ranked[1:4])
    )
    if ambiguous:
        raise WeatherCapabilityError(
            "WEATHER_LOCATION_AMBIGUOUS",
            "找到多个可能的地点，需要补充国家、州省或城市信息。",
            {
                "resolution_status": "ambiguous",
                "original_location": original,
                "attempts": safe_attempts,
                "candidates": [_safe_place(item[1]) for item in ranked[:3]],
            },
        )

    observation = {
        "resolution_status": "resolved",
        "original_location": original,
        "selected_query": selected_query,
        "attempts": safe_attempts,
        "canonical_location": _safe_place(top),
        "candidate_count": len(ranked),
    }
    return top, observation


def fetch_daily_weather(
    client: httpx.Client,
    place: dict[str, Any],
    requested_date: str | date | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    timezone_name = str(place.get("timezone") or "UTC")
    try:
        local_today = datetime.now(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:
        timezone_name = "UTC"
        local_today = datetime.now(ZoneInfo("UTC")).date()
    target = (
        requested_date
        if isinstance(requested_date, date)
        else date.fromisoformat(str(requested_date))
        if requested_date
        else local_today
    )
    delta = (target - local_today).days

    base_params = {
        "latitude": place["latitude"],
        "longitude": place["longitude"],
        "timezone": timezone_name,
    }
    if delta > MAX_FORECAST_DAYS - 1:
        raise WeatherCapabilityError(
            "WEATHER_DATE_OUT_OF_RANGE",
            "天气日期超出当前可查询的未来范围。",
            _date_range_details(local_today, target, timezone_name),
        )
    if target < EARLIEST_ARCHIVE_DATE:
        raise WeatherCapabilityError(
            "WEATHER_DATE_OUT_OF_RANGE",
            "天气日期早于当前历史数据支持范围。",
            _date_range_details(local_today, target, timezone_name),
        )

    if delta >= -MAX_RECENT_PAST_DAYS:
        route = "forecast"
        params = {
            **base_params,
            "daily": FORECAST_DAILY_FIELDS,
            "forecast_days": max(1, delta + 1),
            "past_days": max(0, -delta),
        }
        endpoint = FORECAST_ENDPOINT
    else:
        route = "archive"
        params = {
            **base_params,
            "daily": ARCHIVE_DAILY_FIELDS,
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
        }
        endpoint = ARCHIVE_ENDPOINT

    response = client.get(endpoint, params=params)
    response.raise_for_status()
    daily = response.json().get("daily") or {}
    dates = daily.get("time") or []
    target_text = target.isoformat()
    if target_text not in dates:
        raise WeatherCapabilityError(
            "WEATHER_DATE_UNAVAILABLE",
            "天气服务没有返回请求日期的数据。",
            {
                **_date_range_details(local_today, target, timezone_name),
                "data_route": route,
                "returned_start": dates[0] if dates else None,
                "returned_end": dates[-1] if dates else None,
            },
        )
    index = dates.index(target_text)
    result = {
        "location": place.get("name"),
        "country": place.get("country"),
        "admin1": place.get("admin1"),
        "date": target_text,
        "timezone": timezone_name,
        "data_route": route,
        "weather_code": _daily_value(daily, "weather_code", index),
        "temperature_max_c": _daily_value(daily, "temperature_2m_max", index),
        "temperature_min_c": _daily_value(daily, "temperature_2m_min", index),
        "precipitation_probability_percent": _daily_value(
            daily, "precipitation_probability_max", index
        ),
        "precipitation_sum_mm": _daily_value(daily, "precipitation_sum", index),
        "wind_speed_max_kmh": _daily_value(daily, "wind_speed_10m_max", index),
    }
    observation = {
        "data_route": route,
        "requested_date": target_text,
        "location_local_today": local_today.isoformat(),
        "timezone": timezone_name,
        "supported_history_start": EARLIEST_ARCHIVE_DATE.isoformat(),
        "supported_forecast_end": (
            date.fromordinal(local_today.toordinal() + MAX_FORECAST_DAYS - 1)
        ).isoformat(),
        "provider": "Open-Meteo",
    }
    return result, observation


def _place_score(original: str, query: str, place: dict[str, Any]) -> float:
    original_text = _match_text(original)
    query_text = _match_text(query)
    name = _match_text(place.get("name"))
    score = 0.0
    if query_text and query_text == name:
        score += 8.0
    elif query_text and (query_text in name or name in query_text):
        score += 5.0
    for key, weight in (("country", 5.0), ("admin1", 3.0), ("admin2", 2.0)):
        value = _match_text(place.get(key))
        if value and value in original_text:
            score += weight
    initials = _initials(str(place.get("admin1") or ""))
    if len(initials) >= 2 and initials in original_text:
        score += 3.0
    if place.get("feature_code") in _CAPITAL_FEATURES:
        score += 1.5
    score += _granularity_bonus(original, str(place.get("feature_code") or ""))
    population = int(place.get("population") or 0)
    if population > 0:
        score += min(2.0, math.log10(population + 1) / 4)
    return score


def _granularity_bonus(original: str, feature_code: str) -> float:
    compact = re.sub(r"\s+", "", original)
    if compact.endswith(("区", "县", "旗")):
        return 5.0 if feature_code in {"PPLA3", "PPLA4", "ADM3", "ADM4"} else 0.0
    if compact.endswith(("市", "城", "镇")):
        return 2.0 if feature_code.startswith("PPL") else 0.0
    if compact.endswith(("省", "州", "自治区")):
        return 2.0 if feature_code in {"ADM1", "PPLA"} else 0.0
    return 0.0


def _ambiguous(
    top_score: float,
    top: dict[str, Any],
    others: list[tuple[float, dict[str, Any], str]],
) -> bool:
    for score, place, _query in others:
        if top_score - score >= 1.5:
            continue
        if (
            place.get("country_code") != top.get("country_code")
            or place.get("admin1") != top.get("admin1")
        ):
            return True
    return False


def _safe_place(place: dict[str, Any]) -> dict[str, Any]:
    return {
        key: place.get(key)
        for key in (
            "id", "name", "country", "country_code", "admin1", "admin2",
            "feature_code", "timezone", "latitude", "longitude",
        )
        if place.get(key) is not None
    }


def _valid_place(place: dict[str, Any]) -> bool:
    return (
        isinstance(place, dict)
        and isinstance(place.get("latitude"), (int, float))
        and isinstance(place.get("longitude"), (int, float))
        and bool(place.get("name"))
    )


def _date_range_details(
    local_today: date,
    target: date,
    timezone_name: str,
) -> dict[str, Any]:
    return {
        "requested_date": target.isoformat(),
        "location_local_today": local_today.isoformat(),
        "timezone": timezone_name,
        "supported_history_start": EARLIEST_ARCHIVE_DATE.isoformat(),
        "supported_forecast_end": date.fromordinal(
            local_today.toordinal() + MAX_FORECAST_DAYS - 1
        ).isoformat(),
        "forecast_days": MAX_FORECAST_DAYS,
        "recent_past_days": MAX_RECENT_PAST_DAYS,
    }


def _daily_value(daily: dict[str, Any], key: str, index: int) -> Any:
    values = daily.get(key)
    return values[index] if isinstance(values, list) and len(values) > index else None


def _match_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def _initials(value: str) -> str:
    words = [
        word for word in re.findall(r"[A-Za-z]+", value)
        if word.casefold() not in _LATIN_STOPWORDS
    ]
    return "".join(word[0].casefold() for word in words)
