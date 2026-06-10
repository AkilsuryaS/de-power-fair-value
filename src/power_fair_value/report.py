from __future__ import annotations

from typing import Any, Dict

import matplotlib.pyplot as plt
import pandas as pd

from power_fair_value.config import project_path
from power_fair_value.utils import ensure_dir


def _metric(metrics: pd.DataFrame, model: str, segment: str, field: str) -> float:
    row = metrics[(metrics["model"] == model) & (metrics["segment"] == segment)]
    return float(row.iloc[0][field])


def plot_outputs(
    backtest_predictions: pd.DataFrame,
    forecast_day: pd.DataFrame,
    config: Dict[str, Any],
) -> Dict[str, str]:
    fig_dir = project_path(config, "outputs/figures")
    ensure_dir(fig_dir)

    tail = backtest_predictions.tail(24 * 14)
    plt.figure(figsize=(11, 4))
    plt.plot(pd.to_datetime(tail["timestamp_utc"]), tail["da_price_eur_mwh"], label="Actual", linewidth=1.4)
    plt.plot(pd.to_datetime(tail["timestamp_utc"]), tail["hist_gradient_boosting"], label="Improved model", linewidth=1.2)
    plt.title("Validation Window: Actual vs Improved Model")
    plt.ylabel("EUR/MWh")
    plt.legend()
    plt.tight_layout()
    validation_path = fig_dir / "validation_actual_vs_pred.png"
    plt.savefig(validation_path, dpi=160)
    plt.close()

    plt.figure(figsize=(10, 4))
    plt.plot(forecast_day["hour_local"], forecast_day["y_pred"], marker="o", label="Fair value")
    plt.plot(forecast_day["hour_local"], forecast_day["da_price_eur_mwh"], marker="x", label="Actual if available")
    plt.title(f"Hourly Fair Value: {config['data']['forecast_date']}")
    plt.xlabel("Local hour")
    plt.ylabel("EUR/MWh")
    plt.legend()
    plt.tight_layout()
    forecast_path = fig_dir / "daily_fair_value_shape.png"
    plt.savefig(forecast_path, dpi=160)
    plt.close()

    return {
        "validation_plot": str(validation_path.relative_to(project_path(config))),
        "forecast_plot": str(forecast_path.relative_to(project_path(config))),
    }


def generate_report(
    config: Dict[str, Any],
    qa_report: Dict[str, Any],
    metrics: pd.DataFrame,
    curve_view: Dict[str, Any],
    llm_record: Dict[str, Any],
    figure_paths: Dict[str, str],
) -> str:
    docs_dir = project_path(config, "docs")
    ensure_dir(docs_dir)

    baseline_mae = _metric(metrics, "baseline_lag_24h", "all_hours", "mae")
    improved_mae = _metric(metrics, "hist_gradient_boosting", "all_hours", "mae")
    baseline_rmse = _metric(metrics, "baseline_lag_24h", "all_hours", "rmse")
    improved_rmse = _metric(metrics, "hist_gradient_boosting", "all_hours", "rmse")

    fv = curve_view["fair_value"]
    edges = curve_view["edges"]
    marks = curve_view["curve_marks"]
    project = config["project"]

    markdown = f"""# {project['title']}

**Name:** {project['author_name']}  
**Email:** {project['author_email']}  
**Market:** {config['market']['name']} (`{config['market']['bidding_zone']}`)  
**Run window:** `{config['data']['start']}` to `{config['data']['end']}`; fair-value date `{config['data']['forecast_date']}`

## Data And QA

The dataset is hourly DE-LU day-ahead price with day-ahead forecast drivers for load, wind onshore, wind offshore, and solar. Sources are the public Fraunhofer Energy-Charts API: `/price` for day-ahead spot prices and `/public_power_forecast` for fundamental forecasts. Price data for DE-LU is licensed CC BY 4.0 from Bundesnetzagentur/SMARD.de as reported by the API.

QA status: **{qa_report['status'].upper()}** across `{qa_report['rows']}` hourly rows. Checks cover required columns, duplicate timestamps, hourly UTC cadence, missing values, price bounds, and non-negative driver forecasts. Full QA output is in `outputs/qa/qa_report.md`.

## Forecasting

Baseline model: same-hour previous-day price (`lag_24h`). Improved model: histogram gradient boosting with calendar variables, lagged prices, rolling price means, and day-ahead load/wind/solar/residual-load forecasts. The final daily fair value is trained only on data before the fair-value date.

| Model | MAE | RMSE |
|---|---:|---:|
| Baseline lag 24h | {baseline_mae:.2f} | {baseline_rmse:.2f} |
| Improved gradient boosting | {improved_mae:.2f} | {improved_rmse:.2f} |

Validation plot: `{figure_paths['validation_plot']}`  
Daily shape plot: `{figure_paths['forecast_plot']}`

## DA-To-Curve View

For `{curve_view['forecast_date']}`, model fair value is **{fv['base']:.2f} EUR/MWh base** and **{fv['peak']:.2f} EUR/MWh peak**. Curve marks use `{marks['source']}`: base `{marks['front_week_base_eur_mwh']:.2f}`, peak `{marks['front_week_peak_eur_mwh']:.2f}` EUR/MWh.

Base edge: **{edges['base_eur_mwh']:.2f} EUR/MWh**. {curve_view['positioning']['base']}  
Peak edge: **{edges['peak_eur_mwh']:.2f} EUR/MWh**. {curve_view['positioning']['peak']}

Use: compare the forecast strip with executable prompt-week/base and peak marks to decide whether the prompt curve is cheap or rich versus expected cash settlement. Invalidate the view if residual-load forecasts revise by more than 2 GW, curve marks move by more than the edge threshold, or new fuel/carbon/outage/interconnector information changes marginal pricing before execution.

## AI/LLM Component

The pipeline includes `power_fair_value.llm.generate_trading_memo`, which sends QA, validation, and curve-view context to OpenAI when `OPENAI_API_KEY` is available. Prompts and outputs are logged in `outputs/llm/prompt_log.jsonl`; when no key is available, a deterministic offline memo is written so the pipeline remains reproducible. This reduces manual effort by drafting the desk-facing trading note from structured model outputs.

LLM provider used in this run: `{llm_record['provider_used']}`.
"""

    report_path = docs_dir / "fair_value_report.md"
    report_path.write_text(markdown, encoding="utf-8")
    return str(report_path)
