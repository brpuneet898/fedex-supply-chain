from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt

from scripts.utils import load_config, ensure_dir, write_text
from scripts.data_build import build_panel
from scripts.features import add_lag_roll_features, make_targets
from scripts.models import (
    prepare_xy,
    train_baseline_moving_average,
    train_glm_models,
    train_lgbm_models,
)
from scripts.evaluation import (
    classification_metrics,
    calibration_slope_intercept,
    regression_metrics,
    slice_errors,
)

def _save_metrics_rows(rows, results_path: str):
    mdf = pd.DataFrame(rows)
    mdf.to_csv(results_path, index=False)

def _plot_roc_pr(y_true, p_pred, out_path):
    from sklearn.metrics import RocCurveDisplay, PrecisionRecallDisplay
    plt.figure()
    RocCurveDisplay.from_predictions(y_true, p_pred)
    PrecisionRecallDisplay.from_predictions(y_true, p_pred)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()

def _plot_calibration(y_true, p_pred, out_path):
    from sklearn.calibration import CalibrationDisplay
    plt.figure()
    CalibrationDisplay.from_predictions(y_true, p_pred, n_bins=10)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()

def _plot_regression_slices(slice_df, out_path):
    # show worst lanes per month (top 10)
    plt.figure()
    # Keep top 10 worst by MAE overall (across months)
    worst = (slice_df.groupby("lane")["mae"].mean().sort_values(ascending=False).head(10).index)
    sub = slice_df[slice_df["lane"].isin(worst)].copy()
    # simple plot: month vs mae for each lane
    for lane, g in sub.groupby("lane"):
        plt.plot(g["month"], g["mae"], marker="o", label=lane)
    plt.xlabel("Month")
    plt.ylabel("MAE (p90 delay days)")
    plt.legend(fontsize=6)
    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close()

