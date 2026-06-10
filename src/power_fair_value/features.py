from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd


FEATURE_COLUMNS: List[str] = [
    "hour_local",
    "day_of_week",
    "month",
    "is_weekend",
    "load_da_forecast_mw",
    "wind_onshore_da_forecast_mw",
    "wind_offshore_da_forecast_mw",
    "solar_da_forecast_mw",
    "wind_total_da_forecast_mw",
    "renewables_da_forecast_mw",
    "residual_load_da_forecast_mw",
    "price_lag_24",
    "price_lag_48",
    "price_lag_168",
    "price_roll_24_mean",
    "price_roll_168_mean",
    "price_lag_72",
    "price_lag_336",
    "price_roll_24_std",
    "price_roll_168_std",
    "residual_load_lag_24",
    "residual_load_ramp_1h",
    "residual_load_ramp_24h",
    "renewable_share_forecast",
    "solar_x_hour",
    "residual_x_peak",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out.sort_values("timestamp_utc").reset_index(drop=True)
    out["price_lag_24"] = out["da_price_eur_mwh"].shift(24)
    out["price_lag_48"] = out["da_price_eur_mwh"].shift(48)
    out["price_lag_168"] = out["da_price_eur_mwh"].shift(168)
    out["price_lag_72"] = out["da_price_eur_mwh"].shift(72)
    out["price_lag_336"] = out["da_price_eur_mwh"].shift(336)
    out["price_roll_24_mean"] = out["da_price_eur_mwh"].shift(1).rolling(24).mean()
    out["price_roll_168_mean"] = out["da_price_eur_mwh"].shift(1).rolling(168).mean()
    out["price_roll_24_std"] = out["da_price_eur_mwh"].shift(1).rolling(24).std()
    out["price_roll_168_std"] = out["da_price_eur_mwh"].shift(1).rolling(168).std()

    out["hour_sin"] = np.sin(2 * np.pi * out["hour_local"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour_local"] / 24)
    out["dow_sin"] = np.sin(2 * np.pi * out["day_of_week"] / 7)
    out["dow_cos"] = np.cos(2 * np.pi * out["day_of_week"] / 7)
    out["residual_load_lag_24"] = out["residual_load_da_forecast_mw"].shift(24)
    out["residual_load_ramp_1h"] = out["residual_load_da_forecast_mw"].diff()
    out["residual_load_ramp_24h"] = (
        out["residual_load_da_forecast_mw"] - out["residual_load_lag_24"]
    )
    out["renewable_share_forecast"] = (
        out["renewables_da_forecast_mw"] / out["load_da_forecast_mw"]
    )
    out["solar_x_hour"] = out["solar_da_forecast_mw"] * out["hour_sin"]
    peak_flag = (
        (out["hour_local"] >= 8)
        & (out["hour_local"] < 20)
        & (out["is_weekend"] == 0)
    ).astype(int)
    out["residual_x_peak"] = out["residual_load_da_forecast_mw"] * peak_flag

    return out


def model_features() -> List[str]:
    return FEATURE_COLUMNS + ["hour_sin", "hour_cos", "dow_sin", "dow_cos"]
