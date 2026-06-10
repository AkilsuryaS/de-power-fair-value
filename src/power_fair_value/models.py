from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from power_fair_value.config import project_path
from power_fair_value.features import model_features
from power_fair_value.utils import ensure_dir, write_json


TARGET = "da_price_eur_mwh"
BASELINE_MODEL_NAME = "baseline_lag_24h"
DEFAULT_IMPROVED_MODEL_NAME = "hist_gradient_boosting_absolute_error"


def _metrics(y_true: pd.Series, y_pred: pd.Series) -> Dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "bias": float(np.mean(y_pred - y_true)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def _candidate_models(config: Dict[str, Any]) -> Dict[str, Any]:
    random_state = int(config["model"]["random_state"])
    return {
        "hist_gradient_boosting_squared_error": HistGradientBoostingRegressor(
            loss="squared_error",
            learning_rate=0.05,
            max_iter=350,
            max_leaf_nodes=31,
            l2_regularization=0.05,
            random_state=random_state,
        ),
        "hist_gradient_boosting_absolute_error": HistGradientBoostingRegressor(
            loss="absolute_error",
            learning_rate=0.04,
            max_iter=500,
            max_leaf_nodes=31,
            min_samples_leaf=20,
            l2_regularization=0.05,
            random_state=random_state,
        ),
        "extra_trees": ExtraTreesRegressor(
            n_estimators=450,
            max_features=0.8,
            min_samples_leaf=2,
            random_state=random_state,
            n_jobs=-1,
        ),
        "gradient_boosting_huber": GradientBoostingRegressor(
            loss="huber",
            learning_rate=0.035,
            n_estimators=600,
            max_depth=3,
            subsample=0.85,
            random_state=random_state,
        ),
        "ridge_linear": make_pipeline(
            StandardScaler(),
            RidgeCV(alphas=np.logspace(-3, 3, 13)),
        ),
    }


def _build_model(config: Dict[str, Any], model_name: str | None = None) -> Any:
    candidates = _candidate_models(config)
    selected = model_name or DEFAULT_IMPROVED_MODEL_NAME
    if selected not in candidates:
        raise ValueError(f"Unknown model '{selected}'. Available: {sorted(candidates)}")
    return candidates[selected]


def _validation_cutoff(df: pd.DataFrame, test_days: int) -> str:
    unique_dates = sorted(df["date_local"].unique())
    if len(unique_dates) <= test_days + 8:
        raise ValueError("Not enough dates for the requested validation window.")
    return unique_dates[-test_days]


def _split_cutoffs(df: pd.DataFrame, test_days: int, tuning_days: int) -> Tuple[str, str]:
    unique_dates = sorted(df["date_local"].unique())
    if len(unique_dates) <= test_days + tuning_days + 8:
        raise ValueError("Not enough dates for the requested tuning and test windows.")
    test_cutoff = unique_dates[-test_days]
    tuning_cutoff = unique_dates[-(test_days + tuning_days)]
    return tuning_cutoff, test_cutoff


def _peak_mask(df: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
    start = int(config["curve"]["peak_start_hour"])
    end = int(config["curve"]["peak_end_hour"])
    return (df["hour_local"] >= start) & (df["hour_local"] < end) & (df["is_weekend"] == 0)


def _training_ready(feature_df: pd.DataFrame, config: Dict[str, Any], features: list[str]) -> pd.DataFrame:
    ready = feature_df.dropna(subset=features + [TARGET]).copy()
    training_start = config["model"].get("training_start")
    if training_start:
        ready = ready[ready["date_local"] >= training_start].copy()
    return ready


def validate_models(
    feature_df: pd.DataFrame,
    config: Dict[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    features = model_features()
    ready = _training_ready(feature_df, config, features)
    test_days = int(config["validation"]["test_days"])
    tuning_days = int(config["validation"].get("tuning_days", 30))
    tuning_cutoff, cutoff_date = _split_cutoffs(ready, test_days, tuning_days)

    selection_train = ready[ready["date_local"] < tuning_cutoff]
    tuning = ready[(ready["date_local"] >= tuning_cutoff) & (ready["date_local"] < cutoff_date)]
    train = ready[ready["date_local"] < cutoff_date]
    test = ready[ready["date_local"] >= cutoff_date]

    if selection_train.empty or tuning.empty or train.empty or test.empty:
        raise ValueError("Empty train, tuning, or test split after feature preparation.")

    selection_rows = []
    for model_name, model in _candidate_models(config).items():
        model.fit(selection_train[features], selection_train[TARGET])
        tuning_pred = pd.Series(model.predict(tuning[features]), index=tuning.index)
        selection_rows.append(
            {
                "model": model_name,
                "selection_segment": "tuning_window",
                **_metrics(tuning[TARGET], tuning_pred),
            }
        )

    selection = pd.DataFrame(selection_rows).sort_values(["mae", "rmse"]).reset_index(drop=True)
    selected_model_name = str(selection.iloc[0]["model"])

    baseline_pred = test["price_lag_24"].copy()
    model = _build_model(config, selected_model_name)
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
        metrics_rows.append({"model": BASELINE_MODEL_NAME, "segment": segment, **_metrics(segment_test[TARGET], baseline_pred[mask])})
        metrics_rows.append({"model": selected_model_name, "segment": segment, **_metrics(segment_test[TARGET], improved_pred[mask])})

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
    predictions[selected_model_name] = improved_pred
    predictions["selected_model_prediction"] = improved_pred

    out_dir = project_path(config, "outputs")
    ensure_dir(out_dir / "metrics")
    ensure_dir(out_dir / "predictions")
    metrics.to_csv(out_dir / "metrics/validation_metrics.csv", index=False)
    selection.to_csv(out_dir / "metrics/model_selection.csv", index=False)
    predictions.to_csv(out_dir / "predictions/backtest_predictions.csv", index=False)
    write_json(
        out_dir / "metrics/validation_split.json",
        {
            "cutoff_date": cutoff_date,
            "tuning_cutoff_date": tuning_cutoff,
            "selection_train_rows": len(selection_train),
            "tuning_rows": len(tuning),
            "train_rows": len(train),
            "test_rows": len(test),
            "feature_columns": features,
            "selected_model": selected_model_name,
            "selection_metric": "lowest tuning-window MAE",
            "training_start": config["model"].get("training_start"),
        },
    )
    return metrics, predictions


def select_model_for_forecast(ready: pd.DataFrame, config: Dict[str, Any], features: list[str]) -> str:
    forecast_date = config["data"]["forecast_date"]
    training_start = config["model"].get("training_start")
    history = ready[ready["date_local"] < forecast_date].copy()
    if training_start:
        history = history[history["date_local"] >= training_start].copy()
    tuning_days = int(config["validation"].get("tuning_days", 30))
    unique_dates = sorted(history["date_local"].unique())
    if len(unique_dates) <= tuning_days + 8:
        return DEFAULT_IMPROVED_MODEL_NAME

    tuning_cutoff = unique_dates[-tuning_days]
    selection_train = history[history["date_local"] < tuning_cutoff]
    tuning = history[history["date_local"] >= tuning_cutoff]
    if selection_train.empty or tuning.empty:
        return DEFAULT_IMPROVED_MODEL_NAME

    scores = []
    for model_name, model in _candidate_models(config).items():
        model.fit(selection_train[features], selection_train[TARGET])
        pred = model.predict(tuning[features])
        scores.append((mean_absolute_error(tuning[TARGET], pred), model_name))
    return min(scores)[1]


def forecast_delivery_day(feature_df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    features = model_features()
    ready = feature_df.dropna(subset=features + [TARGET]).copy()
    forecast_date = config["data"]["forecast_date"]
    training_start = config["model"].get("training_start")

    train = ready[ready["date_local"] < forecast_date]
    if training_start:
        train = train[train["date_local"] >= training_start]
    day = ready[ready["date_local"] == forecast_date].copy()
    if train.empty or day.empty:
        raise ValueError(f"Cannot train and forecast delivery date {forecast_date}.")

    selected_model_name = select_model_for_forecast(ready, config, features)
    model = _build_model(config, selected_model_name)
    model.fit(train[features], train[TARGET])
    day["y_pred"] = model.predict(day[features])
    day["baseline_lag_24h"] = day["price_lag_24"]
    day["selected_model"] = selected_model_name
    day["id"] = day["timestamp_local"].astype(str)

    out_dir = project_path(config, "outputs/predictions")
    ensure_dir(out_dir)
    day.to_csv(out_dir / "daily_fair_value.csv", index=False)
    day[["id", "y_pred"]].to_csv(project_path(config, "data/processed/submission.csv"), index=False)
    return day
