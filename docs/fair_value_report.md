# DE-LU Power Fair Value

**Name:** Akil Surya  
**Email:** akilsurya20399@gmail.com  
**Market:** Germany/Luxembourg day-ahead power (`DE-LU`)  
**Run window:** `2025-07-01` to `2025-12-31`; fair-value date `2025-12-31`

## Data And QA

The dataset is hourly DE-LU day-ahead price with day-ahead forecast drivers for load, wind onshore, wind offshore, and solar. Sources are the public Fraunhofer Energy-Charts API: `/price` for day-ahead spot prices and `/public_power_forecast` for fundamental forecasts. Price data for DE-LU is licensed CC BY 4.0 from Bundesnetzagentur/SMARD.de as reported by the API.

QA status: **PASSED** across `4417` hourly rows. Checks cover required columns, duplicate timestamps, hourly UTC cadence, missing values, price bounds, and non-negative driver forecasts. Full QA output is in `outputs/qa/qa_report.md`.

## Forecasting

Baseline model: same-hour previous-day price (`lag_24h`). Improved model: histogram gradient boosting with calendar variables, lagged prices, rolling price means, and day-ahead load/wind/solar/residual-load forecasts. The final daily fair value is trained only on data before the fair-value date.

| Model | MAE | RMSE |
|---|---:|---:|
| Baseline lag 24h | 24.34 | 39.64 |
| Improved gradient boosting | 13.57 | 23.98 |

Validation plot: `outputs/figures/validation_actual_vs_pred.png`  
Daily shape plot: `outputs/figures/daily_fair_value_shape.png`

## DA-To-Curve View

For `2025-12-31`, model fair value is **79.42 EUR/MWh base** and **82.97 EUR/MWh peak**. Curve marks use `trailing_7d_day_ahead_proxy`: base `86.14`, peak `88.86` EUR/MWh.

Base edge: **-6.72 EUR/MWh**. Short prompt base: model fair value is 6.72 EUR/MWh below the curve mark.  
Peak edge: **-5.88 EUR/MWh**. Short prompt peak: model fair value is 5.88 EUR/MWh below the curve mark.

Use: compare the forecast strip with executable prompt-week/base and peak marks to decide whether the prompt curve is cheap or rich versus expected cash settlement. Invalidate the view if residual-load forecasts revise by more than 2 GW, curve marks move by more than the edge threshold, or new fuel/carbon/outage/interconnector information changes marginal pricing before execution.

## AI/LLM Component

The pipeline includes `power_fair_value.llm.generate_trading_memo`, which sends QA, validation, and curve-view context to OpenAI when `OPENAI_API_KEY` is available. Prompts and outputs are logged in `outputs/llm/prompt_log.jsonl`; when no key is available, a deterministic offline memo is written so the pipeline remains reproducible. This reduces manual effort by drafting the desk-facing trading note from structured model outputs.

LLM provider used in this run: `openai`.