def _build_model_card(cfg, panel_stats: dict, metrics_summary: dict) -> str:
    thr = cfg["targets"]["cls_delay_prob_threshold"]
    return f"""# Model Card (1-pager) — Predictive Pilot (Facility/Lane-Week)

## Purpose
Predict weekly operational delay risk at the **facility–lane–week** level using historical shipment performance.

## Data
- Source file: `{cfg["paths"]["data_csv"]}`
- Rows (raw): {panel_stats["raw_rows"]}
- Panel rows (facility×lane×week): {panel_stats["panel_rows"]}
- Time range (shipping date): {panel_stats["min_week"].date()} → {panel_stats["max_week"].date()}

## Targets
### T1 — High delay-probability classification
- Per week: `delay_prob = mean( delay_flag )`
- `delay_flag = 1` if `Days(real) > Days(scheduled)`, else 0
- Label: `y_cls = 1` if `delay_prob ≥ {thr}`, else 0

### T2 — Delay severity regression
- `delay_days = max(0, Days(real) − Days(scheduled))`
- `y_reg = p90(delay_days)` per facility–lane–week

## Models
Baselines:
- Seasonal-naïve (t-1) and moving average (4w) per facility–lane
- GLM: LogisticRegression (T1), Ridge (T2)

Strong:
- LightGBM (T1, T2) + **probability calibration** ({cfg["calibration"]["method"]})

## Evaluation (test window = last {cfg["split"]["test_weeks"]} weeks)
T1 (classification): ROC-AUC, PR-AUC, Brier, calibration slope/intercept  
T2 (regression): MAE, sMAPE + error slicing by lane/month

## Key Results (test)
{metrics_summary}

## Operational Notes / Limitations
- Dataset is e-commerce logistics proxy, not FedEx scan-level events.
- Facility/Lane definitions are approximations: facility=`Order Region`, lane=`Order Country→Customer Country`.
- Weekly aggregation reduces noise but can hide intra-week spikes.
- Threshold-based T1 label (≥{thr}) is tuned for “high-risk” classification to avoid trivial positives.

## Next Steps (when FedEx data arrives)
- Replace facility with true origin facility, lane with origin→destination lane.
- Add scan/event features (handoff times, exception codes) and capacity covariates.
- Calibrate per-service level and incorporate cost proxy if available.
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="Path to YAML config")
    args = ap.parse_args()

    cfg = load_config(args.config)

    # Ensure dirs
    ensure_dir(cfg["paths"]["results_dir"])
    ensure_dir(cfg["paths"]["plots_dir"])
    ensure_dir(cfg["paths"]["models_dir"])

    # Load
    df = pd.read_csv(cfg["paths"]["data_csv"], encoding="latin1", low_memory=False)

    # Build panel + features + targets
    panel = build_panel(df, cfg)
    panel = add_lag_roll_features(panel, cfg)
    panel = make_targets(panel, cfg)

    # Prepare splits
    data, meta = prepare_xy(panel, cfg)

    metrics_rows = []

    # ---- Baseline: naive / moving average (on panel, then evaluate on test)
    panel_b = train_baseline_moving_average(panel)

    # Align baseline predictions to test period
    test_weeks = sorted(panel["week_start"].unique())[-int(cfg["split"]["test_weeks"]):]
    test_mask = panel_b["week_start"].isin(test_weeks)
    test_b = panel_b.loc[test_mask].copy()

    thr = float(cfg["targets"]["cls_delay_prob_threshold"])
    for name, pcol in [("naive", "pred_prob_naive"), ("ma4", "pred_prob_ma4")]:
        p = test_b[pcol].to_numpy()
        y = test_b["y_cls"].to_numpy()
        ok = np.isfinite(p)
        cm = classification_metrics(y[ok], p[ok])
        cal = calibration_slope_intercept(y[ok], p[ok])
        for k, v in {**cm, **cal}.items():
            metrics_rows.append({"task": "T1", "model": f"baseline_{name}", "split": "test", "metric": k, "value": v})

    for name, pcol in [("naive", "pred_p90_naive"), ("ma4", "pred_p90_ma4")]:
        pred = test_b[pcol].to_numpy()
        y = test_b["y_reg"].to_numpy()
        ok = np.isfinite(pred)
        rm = regression_metrics(y[ok], pred[ok])
        for k, v in rm.items():
            metrics_rows.append({"task": "T2", "model": f"baseline_{name}", "split": "test", "metric": k, "value": v})

    # ---- GLM baseline
    glm_clf, glm_reg = train_glm_models(data, meta, cfg)
    p_glm = glm_clf.predict_proba(data.X_test)[:, 1]
    y_test_cls = data.ycls_test
    cm = classification_metrics(y_test_cls, p_glm)
    cal = calibration_slope_intercept(y_test_cls, p_glm)
    for k, v in {**cm, **cal}.items():
        metrics_rows.append({"task": "T1", "model": "glm_logistic", "split": "test", "metric": k, "value": v})

    pred_glm_reg = glm_reg.predict(data.X_test)
    rm = regression_metrics(data.yreg_test, pred_glm_reg)
    for k, v in rm.items():
        metrics_rows.append({"task": "T2", "model": "glm_ridge", "split": "test", "metric": k, "value": v})

    # ---- Strong model: LightGBM + calibration for classification
    lgbm_clf_cal, lgbm_reg = train_lgbm_models(data, meta, cfg)

    p_lgbm = lgbm_clf_cal.predict_proba(data.X_test)[:, 1]
    cm = classification_metrics(y_test_cls, p_lgbm)
    cal = calibration_slope_intercept(y_test_cls, p_lgbm)
    for k, v in {**cm, **cal}.items():
        metrics_rows.append({"task": "T1", "model": "lgbm_calibrated", "split": "test", "metric": k, "value": v})

    pred_lgbm_reg = lgbm_reg.predict(data.X_test)
    rm = regression_metrics(data.yreg_test, pred_lgbm_reg)
    for k, v in rm.items():
        metrics_rows.append({"task": "T2", "model": "lgbm_reg", "split": "test", "metric": k, "value": v})

    # Save models
    joblib.dump(lgbm_clf_cal, str(Path(cfg["paths"]["models_dir"]) / "t1_classifier.joblib"))
    joblib.dump(lgbm_reg, str(Path(cfg["paths"]["models_dir"]) / "t2_regressor.joblib"))

    # Save metrics CSV
    metrics_path = str(Path(cfg["paths"]["results_dir"]) / "predictive_metrics.csv")
    _save_metrics_rows(metrics_rows, metrics_path)

    # Plots (2–3 key plots)
    _plot_roc_pr(y_test_cls, p_lgbm, str(Path(cfg["paths"]["plots_dir"]) / "t1_roc_pr.png"))
    _plot_calibration(y_test_cls, p_lgbm, str(Path(cfg["paths"]["plots_dir"]) / "t1_calibration.png"))

    # regression slices plot
    # rebuild test frame for slices
    test_frame = data.X_test.copy()
    # we need lane/month for slicing; easiest: rebuild from panel aligned with test weeks
    test_panel = panel.loc[panel["week_start"].isin(test_weeks)].copy()
    test_panel = test_panel.sort_values(["facility", "lane", "week_start"]).reset_index(drop=True)
    # prediction ordering: data.X_test ordering corresponds to test_panel feature selection ordering
    test_panel["pred_y_reg"] = pred_lgbm_reg
    slices = slice_errors(test_panel, "y_reg", "pred_y_reg")
    _plot_regression_slices(slices, str(Path(cfg["paths"]["plots_dir"]) / "t2_error_slices.png"))

    # Model card markdown
    panel_stats = {
        "raw_rows": int(len(df)),
        "panel_rows": int(len(panel)),
        "min_week": panel["week_start"].min(),
        "max_week": panel["week_start"].max(),
    }

    # small summary for the card
    # pick best T1/T2 rows for lgbm
    mdf = pd.DataFrame(metrics_rows)
    def _fmt(model, task):
        sub = mdf[(mdf["model"] == model) & (mdf["task"] == task)]
        lines = []
        for metric in ["roc_auc", "pr_auc", "brier", "calib_slope", "calib_intercept", "mae", "smape"]:
            r = sub[sub["metric"] == metric]
            if len(r) == 1 and np.isfinite(r["value"].iloc[0]):
                lines.append(f"- {task} {metric}: {r['value'].iloc[0]:.4f}")
        return "\n".join(lines)

    metrics_summary = _fmt("lgbm_calibrated", "T1") + "\n" + _fmt("lgbm_reg", "T2")
    card = _build_model_card(cfg, panel_stats, metrics_summary)
    write_text(cfg["paths"]["model_card_path"], card)

    print("Done.")
    print(f"Saved: {metrics_path}")
    print(f"Saved plots in: {cfg['paths']['plots_dir']}")
    print(f"Saved models in: {cfg['paths']['models_dir']}")
    print(f"Saved model card: {cfg['paths']['model_card_path']}")

if __name__ == "__main__":
    main()
