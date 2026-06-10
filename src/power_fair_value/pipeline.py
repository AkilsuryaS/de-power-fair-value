from __future__ import annotations

import argparse
from typing import Any, Dict

import pandas as pd

from power_fair_value.config import load_config, project_path
from power_fair_value.curve import translate_to_curve_view
from power_fair_value.data import build_dataset
from power_fair_value.features import build_features
from power_fair_value.llm import generate_trading_memo
from power_fair_value.models import forecast_delivery_day, validate_models
from power_fair_value.qa import run_qa
from power_fair_value.report import generate_report, plot_outputs
from power_fair_value.utils import ensure_dir, read_json, write_json


def _metrics_context(metrics: pd.DataFrame) -> Dict[str, float]:
    improved_model = (
        metrics.loc[
            (metrics["segment"] == "all_hours") & (metrics["model"] != "baseline_lag_24h"),
            "model",
        ]
        .iloc[0]
    )

    def lookup(model: str, field: str) -> float:
        row = metrics[(metrics["model"] == model) & (metrics["segment"] == "all_hours")]
        return float(row.iloc[0][field])

    return {
        "baseline_all_hours_mae": lookup("baseline_lag_24h", "mae"),
        "improved_all_hours_mae": lookup(improved_model, "mae"),
        "baseline_all_hours_rmse": lookup("baseline_lag_24h", "rmse"),
        "improved_all_hours_rmse": lookup(improved_model, "rmse"),
        "improved_model": improved_model,
    }


def run_pipeline(config_path: str) -> Dict[str, Any]:
    config = load_config(config_path)
    for path in [
        "data/raw",
        "data/processed",
        "outputs/qa",
        "outputs/metrics",
        "outputs/predictions",
        "outputs/figures",
        "outputs/llm",
        "docs",
    ]:
        ensure_dir(project_path(config, path))

    print("Fetching and assembling dataset...")
    dataset = build_dataset(config)
    print(f"Dataset rows: {len(dataset)}")

    print("Running QA checks...")
    qa_report = run_qa(dataset, config)

    print("Building model features...")
    feature_df = build_features(dataset)
    feature_df.to_csv(project_path(config, "data/processed/model_features.csv"), index=False)

    print("Validating baseline and improved models...")
    metrics, backtest_predictions = validate_models(feature_df, config)

    print("Forecasting fair-value delivery day...")
    forecast_day = forecast_delivery_day(feature_df, config)

    print("Translating forecast into prompt curve view...")
    curve_view = translate_to_curve_view(forecast_day, feature_df, config)
    write_json(project_path(config, "outputs/predictions/curve_view.json"), curve_view)

    print("Generating AI-assisted memo...")
    llm_context = {
        "market": config["market"],
        "qa_status": qa_report["status"],
        "validation_metrics": _metrics_context(metrics),
        "curve_view": curve_view,
    }
    llm_record = generate_trading_memo(llm_context, config)

    print("Writing figures and report...")
    split_info = read_json(project_path(config, "outputs/metrics/validation_split.json"))
    figures = plot_outputs(backtest_predictions, forecast_day, config)
    report_path = generate_report(config, qa_report, metrics, curve_view, llm_record, figures, split_info)

    return {
        "dataset": str(project_path(config, "data/processed/de_lu_hourly_dataset.csv")),
        "metrics": str(project_path(config, "outputs/metrics/validation_metrics.csv")),
        "fair_value": str(project_path(config, "outputs/predictions/daily_fair_value.csv")),
        "submission": str(project_path(config, "data/processed/submission.csv")),
        "report": report_path,
        "llm_provider_used": llm_record["provider_used"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the DE-LU power fair-value pipeline.")
    parser.add_argument("--config", default="configs/default.yml", help="Path to YAML config.")
    args = parser.parse_args()
    outputs = run_pipeline(args.config)
    print("\nPipeline complete:")
    for key, value in outputs.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
