"""
FedEx Adapter Module
--------------------

Builds the Canonical Bronze KPI dataset from:

1. Weekly KPI dataset
2. August Actuals with DOM dataset
3. Optional XLSB operational extract

Applies:
- Column standardization
- Lane harmonization
- Aug Lane_ recovery rule
- Weight normalization
- Schema alignment
"""

import pandas as pd
from typing import Optional


# =====================================================
# Utility Functions
# =====================================================

def _standardize_lane(row):
    """
    Harmonize lane values to canonical Dest_Lane.
    """
    lane_map = {
        "EU": "Europe",
        "Europe": "Europe",
        "AS": "APAC",
        "APAC": "APAC",
        "ME": "MEISA",
        "MEISA": "MEISA",
        "NA": "Americas",
        "LA": "Americas",
        "Americas": "Americas"
    }

    if pd.notna(row):
        return lane_map.get(str(row).strip(), str(row).strip())
    return row


def _apply_aug_lane_recovery(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply business rule:
    IF Lane_ is NULL AND Lane == 'Americas'
    THEN Lane_ = 'LA'
    """
    mask = df["Lane_"].isna() & (df["Lane"] == "Americas")
    df.loc[mask, "Lane_"] = "LA"
    return df


def _standardize_weights(df: pd.DataFrame, weight_col: str) -> pd.Series:
    """
    Convert weight column to numeric aPounds.
    """
    weights = pd.to_numeric(df[weight_col], errors="coerce")
    return weights


# =====================================================
# Loaders
# =====================================================

def load_weekly(path: str) -> pd.DataFrame:
    """
    Load Weekly KPI dataset and standardize schema.
    """
    df = pd.read_excel(path)

    df = df.rename(columns={
        "Dest_Lane": "Dest_Lane",
        "Product_Code": "Product_Code",
        "PACKS": "PACKS",
        "Shipments": "Shipments",
        "aPounds": "aPounds"
    })

    df["Dest_Lane"] = df["Dest_Lane"].apply(_standardize_lane)

    df["PACKS"] = pd.to_numeric(df["PACKS"], errors="coerce").fillna(0)
    df["Shipments"] = pd.to_numeric(df["Shipments"], errors="coerce").fillna(0)
    df["aPounds"] = _standardize_weights(df, "aPounds").fillna(0)

    return df


def load_aug(path: str) -> pd.DataFrame:
    """
    Load August Actuals dataset and transform to Bronze schema.
    """
    df = pd.read_excel(path)

    # Apply Lane_ recovery rule
    df = _apply_aug_lane_recovery(df)

    # Harmonize lanes
    df["Dest_Lane"] = df["Lane"].apply(_standardize_lane)

    # Standardize measures
    df["PACKS"] = pd.to_numeric(df["Packs"], errors="coerce").fillna(0)
    df["Shipments"] = pd.to_numeric(df["Shipments"], errors="coerce").fillna(0)
    df["aPounds"] = _standardize_weights(df, "aLbs").fillna(0)

    # Align columns
    df = df.rename(columns={
        "Product": "Product_Code"
    })

    # Keep only canonical columns
    bronze_cols = [
        "FY",
        "WeekNbr",
        "Orig_Ctry",
        "ORIG_RAMP",
        "Business_Region",
        "Dest_Lane",
        "Product_Code",
        "PACKS",
        "Shipments",
        "aPounds"
    ]

    return df[bronze_cols]


def load_xlsb(path: str) -> pd.DataFrame:
    """
    Load XLSB extract (if usable).
    """
    try:
        df = pd.read_excel(path, engine="pyxlsb")
        return df
    except Exception:
        return pd.DataFrame()


# =====================================================
# Bronze Builder
# =====================================================

def build_bronze(
    weekly_path: str,
    aug_path: str,
    xlsb_path: Optional[str] = None
) -> pd.DataFrame:
    """
    Build Canonical Bronze KPI dataset from all sources.
    """

    weekly_df = load_weekly(weekly_path)
    aug_df = load_aug(aug_path)

    frames = [weekly_df, aug_df]

    if xlsb_path:
        xlsb_df = load_xlsb(xlsb_path)
        if not xlsb_df.empty:
            frames.append(xlsb_df)

    bronze = pd.concat(frames, ignore_index=True)

    # Fill missing numeric values
    bronze["PACKS"] = bronze["PACKS"].fillna(0)
    bronze["Shipments"] = bronze["Shipments"].fillna(0)
    bronze["aPounds"] = bronze["aPounds"].fillna(0)

    # Enforce canonical column order
    bronze = bronze[
        [
            "FY",
            "WeekNbr",
            "Orig_Ctry",
            "ORIG_RAMP",
            "Business_Region",
            "Dest_Lane",
            "Product_Code",
            "PACKS",
            "Shipments",
            "aPounds",
        ]
    ]

    return bronze