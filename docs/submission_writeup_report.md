# DE-LU Power Fair Value - Submission Writeup

**Name:** Akil Surya  
**Email:** akilsurya20399@gmail.com  
**Market:** Germany/Luxembourg day-ahead power (`DE-LU`)  
**Run window:** `2024-01-01` to `2025-12-31`; fair-value date `2025-12-31`

## 1. Project Objective

The aim of this project was to build a small but realistic fair-value pipeline for the Germany/Luxembourg day-ahead power market. I focused on next-day hourly prices because this is the most direct way to connect a power forecast to a prompt curve view. The final output is not just a price forecast; it also converts the hourly forecast into base and peak fair values, compares them with a prompt-curve proxy, and gives a simple trade direction with clear invalidation points.

## 2. Data, Cleaning, And QA

I used public Fraunhofer Energy-Charts data. The target is hourly DE-LU day-ahead spot price from `/price`. The fundamental drivers come from `/public_power_forecast` using day-ahead forecasts for load, wind onshore, wind offshore, and solar. From these drivers I also created wind total, renewable generation, renewable share, and residual load. Residual load is especially important in power because it is a practical proxy for how much conventional generation the market still needs after wind and solar.

The raw API data is cached in `data/raw/`, then converted into an hourly modelling table. I resampled any sub-hourly observations to hourly values, aligned everything on UTC timestamps, and added local calendar fields such as local date, local hour, day of week, month, and weekend flag. The final processed dataset has `17544` hourly rows and passed the QA checks. The checks cover required columns, duplicate timestamps, hourly cadence, missing values, price bounds, non-negative forecast drivers, and a basic load sanity check. The detailed QA output is in `outputs/qa/qa_report.md`.

For EDA, I mainly used the validation and daily-shape plots rather than adding a separate exploratory notebook. The validation plot shows that the model follows the broad level and direction of the market much better than the lag baseline, although sharp price moves remain the hardest part. The daily fair-value plot is useful for trading because it shows the intraday shape: the model does not only produce one daily number, it produces an hourly strip that can be averaged into base, peak, and off-peak views.

## 3. Forecasting Approach And Model Improvement

I started with a very simple baseline: the same local hour from the previous day (`price_lag_24`). This is a fair baseline for day-ahead power because prices have strong daily seasonality, but it is also limited because it cannot react properly when load, wind, solar, or residual load changes.

The improved model uses features that would be available before delivery: day-ahead load/wind/solar forecasts, residual load, calendar variables, price lags, rolling price means and volatility, residual-load ramps, renewable share, and a few peak/solar interactions. I tested several model families and selected the model on a tuning window before evaluating it on the final holdout. This avoids choosing the best model after looking at the final test period.

The modelling improved in stages. The first version used a single gradient-boosting style model and was materially better than the baseline, but still left too much error. I then added a proper candidate-selection step and compared several models on the same tuning window. I also widened the data window so 2024 history can warm up lag and rolling features, while setting `model.training_start` to `2025-01-01` so older market regimes do not dominate the actual model fit.

The full candidate comparison is below. I chose the final model based on the lowest tuning-window MAE, not by looking at the final holdout. I used MAE as the main selection metric because it is easy to interpret in EUR/MWh and is less dominated by a few extreme price spikes than RMSE.

| Candidate model | Tuning MAE | Tuning RMSE | Why it was considered |
|---|---:|---:|---|
| `hist_gradient_boosting_absolute_error` | 11.22 | 16.32 | Tree boosting with MAE-style loss; robust to spikes and nonlinear fundamentals. |
| `gradient_boosting_huber` | 11.94 | 16.89 | Boosting with Huber loss; tested as a robust alternative for volatile prices. |
| `hist_gradient_boosting_squared_error` | 12.85 | 19.28 | Tree boosting with squared-error loss; captures nonlinear effects but can chase spikes. |
| `extra_trees` | 14.19 | 20.69 | Randomized tree ensemble; useful benchmark for nonlinear feature interactions. |
| `ridge_linear` | 16.00 | 20.12 | Regularized linear benchmark to check whether simpler relationships are enough. |

The selected final model was `hist_gradient_boosting_absolute_error`. I used it for the final prediction because it had the best tuning MAE (`11.22` EUR/MWh), kept RMSE competitive, and had lower bias than several alternatives. The squared-error boosting model was more sensitive to large errors, extra trees was less stable on this time-series style problem, and ridge regression was useful as a linear benchmark but underfit the nonlinear relationship between residual load, renewables, hour of day, and price.

| Model | MAE | RMSE |
|---|---:|---:|
| Baseline lag 24h | 24.34 | 39.64 |
| Selected improved model | 11.15 | 17.31 |

The final all-hours MAE is `11.15` EUR/MWh versus `24.34` EUR/MWh for the baseline. Peak weekday hours remain harder, with MAE around `17.62` EUR/MWh, while off-peak and weekend hours are much cleaner at about `7.40` EUR/MWh. That split makes sense: peak hours are more exposed to scarcity, ramping, and marginal fuel/outage effects that are not fully captured in the public dataset.

## 4. Plots, Final Prediction, And Curve View

The validation plot in `outputs/figures/validation_actual_vs_pred.png` compares actual prices with the selected model over the final holdout period. My main takeaway is that the model captures the broad price level and many day-to-day moves, but still under-reacts in some high-price periods. This is realistic for a public-data prototype: without fuel, carbon, outages, interconnector flows, and weather forecast revisions, the model should not be expected to explain every spike.

For the delivery date `2025-12-31`, the model forecast is `78.93` EUR/MWh for base, `82.11` EUR/MWh for peak, and `75.75` EUR/MWh for off-peak. The hourly forecast ranges from `61.79` to `89.76` EUR/MWh. The daily shape plot in `outputs/figures/daily_fair_value_shape.png` shows how the model distributes value across the day rather than relying only on a flat daily average.

To translate the forecast into a prompt curve view, I compared the model base and peak fair values with a trailing seven-day day-ahead proxy. In a live desk setup this would be replaced by executable broker or exchange marks. The proxy curve marks are `86.14` EUR/MWh for base and `88.86` EUR/MWh for peak. The model is lower than both marks: base edge is `-7.21` EUR/MWh and peak edge is `-6.74` EUR/MWh. Since both edges are larger than the configured `5` EUR/MWh threshold, the pipeline gives a short prompt base and short prompt peak view.

I would invalidate or reduce confidence in this view if residual-load forecasts move by more than 2 GW, if prompt marks move by more than the signal threshold, or if fresh fuel, carbon, outage, or interconnector news changes the likely marginal plant stack. I would also be more cautious in peak hours because the validation error is meaningfully higher there.

## 5. AI/LLM Component

The LLM is deliberately not used to forecast prices. The forecasting is done by the machine-learning model described above. I used the LLM only as a workflow helper after the numbers are produced. The pipeline sends structured QA, validation, and curve-view context to OpenAI and asks it to draft a short trading memo. The prompt and output are logged in `outputs/llm/prompt_log.jsonl`, and the memo is saved in `outputs/llm/trading_memo.md`. This is useful because it reduces manual write-up time while keeping the numerical forecast and trading signal fully auditable.

LLM provider used in this run: `openai`.
