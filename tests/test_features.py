import pandas as pd

from power_fair_value.features import build_features, model_features


def test_build_features_adds_lags_and_calendar_terms():
    ts = pd.date_range("2025-01-01", periods=200, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp_utc": ts,
            "timestamp_local": ts.tz_convert("Europe/Berlin"),
            "date_local": ts.tz_convert("Europe/Berlin").strftime("%Y-%m-%d"),
            "hour_local": ts.tz_convert("Europe/Berlin").hour,
            "day_of_week": ts.tz_convert("Europe/Berlin").dayofweek,
            "month": ts.tz_convert("Europe/Berlin").month,
            "is_weekend": 0,
            "da_price_eur_mwh": range(200),
            "load_da_forecast_mw": 50000,
            "wind_onshore_da_forecast_mw": 10000,
            "wind_offshore_da_forecast_mw": 3000,
            "solar_da_forecast_mw": 1000,
            "wind_total_da_forecast_mw": 13000,
            "renewables_da_forecast_mw": 14000,
            "residual_load_da_forecast_mw": 36000,
        }
    )

    out = build_features(df)
    assert out.loc[24, "price_lag_24"] == 0
    assert out.loc[168, "price_lag_168"] == 0
    assert set(model_features()).issubset(out.columns)
