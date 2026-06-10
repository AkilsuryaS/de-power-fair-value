from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Dict

import pandas as pd
import requests
from requests import HTTPError

from power_fair_value.config import project_path
from power_fair_value.utils import ensure_dir, read_json, write_json


BASE_URL = "https://api.energy-charts.info"
FORECAST_TYPES = {
    "load": "load_da_forecast_mw",
    "wind_onshore": "wind_onshore_da_forecast_mw",
    "wind_offshore": "wind_offshore_da_forecast_mw",
    "solar": "solar_da_forecast_mw",
}


def _cache_path(config: Dict[str, Any], stem: str) -> Path:
    raw_dir = project_path(config, config["data"]["raw_dir"])
    ensure_dir(raw_dir)
    return raw_dir / f"{stem}_{config['data']['start']}_{config['data']['end']}.json"


def fetch_json(
    endpoint: str,
    params: Dict[str, Any],
    cache_path: Path,
    force_refresh: bool = False,
    max_attempts: int = 6,
) -> Dict[str, Any]:
    if cache_path.exists() and not force_refresh:
        return read_json(cache_path)

    response = None
    for attempt in range(max_attempts):
        response = requests.get(f"{BASE_URL}{endpoint}", params=params, timeout=120)
        if response.status_code not in {429, 500, 502, 503, 504}:
            break
        retry_after = response.headers.get("Retry-After")
        sleep_seconds = int(retry_after) if retry_after and retry_after.isdigit() else min(60, 5 * (attempt + 1))
        time.sleep(sleep_seconds)

    assert response is not None
    response.raise_for_status()
    payload = response.json()
    write_json(cache_path, payload)
    return payload


def _time_frame(unix_seconds: list[int], values: list[float], column: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_utc": pd.to_datetime(unix_seconds, unit="s", utc=True),
            column: values,
        }
    )


def fetch_prices(config: Dict[str, Any]) -> tuple[pd.DataFrame, Dict[str, Any]]:
    params = {
        "bzn": config["market"]["bidding_zone"],
        "start": config["data"]["start"],
        "end": config["data"]["end"],
    }
    payload = fetch_json(
        "/price",
        params,
        _cache_path(config, "price"),
        config["data"].get("force_refresh", False),
    )
    frame = _time_frame(payload["unix_seconds"], payload["price"], "da_price_eur_mwh")
    frame = (
        frame.set_index("timestamp_utc")
        .resample("h")
        .mean()
        .reset_index()
    )
    metadata = {
        "endpoint": "/price",
        "params": params,
        "license_info": payload.get("license_info"),
        "unit": payload.get("unit"),
        "deprecated": payload.get("deprecated"),
        "source_url": f"{BASE_URL}/price",
        "cleaning": "Sub-hourly price rows, if present, are averaged to hourly delivery values.",
    }
    return frame, metadata


def fetch_driver(config: Dict[str, Any], production_type: str, column: str) -> pd.DataFrame:
    full_params = {
        "country": config["market"]["country"],
        "production_type": production_type,
        "forecast_type": "day-ahead",
        "start": config["data"]["start"],
        "end": config["data"]["end"],
    }
    try:
        payload = fetch_json(
            "/public_power_forecast",
            full_params,
            _cache_path(config, f"forecast_{production_type}"),
            config["data"].get("force_refresh", False),
            max_attempts=4,
        )
        frame = _time_frame(payload["unix_seconds"], payload["forecast_values"], column)
        return (
            frame.set_index("timestamp_utc")
            .resample("h")
            .mean()
            .reset_index()
        )
    except HTTPError:
        pass

    frames = []
    for chunk_start, chunk_end in _date_chunks(config["data"]["start"], config["data"]["end"], months=3):
        params = {
            "country": config["market"]["country"],
            "production_type": production_type,
            "forecast_type": "day-ahead",
            "start": chunk_start,
            "end": chunk_end,
        }
        payload = fetch_json(
            "/public_power_forecast",
            params,
            _cache_path(config, f"forecast_{production_type}_{chunk_start}_{chunk_end}"),
            config["data"].get("force_refresh", False),
            max_attempts=3,
        )
        frames.append(_time_frame(payload["unix_seconds"], payload["forecast_values"], column))
        time.sleep(3.0)

    frame = pd.concat(frames, ignore_index=True).drop_duplicates("timestamp_utc")
    return (
        frame.set_index("timestamp_utc")
        .resample("h")
        .mean()
        .reset_index()
    )


def _date_chunks(start: str, end: str, months: int) -> list[tuple[str, str]]:
    chunks = []
    current = pd.Timestamp(start)
    final = pd.Timestamp(end)
    while current <= final:
        chunk_end = min(current + pd.DateOffset(months=months) - pd.Timedelta(days=1), final)
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = chunk_end + pd.Timedelta(days=1)
    return chunks


def build_dataset(config: Dict[str, Any]) -> pd.DataFrame:
    prices, price_metadata = fetch_prices(config)
    dataset = prices.copy()

    source_metadata = {
        "price": price_metadata,
        "drivers": [],
        "notes": [
            "Price target is Energy-Charts /price day-ahead spot price for DE-LU.",
            "Driver features use Energy-Charts /public_power_forecast with forecast_type=day-ahead.",
            "15-minute driver forecasts are averaged to hourly timestamps before merging to hourly price.",
        ],
    }

    for production_type, column in FORECAST_TYPES.items():
        driver = fetch_driver(config, production_type, column)
        dataset = dataset.merge(driver, on="timestamp_utc", how="left")
        source_metadata["drivers"].append(
            {
                "endpoint": "/public_power_forecast",
                "production_type": production_type,
                "column": column,
                "source_url": f"{BASE_URL}/public_power_forecast",
            }
        )

    tz = config["market"]["timezone"]
    dataset = dataset.sort_values("timestamp_utc").reset_index(drop=True)
    dataset["timestamp_local"] = dataset["timestamp_utc"].dt.tz_convert(tz)
    dataset["date_local"] = dataset["timestamp_local"].dt.strftime("%Y-%m-%d")
    dataset["hour_local"] = dataset["timestamp_local"].dt.hour
    dataset["day_of_week"] = dataset["timestamp_local"].dt.dayofweek
    dataset["month"] = dataset["timestamp_local"].dt.month
    dataset["is_weekend"] = dataset["day_of_week"].isin([5, 6]).astype(int)

    dataset["wind_total_da_forecast_mw"] = (
        dataset["wind_onshore_da_forecast_mw"] + dataset["wind_offshore_da_forecast_mw"]
    )
    dataset["renewables_da_forecast_mw"] = (
        dataset["wind_total_da_forecast_mw"] + dataset["solar_da_forecast_mw"]
    )
    dataset["residual_load_da_forecast_mw"] = (
        dataset["load_da_forecast_mw"] - dataset["renewables_da_forecast_mw"]
    )

    processed_dir = project_path(config, config["data"]["processed_dir"])
    ensure_dir(processed_dir)
    dataset.to_csv(processed_dir / "de_lu_hourly_dataset.csv", index=False)
    write_json(project_path(config, "outputs/qa/source_metadata.json"), source_metadata)
    return dataset
