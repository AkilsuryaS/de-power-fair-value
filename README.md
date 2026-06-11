# DE-LU Power Fair Value

Prototype pipeline for forecasting Germany/Luxembourg hourly day-ahead power fair value and translating the forecast into a prompt-curve view.

## What It Builds

- Hourly dataset with DE-LU day-ahead prices and day-ahead forecast drivers for load, wind onshore, wind offshore, and solar.
- QA output covering schema, missing values, hourly cadence, duplicates, and sanity bounds.
- Baseline model: same-hour previous-day price.
- Improved model: selected on an earlier tuning window from histogram gradient boosting, extra trees, Huber gradient boosting, and a regularized linear benchmark.
- Daily fair-value strip, validation metrics, figures, `submission.csv`, and a concise trading report.
- AI-assisted trading memo generator with logged prompts/outputs.

## Data Sources

The pipeline uses the public [Fraunhofer Energy-Charts API](https://api.energy-charts.info/):

- `/price`: day-ahead spot market price for bidding zone `DE-LU`.
- `/public_power_forecast`: day-ahead forecasts for `load`, `wind_onshore`, `wind_offshore`, and `solar`.

Energy-Charts reports the DE-LU price license as CC BY 4.0 from Bundesnetzagentur / SMARD.de. The source metadata used by a run is written to `outputs/qa/source_metadata.json`.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python scripts/run_pipeline.py --config configs/default.yml
python -m pytest
```

If `OPENAI_API_KEY` is available in the environment or a parent `.env`, the memo step calls OpenAI and logs the request/response in `outputs/llm/prompt_log.jsonl`. Without a key, the pipeline writes a deterministic fallback memo so the run remains reproducible.

## Modeling Approach

The validation design avoids choosing a model on the final holdout window:

- Baseline: same-hour previous-day price (`lag_24h`).
- Data window: starts in 2024 so lag and rolling features have enough warm-up history.
- Training window: starts at `model.training_start` (`2025-01-01` by default) so older regimes inform history features without dominating model fitting.
- Candidate selection: train candidates on earlier history and choose the lowest-MAE model on a later tuning window.
- Final validation: retrain the selected model on all data before the holdout, then evaluate once on the untouched holdout.

The selected model in the latest run is `hist_gradient_boosting_absolute_error`. It uses day-ahead fundamentals, calendar variables, price lags, rolling means/volatility, residual-load ramps, renewable share, and simple peak/solar interactions.

## Main Outputs

- `data/processed/de_lu_hourly_dataset.csv`
- `data/processed/model_features.csv`
- `data/processed/submission.csv`
- `outputs/qa/qa_report.md`
- `outputs/metrics/validation_metrics.csv`
- `outputs/metrics/model_selection.csv`
- `outputs/predictions/daily_fair_value.csv`
- `outputs/predictions/curve_view.json`
- `outputs/llm/prompt_log.jsonl`
- `docs/submission_writeup_report.md`

## Evaluation Checklist

| Evaluation area | How this repo addresses it | Key artifacts |
|---|---|---|
| Dataset correctness and QA | Public DE-LU hourly day-ahead prices are merged with day-ahead load, wind, and solar forecast drivers; QA checks schema, cadence, duplicates, missing values, bounds, and driver sanity. | [dataset](data/processed/de_lu_hourly_dataset.csv), [QA report](outputs/qa/qa_report.md), [source metadata](outputs/qa/source_metadata.json) |
| Forecasting rigor | Includes a lag-24h baseline, multiple candidate improved models, tuning-window model selection, and untouched holdout validation with MAE/RMSE/bias/R2. | [model code](src/power_fair_value/models.py), [validation metrics](outputs/metrics/validation_metrics.csv), [model selection](outputs/metrics/model_selection.csv), [validation split](outputs/metrics/validation_split.json) |
| Trading relevance | Converts hourly fair value into base/peak prompt-curve views, edge versus curve marks, directional guidance, and invalidation triggers. | [curve code](src/power_fair_value/curve.py), [curve view output](outputs/predictions/curve_view.json), [submission writeup report](docs/submission_writeup_report.md) |
| Engineering quality and reproducibility | Provides a clean package layout, config-driven run, one-command pipeline, tests, cached raw data, and regenerated outputs. | [README](README.md), [config](configs/default.yml), [pipeline script](scripts/run_pipeline.py), [project dependencies](pyproject.toml), [tests](tests/) |
| Programmatic AI/LLM use | Uses an OpenAI-powered memo step to draft a desk-facing trading note from structured QA, validation, and curve-view outputs; prompts and responses are logged. | [LLM code](src/power_fair_value/llm.py), [trading memo](outputs/llm/trading_memo.md), [prompt log](outputs/llm/prompt_log.jsonl) |

## Prompt-Curve Translation

The default config compares the model's fair-value delivery-day base and peak strips with a trailing seven-day day-ahead proxy when explicit broker or exchange prompt-week marks are not supplied. For a more realistic desk workflow, set `curve.front_week_base_eur_mwh` and `curve.front_week_peak_eur_mwh` in `configs/default.yml`.

Decision rule:

- Fair value above curve mark by more than `threshold_eur_mwh`: long prompt base/peak.
- Fair value below curve mark by more than `threshold_eur_mwh`: short prompt base/peak.
- Otherwise neutral.

The report also lists invalidation triggers for residual-load forecast revisions, curve movement, model-error widening, and fuel/carbon/outage/interconnector news.
