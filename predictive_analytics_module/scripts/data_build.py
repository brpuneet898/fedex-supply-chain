from __future__ import annotations
import numpy as np
import pandas as pd

def _week_start_sun(dt: pd.Series) -> pd.Series:
    # Week periods ending Sunday; we use start_time as the "week start" key
    return dt.dt.to_period("W-SUN").apply(lambda p: p.start_time.normalize())

def build_panel(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    p = cfg["panel"]

    ship_dt = pd.to_datetime(df[p["ship_date_col"]], errors="coerce")
    df = df.loc[ship_dt.notna()].copy()
    df["shipping_dt"] = ship_dt

    days_real = pd.to_numeric(df[p["days_real_col"]], errors="coerce")
    days_sched = pd.to_numeric(df[p["days_sched_col"]], errors="coerce")
    df = df.loc[days_real.notna() & days_sched.notna()].copy()

    df["delay_days"] = (days_real - days_sched).clip(lower=0)
    df["delay_flag"] = (days_real > days_sched).astype(int)

    df["facility"] = df[p["facility_col"]].fillna("UNK").astype(str)
    origin = df[p["origin_col"]].fillna("UNK").astype(str)
    dest = df[p["dest_col"]].fillna("UNK").astype(str)
    df["lane"] = origin + "->" + dest

    df["week_start"] = _week_start_sun(df["shipping_dt"])
    df["month"] = df["shipping_dt"].dt.month.astype(int)
    df["weekofyear"] = df["shipping_dt"].dt.isocalendar().week.astype(int)

    # Aggregate shipping mode proportions and market mode (most common)
    ship_mode = df[p["shipping_mode_col"]].fillna("UNK").astype(str)
    market = df[p["market_col"]].fillna("UNK").astype(str)

    # core agg
    grp = df.groupby(["facility", "lane", "week_start"], as_index=False)
    panel = grp.agg(
        shipments=("delay_flag", "size"),
        delay_prob=("delay_flag", "mean"),
        delay_mean=("delay_days", "mean"),
        delay_p90=("delay_days", lambda x: float(np.quantile(x, 0.90))),
        month=("month", "max"),
        weekofyear=("weekofyear", "max"),
    )

    # market (mode)
    mkt_mode = (
        df.assign(market=market)
          .groupby(["facility", "lane", "week_start"])["market"]
          .agg(lambda s: s.value_counts().index[0])
          .reset_index()
    )
    panel = panel.merge(mkt_mode, on=["facility", "lane", "week_start"], how="left")

    # shipping mode proportions
    ship_counts = (
        df.assign(shipping_mode=ship_mode)
          .groupby(["facility", "lane", "week_start", "shipping_mode"])
          .size()
          .rename("cnt")
          .reset_index()
    )
    ship_piv = ship_counts.pivot_table(
        index=["facility", "lane", "week_start"],
        columns="shipping_mode",
        values="cnt",
        fill_value=0,
        aggfunc="sum",
    )
    ship_piv = ship_piv.div(ship_piv.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    ship_piv.columns = [f"shipmode_prop__{c}" for c in ship_piv.columns]
    ship_piv = ship_piv.reset_index()

    panel = panel.merge(ship_piv, on=["facility", "lane", "week_start"], how="left")

    panel = panel.sort_values(["facility", "lane", "week_start"]).reset_index(drop=True)
    return panel
