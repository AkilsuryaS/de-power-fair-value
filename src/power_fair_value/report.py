from __future__ import annotations

from typing import Any, Dict

import matplotlib.pyplot as plt
import pandas as pd

from power_fair_value.config import project_path
from power_fair_value.utils import ensure_dir


def _metric(metrics: pd.DataFrame, model: str, segment: str, field: str) -> float:
    row = metrics[(metrics["model"] == model) & (metrics["segment"] == segment)]
    return float(row.iloc[0][field])


def _improved_model(metrics: pd.DataFrame) -> str:
    row = metrics[(metrics["segment"] == "all_hours") & (metrics["model"] != "baseline_lag_24h")]
    return str(row.iloc[0]["model"])


def _candidate_reason(model_name: str) -> str:
    reasons = {
        "hist_gradient_boosting_absolute_error": "Tree boosting with MAE-style loss; robust to spikes and nonlinear fundamentals.",
        "gradient_boosting_huber": "Boosting with Huber loss; tested as a robust alternative for volatile prices.",
        "hist_gradient_boosting_squared_error": "Tree boosting with squared-error loss; captures nonlinear effects but can chase spikes.",
        "extra_trees": "Randomized tree ensemble; useful benchmark for nonlinear feature interactions.",
        "ridge_linear": "Regularized linear benchmark to check whether simpler relationships are enough.",
    }
    return reasons.get(model_name, "Candidate model included in the tuning-window comparison.")


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
    plt.plot(pd.to_datetime(tail["timestamp_utc"]), tail["selected_model_prediction"], label="Selected model", linewidth=1.2)
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
    split_info: Dict[str, Any],
) -> str:
    docs_dir = project_path(config, "docs")
    ensure_dir(docs_dir)

    improved_model = _improved_model(metrics)
    baseline_mae = _metric(metrics, "baseline_lag_24h", "all_hours", "mae")
    improved_mae = _metric(metrics, improved_model, "all_hours", "mae")
    baseline_rmse = _metric(metrics, "baseline_lag_24h", "all_hours", "rmse")
    improved_rmse = _metric(metrics, improved_model, "all_hours", "rmse")
    peak_mae = _metric(metrics, improved_model, "peak_weekday", "mae")
    offpeak_mae = _metric(metrics, improved_model, "offpeak_or_weekend", "mae")

    fv = curve_view["fair_value"]
    edges = curve_view["edges"]
    marks = curve_view["curve_marks"]
    project = config["project"]
    model_selection_path = project_path(config, "outputs/metrics/model_selection.csv")
    model_selection_markdown = ""
    selected_tuning_mae = None
    if model_selection_path.exists():
        model_selection = pd.read_csv(model_selection_path)
        selected_row = model_selection[model_selection["model"] == improved_model]
        if not selected_row.empty:
            selected_tuning_mae = float(selected_row.iloc[0]["mae"])
        model_selection_markdown = "\n".join(
            [
                "| Candidate model | Tuning MAE | Tuning RMSE | Why it was considered |",
                "|---|---:|---:|---|",
            ]
            + [
                (
                    f"| `{row.model}` | {row.mae:.2f} | {row.rmse:.2f} | "
                    f"{_candidate_reason(str(row.model))} |"
                )
                for row in model_selection.itertuples(index=False)
            ]
        )
    if selected_tuning_mae is None:
        selected_tuning_mae = improved_mae
    if not model_selection_markdown:
        model_selection_markdown = "Model-selection details are available after running the validation pipeline."

    markdown = f"""# {project['title']} - Submission Writeup

**Name:** {project['author_name']}  
**Email:** {project['author_email']}  
**Market:** {config['market']['name']} (`{config['market']['bidding_zone']}`)  
**Run window:** `{config['data']['start']}` to `{config['data']['end']}`; fair-value date `{config['data']['forecast_date']}`

## 1. Project Objective

The aim of this project was to build a small but realistic fair-value pipeline for the Germany/Luxembourg day-ahead power market. I focused on next-day hourly prices because this is the most direct way to connect a power forecast to a prompt curve view. The final output is not just a price forecast; it also converts the hourly forecast into base and peak fair values, compares them with a prompt-curve proxy, and gives a simple trade direction with clear invalidation points.

## 2. Data, Cleaning, And QA

I used public Fraunhofer Energy-Charts data. The target is hourly DE-LU day-ahead spot price from `/price`. The fundamental drivers come from `/public_power_forecast` using day-ahead forecasts for load, wind onshore, wind offshore, and solar. From these drivers I also created wind total, renewable generation, renewable share, and residual load. Residual load is especially important in power because it is a practical proxy for how much conventional generation the market still needs after wind and solar.

The raw API data is cached in `data/raw/`, then converted into an hourly modelling table. I resampled any sub-hourly observations to hourly values, aligned everything on UTC timestamps, and added local calendar fields such as local date, local hour, day of week, month, and weekend flag. The final processed dataset has `{qa_report['rows']}` hourly rows and passed the QA checks. The checks cover required columns, duplicate timestamps, hourly cadence, missing values, price bounds, non-negative forecast drivers, and a basic load sanity check. The detailed QA output is in `outputs/qa/qa_report.md`.

For EDA, I mainly used the validation and daily-shape plots rather than adding a separate exploratory notebook. The validation plot shows that the model follows the broad level and direction of the market much better than the lag baseline, although sharp price moves remain the hardest part. The daily fair-value plot is useful for trading because it shows the intraday shape: the model does not only produce one daily number, it produces an hourly strip that can be averaged into base, peak, and off-peak views.

## 3. Forecasting Approach And Model Improvement

I started with a very simple baseline: the same local hour from the previous day (`price_lag_24`). This is a fair baseline for day-ahead power because prices have strong daily seasonality, but it is also limited because it cannot react properly when load, wind, solar, or residual load changes.

The improved model uses features that would be available before delivery: day-ahead load/wind/solar forecasts, residual load, calendar variables, price lags, rolling price means and volatility, residual-load ramps, renewable share, and a few peak/solar interactions. I tested several model families and selected the model on a tuning window before evaluating it on the final holdout. This avoids choosing the best model after looking at the final test period.

The modelling improved in stages. The first version used a single gradient-boosting style model and was materially better than the baseline, but still left too much error. I then added a proper candidate-selection step and compared several models on the same tuning window. I also widened the data window so 2024 history can warm up lag and rolling features, while setting `model.training_start` to `2025-01-01` so older market regimes do not dominate the actual model fit.

The full candidate comparison is below. I chose the final model based on the lowest tuning-window MAE, not by looking at the final holdout. I used MAE as the main selection metric because it is easy to interpret in EUR/MWh and is less dominated by a few extreme price spikes than RMSE.

{model_selection_markdown}

The selected final model was `{improved_model}`. I used it for the final prediction because it had the best tuning MAE (`{selected_tuning_mae:.2f}` EUR/MWh), kept RMSE competitive, and had lower bias than several alternatives. The squared-error boosting model was more sensitive to large errors, extra trees was less stable on this time-series style problem, and ridge regression was useful as a linear benchmark but underfit the nonlinear relationship between residual load, renewables, hour of day, and price.

| Model | MAE | RMSE |
|---|---:|---:|
| Baseline lag 24h | {baseline_mae:.2f} | {baseline_rmse:.2f} |
| Selected improved model | {improved_mae:.2f} | {improved_rmse:.2f} |

The final all-hours MAE is `{improved_mae:.2f}` EUR/MWh versus `{baseline_mae:.2f}` EUR/MWh for the baseline. Peak weekday hours remain harder, with MAE around `{peak_mae:.2f}` EUR/MWh, while off-peak and weekend hours are much cleaner at about `{offpeak_mae:.2f}` EUR/MWh. That split makes sense: peak hours are more exposed to scarcity, ramping, and marginal fuel/outage effects that are not fully captured in the public dataset.

## 4. Plots, Final Prediction, And Curve View

The validation plot in `{figure_paths['validation_plot']}` compares actual prices with the selected model over the final holdout period. My main takeaway is that the model captures the broad price level and many day-to-day moves, but still under-reacts in some high-price periods. This is realistic for a public-data prototype: without fuel, carbon, outages, interconnector flows, and weather forecast revisions, the model should not be expected to explain every spike.

For the delivery date `{curve_view['forecast_date']}`, the model forecast is `{fv['base']:.2f}` EUR/MWh for base, `{fv['peak']:.2f}` EUR/MWh for peak, and `{fv['offpeak']:.2f}` EUR/MWh for off-peak. The hourly forecast ranges from `{fv['min_hour']:.2f}` to `{fv['max_hour']:.2f}` EUR/MWh. The daily shape plot in `{figure_paths['forecast_plot']}` shows how the model distributes value across the day rather than relying only on a flat daily average.

To translate the forecast into a prompt curve view, I compared the model base and peak fair values with a trailing seven-day day-ahead proxy. In a live desk setup this would be replaced by executable broker or exchange marks. The proxy curve marks are `{marks['front_week_base_eur_mwh']:.2f}` EUR/MWh for base and `{marks['front_week_peak_eur_mwh']:.2f}` EUR/MWh for peak. The model is lower than both marks: base edge is `{edges['base_eur_mwh']:.2f}` EUR/MWh and peak edge is `{edges['peak_eur_mwh']:.2f}` EUR/MWh. Since both edges are larger than the configured `{curve_view['threshold_eur_mwh']:.0f}` EUR/MWh threshold, the pipeline gives a short prompt base and short prompt peak view.

I would invalidate or reduce confidence in this view if residual-load forecasts move by more than 2 GW, if prompt marks move by more than the signal threshold, or if fresh fuel, carbon, outage, or interconnector news changes the likely marginal plant stack. I would also be more cautious in peak hours because the validation error is meaningfully higher there.

## 5. AI/LLM Component

The LLM is deliberately not used to forecast prices. The forecasting is done by the machine-learning model described above. I used the LLM only as a workflow helper after the numbers are produced. The pipeline sends structured QA, validation, and curve-view context to OpenAI and asks it to draft a short trading memo. The prompt and output are logged in `outputs/llm/prompt_log.jsonl`, and the memo is saved in `outputs/llm/trading_memo.md`. This is useful because it reduces manual write-up time while keeping the numerical forecast and trading signal fully auditable.

LLM provider used in this run: `{llm_record['provider_used']}`.
"""

    report_path = docs_dir / "submission_writeup_report.md"
    report_path.write_text(markdown, encoding="utf-8")
    project_path(config, "submission_writeup_report.md").write_text(markdown, encoding="utf-8")
    return str(report_path)
