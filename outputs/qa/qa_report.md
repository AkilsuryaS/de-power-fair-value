# QA Report: Germany/Luxembourg day-ahead power

- Bidding zone: `DE-LU`
- Date range: `2025-07-01` to `2025-12-31`
- Rows: `4417`
- Status: `PASSED`

| Check | Severity | Status | Detail |
|---|---:|---:|---|
| required_columns | critical | PASS | All required columns present. |
| row_count | critical | PASS | Rows: 4417. Expected at least 4232 for configured date range. |
| duplicate_timestamps | critical | PASS | Duplicate UTC timestamps: 0. |
| hourly_cadence | critical | PASS | Non-hourly UTC intervals: 0. |
| missing_values | critical | PASS | Missing values by required column: {'timestamp_utc': 0, 'da_price_eur_mwh': 0, 'load_da_forecast_mw': 0, 'wind_onshore_da_forecast_mw': 0, 'wind_offshore_da_forecast_mw': 0, 'solar_da_forecast_mw': 0}. |
| price_bounds | critical | PASS | All prices within [-500, 1000] EUR/MWh. |
| driver_non_negative | critical | PASS | Negative driver counts: {'load_da_forecast_mw': 0, 'wind_onshore_da_forecast_mw': 0, 'wind_offshore_da_forecast_mw': 0, 'solar_da_forecast_mw': 0}. |
| load_floor | warning | PASS | Hours with load forecast below 10 GW: 0. |
