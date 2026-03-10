"""
Validation Module
-----------------

Implements deterministic data quality gates for the
Canonical Bronze KPI dataset.

QA Gates:
1. Missingness summary
2. Non-negativity checks
3. Key uniqueness check
4. Plausibility flags
"""

import pandas as pd
from typing import Dict


# =====================================================
# 1. Missingness Summary
# =====================================================

def missingness_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns percentage of missing values per column.
    """

    total_rows = len(df)

    summary = pd.DataFrame({
        "column": df.columns,
        "missing_count": df.isnull().sum().values,
        "missing_percent": (df.isnull().sum().values / total_rows) * 100
    })

    return summary.sort_values("missing_percent", ascending=False)


# =====================================================
# 2. Non-Negativity Checks
# =====================================================

def non_negativity_check(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures no negative values in numeric KPI columns.
    """

    numeric_cols = ["PACKS", "Shipments", "aPounds"]

    results = []

    for col in numeric_cols:
        if col in df.columns:
            negative_count = (df[col] < 0).sum()
            results.append({
                "column": col,
                "negative_values": int(negative_count),
                "status": "FAIL" if negative_count > 0 else "PASS"
            })

    return pd.DataFrame(results)


# =====================================================
# 3. Primary Key Uniqueness Check
# =====================================================

def key_uniqueness_check(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures no duplicate rows at canonical Bronze grain.
    """

    key_cols = [
        "FY",
        "WeekNbr",
        "Orig_Ctry",
        "ORIG_RAMP",
        "Business_Region",
        "Dest_Lane",
        "Product_Code"
    ]

    duplicate_count = df.duplicated(subset=key_cols).sum()

    result = pd.DataFrame([{
        "check": "Primary Key Uniqueness",
        "duplicate_rows": int(duplicate_count),
        "status": "FAIL" if duplicate_count > 0 else "PASS"
    }])

    return result


# =====================================================
# 4. Plausibility Checks
# =====================================================

def plausibility_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flags potentially abnormal KPI values.
    Thresholds are conservative and can be tuned.
    """

    flags = []

    # Extreme weight spike
    weight_threshold = df["aPounds"].quantile(0.999) if "aPounds" in df else None

    if weight_threshold is not None:
        extreme_weight = (df["aPounds"] > weight_threshold).sum()
        flags.append({
            "check": "Extreme Weight Spike (>99.9 percentile)",
            "flagged_rows": int(extreme_weight)
        })

    # Extremely high shipments
    shipment_threshold = df["Shipments"].quantile(0.999) if "Shipments" in df else None

    if shipment_threshold is not None:
        extreme_shipments = (df["Shipments"] > shipment_threshold).sum()
        flags.append({
            "check": "Extreme Shipment Spike (>99.9 percentile)",
            "flagged_rows": int(extreme_shipments)
        })

    # Zero volume rows
    zero_rows = (
        (df["PACKS"] == 0) &
        (df["Shipments"] == 0) &
        (df["aPounds"] == 0)
    ).sum()

    flags.append({
        "check": "All-zero KPI rows",
        "flagged_rows": int(zero_rows)
    })

    return pd.DataFrame(flags)


# =====================================================
# 5. Master QA Runner
# =====================================================

def run_all_checks(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Runs all QA checks and returns dictionary of outputs.
    """

    outputs = {
        "missingness_summary": missingness_summary(df),
        "non_negativity_check": non_negativity_check(df),
        "key_uniqueness_check": key_uniqueness_check(df),
        "plausibility_flags": plausibility_flags(df)
    }

    return outputs