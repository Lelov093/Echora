from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.tools.weather_runtime import (
    ARCHIVE_ENDPOINT,
    FORECAST_ENDPOINT,
    MAX_FORECAST_DAYS,
    WeatherCapabilityError,
    build_location_queries,
    fetch_daily_weather,
    resolve_location,
)


class FakeClient:
    def __init__(self, handler):
        self.handler = handler
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict):
        self.calls.append((url, params))
        payload = self.handler(url, params)
        return httpx.Response(
            200,
            json=payload,
            request=httpx.Request("GET", url, params=params),
        )


@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("北京市海淀区", "海淀"),
        ("中国北京市", "北京"),
        ("法国巴黎", "巴黎"),
        ("Washington D.C.", "Washington"),
    ],
)
def test_location_queries_are_derived_from_general_syntax(
    location: str,
    expected: str,
) -> None:
    values = {item.value for item in build_location_queries(location)}
    assert expected in values


def test_resolver_uses_bounded_candidates_and_records_safe_observation() -> None:
    def handler(_url: str, params: dict):
        if params["name"] != "海淀":
            return {}
        return {
            "results": [
                {
                    "id": 1,
                    "name": "海淀",
                    "country": "中国",
                    "country_code": "CN",
                    "admin1": "北京市",
                    "feature_code": "PPLA3",
                    "latitude": 39.96,
                    "longitude": 116.30,
                    "timezone": "Asia/Shanghai",
                }
            ]
        }

    client = FakeClient(handler)
    place, observation = resolve_location(client, "北京市海淀区")

    assert place["name"] == "海淀"
    assert observation["resolution_status"] == "resolved"
    assert observation["selected_query"] == "海淀"
    assert 1 <= len(observation["attempts"]) <= 6
    assert all("query" in item and "result_count" in item for item in observation["attempts"])


def test_resolver_fails_closed_for_close_cross_region_candidates() -> None:
    def handler(_url: str, _params: dict):
        return {
            "results": [
                {
                    "id": 1,
                    "name": "Springfield",
                    "country": "United States",
                    "country_code": "US",
                    "admin1": "State A",
                    "feature_code": "PPLA2",
                    "latitude": 1.0,
                    "longitude": 1.0,
                    "population": 10_000,
                    "timezone": "UTC",
                },
                {
                    "id": 2,
                    "name": "Springfield",
                    "country": "United States",
                    "country_code": "US",
                    "admin1": "State B",
                    "feature_code": "PPLA2",
                    "latitude": 2.0,
                    "longitude": 2.0,
                    "population": 9_900,
                    "timezone": "UTC",
                },
            ]
        }

    with pytest.raises(WeatherCapabilityError) as raised:
        resolve_location(FakeClient(handler), "Springfield")

    assert raised.value.code == "WEATHER_LOCATION_AMBIGUOUS"
    assert len(raised.value.details["candidates"]) == 3 or len(
        raised.value.details["candidates"]
    ) == 2


def test_recent_past_routes_through_forecast_past_days() -> None:
    local_today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    target = local_today - timedelta(days=1)

    def handler(url: str, params: dict):
        assert url == FORECAST_ENDPOINT
        assert params["past_days"] == 1
        return {
            "daily": {
                "time": [target.isoformat()],
                "weather_code": [3],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [17.0],
                "precipitation_probability_max": [20],
                "precipitation_sum": [0.2],
                "wind_speed_10m_max": [10.0],
            }
        }

    result, observation = fetch_daily_weather(
        FakeClient(handler),
        _place(),
        target,
    )

    assert result["date"] == target.isoformat()
    assert result["data_route"] == "forecast"
    assert observation["data_route"] == "forecast"


def test_older_history_routes_through_archive() -> None:
    target = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=100)

    def handler(url: str, params: dict):
        assert url == ARCHIVE_ENDPOINT
        assert params["start_date"] == target.isoformat()
        return {
            "daily": {
                "time": [target.isoformat()],
                "weather_code": [2],
                "temperature_2m_max": [20.0],
                "temperature_2m_min": [10.0],
                "precipitation_sum": [1.2],
                "wind_speed_10m_max": [12.0],
            }
        }

    result, observation = fetch_daily_weather(
        FakeClient(handler),
        _place(),
        target,
    )

    assert result["data_route"] == "archive"
    assert result["precipitation_probability_percent"] is None
    assert result["precipitation_sum_mm"] == 1.2
    assert observation["data_route"] == "archive"


def test_future_out_of_range_reports_real_support_window() -> None:
    local_today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    target = local_today + timedelta(days=MAX_FORECAST_DAYS)

    with pytest.raises(WeatherCapabilityError) as raised:
        fetch_daily_weather(FakeClient(lambda *_args: {}), _place(), target)

    assert raised.value.code == "WEATHER_DATE_OUT_OF_RANGE"
    assert raised.value.details["forecast_days"] == MAX_FORECAST_DAYS
    assert raised.value.details["requested_date"] == target.isoformat()


def _place() -> dict:
    return {
        "name": "Test Place",
        "country": "Test Country",
        "admin1": "Test Admin",
        "latitude": 39.9,
        "longitude": 116.4,
        "timezone": "Asia/Shanghai",
    }
