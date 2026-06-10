# DE-LU Power Fair Value

**Name:** Akil Surya  
**Email:** akilsurya20399@gmail.com  
**Market:** Germany/Luxembourg day-ahead power (`DE-LU`)  
**Run window:** `2025-07-01` to `2025-12-31`; fair-value date `2025-12-31`

## Data And QA

The dataset is hourly DE-LU day-ahead price with day-ahead forecast drivers for load, wind onshore, wind offshore, and solar. Sources are the public Fraunhofer Energy-Charts API: `/price` for day-ahead spot prices and `/public_power_forecast` for fundamental forecasts. Price data for DE-LU is licensed CC BY 4.0 from Bundesnetzagentur/SMARD.de as reported by the API.

QA status: **PASSED** across `4417` hourly rows. Checks cover required columns, duplicate timestamps, hourly UTC cadence, missing values, price bounds, and non-negative driver forecasts. Full QA output is in `outputs/qa/qa_report.md`.

## Forecasting

Baseline model: same-hour previous-day price (`lag_24h`). Improved model: selected from a small, realistic candidate set using an earlier tuning window, then evaluated once on the untouched holdout window. Candidate models include histogram gradient boosting, extra trees, Huber gradient boosting, and a regularized linear benchmark. The selected model is `hist_gradient_boosting_absolute_error`. Features include calendar variables, day-ahead load/wind/solar/residual-load forecasts, price lags, rolling means/volatility, residual-load ramps, and renewable-share interactions.

Model selection uses data before `2025-11-17` only: selection training rows `2280`, tuning rows `721`. Final validation rows `1080` remain untouched until the selected model is evaluated.

| Model | MAE | RMSE |
|---|---:|---:|
| Baseline lag 24h | 24.34 | 39.64 |
| Selected improved model | 12.33 | 21.64 |

Validation plot: `outputs/figures/validation_actual_vs_pred.png`  
Daily shape plot: `outputs/figures/daily_fair_value_shape.png`

## DA-To-Curve View

For `2025-12-31`, model fair value is **79.52 EUR/MWh base** and **85.19 EUR/MWh peak**. Curve marks use `trailing_7d_day_ahead_proxy`: base `86.14`, peak `88.86` EUR/MWh.

Base edge: **-6.62 EUR/MWh**. Short prompt base: model fair value is 6.62 EUR/MWh below the curve mark.  
Peak edge: **-3.67 EUR/MWh**. Neutral prompt peak: edge of -3.67 EUR/MWh is inside the threshold.

Use: compare the forecast strip with executable prompt-week/base and peak marks to decide whether the prompt curve is cheap or rich versus expected cash settlement. Invalidate the view if residual-load forecasts revise by more than 2 GW, curve marks move by more than the edge threshold, or new fuel/carbon/outage/interconnector information changes marginal pricing before execution.

## AI/LLM Component

The pipeline includes `power_fair_value.llm.generate_trading_memo`, which sends QA, validation, and curve-view context to OpenAI when `OPENAI_API_KEY` is available. Prompts and outputs are logged in `outputs/llm/prompt_log.jsonl`; when no key is available, a deterministic offline memo is written so the pipeline remains reproducible. This reduces manual effort by drafting the desk-facing trading note from structured model outputs.

LLM provider used in this run: `openai`.
