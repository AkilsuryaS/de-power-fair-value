import pandas as pd

from power_fair_value.curve import summarize_strip, translate_to_curve_view


def _config():
    return {
        "data": {"forecast_date": "2025-01-10"},
        "curve": {
            "threshold_eur_mwh": 5,
            "peak_start_hour": 8,
            "peak_end_hour": 20,
            "front_week_base_eur_mwh": 60,
            "front_week_peak_eur_mwh": 70,
        },
    }


def test_curve_translation_uses_config_marks():
    hours = pd.date_range("2025-01-10", periods=24, freq="h", tz="Europe/Berlin")
    forecast = pd.DataFrame(
        {
            "timestamp_local": hours,
            "date_local": "2025-01-10",
            "hour_local": hours.hour,
            "is_weekend": 0,
            "y_pred": 80.0,
            "da_price_eur_mwh": 75.0,
        }
    )
    hist = forecast.copy()

    view = translate_to_curve_view(forecast, hist, _config())
    assert view["edges"]["base_eur_mwh"] == 20
    assert view["positioning"]["base"].startswith("Long prompt base")


def test_summarize_strip_returns_base_peak_offpeak():
    hours = pd.date_range("2025-01-08", periods=24, freq="h", tz="Europe/Berlin")
    df = pd.DataFrame(
        {
            "hour_local": hours.hour,
            "is_weekend": 0,
            "value": 10.0,
        }
    )
    summary = summarize_strip(df, "value", _config())
    assert summary["base"] == 10
    assert summary["peak"] == 10
    assert summary["offpeak"] == 10
