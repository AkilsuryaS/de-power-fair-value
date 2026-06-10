from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from power_fair_value.config import project_path
from power_fair_value.features import model_features
from power_fair_value.utils import ensure_dir, write_json


TARGET = "da_price_eur_mwh"


def _metrics(y_true: pd.Series, y_pred: pd.Series) -> Dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "bias": float(np.mean(y_pred - y_true)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def _build_model(config: Dict[str, Any]) -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.05,
        max_iter=350,
        max_leaf_nodes=31,
        l2_regularization=0.05,
        random_state=int(config["model"]["random_state"]),
    )


def _validation_cutoff(df: pd.DataFrame, test_days: int) -> str:
    unique_dates = sorted(df["date_local"].unique())
    if len(unique_dates) <= test_days + 8:
        raise ValueError("Not enough dates for the requested validation window.")
    return unique_dates[-test_days]


def _peak_mask(df: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
    start = int(config["curve"]["peak_start_hour"])
    end = int(config["curve"]["peak_end_hour"])
    return (df["hour_local"] >= start) & (df["hour_local"] < end) & (df["is_weekend"] == 0)


def validate_models(
    feature_df: pd.DataFrame,
    config: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    features = model_features()
    ready = feature_df.dropna(subset=features + [TARGET]).copy()
    cutoff_date = _validation_cutoff(ready, int(config["validation"]["test_days"]))

    train = ready[ready["date_local"] < cutoff_date]
    test = ready[ready["date_local"] >= cutoff_date]

    if train.empty or test.empty:
        raise ValueError("Empty train or test split after feature preparation.")

    baseline_pred = test["price_lag_24"].copy()
    model = _build_model(config)
    model.fit(train[features], train[TARGET])
    improved_pred = pd.Series(model.predict(test[features]), index=test.index)

    metrics_rows = []
    for segment, mask in {
        "all_hours": pd.Series(True, index=test.index),
        "peak_weekday": _peak_mask(test, config),
        "offpeak_or_weekend": ~_peak_mask(test, config),
    }.items():
        segment_test = test[mask]
        if segment_test.empty:
            continue
        metrics_rows.append({"model": "baseline_lag_24h", "segment": segment, **_metrics(segment_test[TARGET], baseline_pred[mask])})
        metrics_rows.append({"model": "hist_gradient_boosting", "segment": segment, **_metrics(segment_test[TARGET], improved_pred[mask])})

    metrics = pd.DataFrame(metrics_rows)

    predictions = test[
        [
            "timestamp_utc",
            "timestamp_local",
            "date_local",
            "hour_local",
            TARGET,
            "load_da_forecast_mw",
            "wind_total_da_forecast_mw",
            "solar_da_forecast_mw",
            "residual_load_da_forecast_mw",
        ]
    ].copy()
    predictions["baseline_lag_24h"] = baseline_pred
    predictions["hist_gradient_boosting"] = improved_pred

    out_dir = project_path(config, "outputs")
    ensure_dir(out_dir / "metrics")
    ensure_dir(out_dir / "predictions")
    metrics.to_csv(out_dir / "metrics/validation_metrics.csv", index=False)
    predictions.to_csv(out_dir / "predictions/backtest_predictions.csv", index=False)
    write_json(
        out_dir / "metrics/validation_split.json",
        {
            "cutoff_date": cutoff_date,
            "train_rows": len(train),
            "test_rows": len(test),
            "feature_columns": features,
        },
    )
    return metrics, predictions


def forecast_delivery_day(feature_df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    features = model_features()
    ready = feature_df.dropna(subset=features + [TARGET]).copy()
    forecast_date = config["data"]["forecast_date"]

    train = ready[ready["date_local"] < forecast_date]
    day = ready[ready["date_local"] == forecast_date].copy()
    if train.empty or day.empty:
        raise ValueError(f"Cannot train and forecast delivery date {forecast_date}.")

    model = _build_model(config)
    model.fit(train[features], train[TARGET])
    day["y_pred"] = model.predict(day[features])
    day["baseline_lag_24h"] = day["price_lag_24"]
    day["id"] = day["timestamp_local"].astype(str)

    out_dir = project_path(config, "outputs/predictions")
    ensure_dir(out_dir)
    day.to_csv(out_dir / "daily_fair_value.csv", index=False)
    day[["id", "y_pred"]].to_csv(project_path(config, "data/processed/submission.csv"), index=False)
    return day
