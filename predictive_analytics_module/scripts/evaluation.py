from __future__ import annotations
import numpy as np
import pandas as pd

from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss,
    mean_absolute_error
)

def classification_metrics(y_true: np.ndarray, p_pred: np.ndarray) -> dict:
    # protect against degenerate y
    out = {}
    if len(np.unique(y_true)) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, p_pred))
        out["pr_auc"] = float(average_precision_score(y_true, p_pred))
    else:
        out["roc_auc"] = np.nan
        out["pr_auc"] = np.nan
    out["brier"] = float(brier_score_loss(y_true, p_pred))
    return out

def calibration_slope_intercept(y_true: np.ndarray, p_pred: np.ndarray) -> dict:
    # Fit y ~ a + b * logit(p) (simple calibration diagnostic)
    eps = 1e-6
    p = np.clip(p_pred, eps, 1 - eps)
    logit = np.log(p / (1 - p))

    X = np.column_stack([np.ones_like(logit), logit])
    y = y_true.astype(float)

    # least squares
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    intercept, slope = beta[0], beta[1]
    return {"calib_intercept": float(intercept), "calib_slope": float(slope)}

def smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denom = (np.abs(y_true) + np.abs(y_pred)).clip(min=1e-6)
    return float(np.mean(2.0 * np.abs(y_pred - y_true) / denom))

def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "smape": smape(y_true, y_pred),
    }

def slice_errors(df: pd.DataFrame, y_col: str, pred_col: str) -> pd.DataFrame:
    # error by lane + season (month)
    out = []
    for (lane, month), g in df.groupby(["lane", "month"]):
        out.append({
            "lane": lane,
            "month": int(month),
            "n": int(len(g)),
            "mae": float(np.mean(np.abs(g[y_col] - g[pred_col]))),
        })
    return pd.DataFrame(out).sort_values(["month", "mae"], ascending=[True, False])
