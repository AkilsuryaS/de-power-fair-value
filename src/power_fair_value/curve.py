from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def peak_mask(df: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
    start = int(config["curve"]["peak_start_hour"])
    end = int(config["curve"]["peak_end_hour"])
    return (df["hour_local"] >= start) & (df["hour_local"] < end) & (df["is_weekend"] == 0)


def summarize_strip(df: pd.DataFrame, value_col: str, config: Dict[str, Any]) -> Dict[str, float]:
    peak = peak_mask(df, config)
    offpeak = ~peak
    return {
        "base": float(df[value_col].mean()),
        "peak": float(df.loc[peak, value_col].mean()) if peak.any() else float("nan"),
        "offpeak": float(df.loc[offpeak, value_col].mean()) if offpeak.any() else float("nan"),
        "min_hour": float(df[value_col].min()),
        "max_hour": float(df[value_col].max()),
    }


def _proxy_curve_mark(
    feature_df: pd.DataFrame,
    forecast_date: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    hist = feature_df[feature_df["date_local"] < forecast_date].tail(24 * 7).copy()
    summary = summarize_strip(hist, "da_price_eur_mwh", config)
    return {
        "source": "trailing_7d_day_ahead_proxy",
        "front_week_base_eur_mwh": summary["base"],
        "front_week_peak_eur_mwh": summary["peak"],
    }


def translate_to_curve_view(
    forecast_day: pd.DataFrame,
    feature_df: pd.DataFrame,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    forecast_date = config["data"]["forecast_date"]
    fair_value = summarize_strip(forecast_day, "y_pred", config)
    actual = summarize_strip(forecast_day, "da_price_eur_mwh", config)

    curve_cfg = config["curve"]
    marks = {
        "source": "config_curve_mark",
        "front_week_base_eur_mwh": curve_cfg.get("front_week_base_eur_mwh"),
        "front_week_peak_eur_mwh": curve_cfg.get("front_week_peak_eur_mwh"),
    }
    if marks["front_week_base_eur_mwh"] is None or marks["front_week_peak_eur_mwh"] is None:
        marks = _proxy_curve_mark(feature_df, forecast_date, config)

    threshold = float(curve_cfg["threshold_eur_mwh"])
    base_edge = fair_value["base"] - float(marks["front_week_base_eur_mwh"])
    peak_edge = fair_value["peak"] - float(marks["front_week_peak_eur_mwh"])

    def call(edge: float, bucket: str) -> str:
        if edge > threshold:
            return f"Long prompt {bucket}: model fair value is {edge:.2f} EUR/MWh above the curve mark."
        if edge < -threshold:
            return f"Short prompt {bucket}: model fair value is {abs(edge):.2f} EUR/MWh below the curve mark."
        return f"Neutral prompt {bucket}: edge of {edge:.2f} EUR/MWh is inside the threshold."

    return {
        "forecast_date": forecast_date,
        "fair_value": fair_value,
        "actual_if_available": actual,
        "curve_marks": marks,
        "threshold_eur_mwh": threshold,
        "edges": {
            "base_eur_mwh": float(base_edge),
            "peak_eur_mwh": float(peak_edge),
        },
        "positioning": {
            "base": call(base_edge, "base"),
            "peak": call(peak_edge, "peak"),
        },
        "invalidations": [
            "Day-ahead load, wind, or solar forecast revisions move residual load by more than 2 GW.",
            "Prompt curve broker marks move by more than the configured edge threshold before execution.",
            "Recent model errors widen materially versus validation MAE, especially in scarcity or negative-price hours.",
            "Fuel, carbon, outage, or interconnector news changes marginal plant economics after the data pull.",
        ],
    }
