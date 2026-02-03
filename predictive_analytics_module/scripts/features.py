from __future__ import annotations
import numpy as np
import pandas as pd

def add_lag_roll_features(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    lags = cfg["features"]["lags"]
    windows = cfg["features"]["rolling_windows"]

    panel = panel.sort_values(["facility", "lane", "week_start"]).copy()

    base_cols = ["delay_prob", "delay_mean", "delay_p90", "shipments"]
    g = panel.groupby(["facility", "lane"], group_keys=False)

    for col in base_cols:
        for k in lags:
            panel[f"{col}_lag{k}"] = g[col].shift(k)

        for w in windows:
            # rolling mean of prior values only (shift(1) then roll)
            panel[f"{col}_rollmean{w}"] = g[col].shift(1).rolling(w).mean()

    # Seasonality features
    panel["sin_woy"] = np.sin(2 * np.pi * panel["weekofyear"] / 52.0)
    panel["cos_woy"] = np.cos(2 * np.pi * panel["weekofyear"] / 52.0)

    # Drop rows without required history
    min_hist = cfg["features"]["min_history_weeks"]
    # rough requirement: need lag(min_hist) available for delay_prob
    # panel["_hist_ok"] = g["delay_prob"].transform(lambda s: s.cumcount() >= (min_hist - 1))
    panel["_hist_ok"] = g.cumcount() >= (min_hist - 1)
    panel = panel.loc[panel["_hist_ok"]].drop(columns=["_hist_ok"])

    return panel

def make_targets(panel: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    thr = float(cfg["targets"]["cls_delay_prob_threshold"])
    panel = panel.copy()
    panel["y_cls"] = (panel["delay_prob"] >= thr).astype(int)
    panel["y_reg"] = panel[cfg["targets"]["reg_target"]].astype(float)
    return panel
