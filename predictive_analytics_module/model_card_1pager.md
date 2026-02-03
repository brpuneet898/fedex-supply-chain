# Model Card (1-pager) — Predictive Pilot (Facility/Lane-Week)

## Purpose
Predict weekly operational delay risk at the **facility–lane–week** level using historical shipment performance.

## Data
- Source file: `./DataCoSupplyChainDataset.csv`
- Rows (raw): 180519
- Panel rows (facility×lane×week): 4342
- Time range (shipping date): 2015-02-02 → 2018-02-05

## Targets
### T1 — High delay-probability classification
- Per week: `delay_prob = mean( delay_flag )`
- `delay_flag = 1` if `Days(real) > Days(scheduled)`, else 0
- Label: `y_cls = 1` if `delay_prob ≥ 0.8`, else 0

### T2 — Delay severity regression
- `delay_days = max(0, Days(real) − Days(scheduled))`
- `y_reg = p90(delay_days)` per facility–lane–week

## Models
Baselines:
- Seasonal-naïve (t-1) and moving average (4w) per facility–lane
- GLM: LogisticRegression (T1), Ridge (T2)

Strong:
- LightGBM (T1, T2) + **probability calibration** (isotonic)

## Evaluation (test window = last 8 weeks)
T1 (classification): ROC-AUC, PR-AUC, Brier, calibration slope/intercept  
T2 (regression): MAE, sMAPE + error slicing by lane/month

## Key Results (test)
- T1 roc_auc: 0.7797
- T1 pr_auc: 0.5824
- T1 brier: 0.1428
- T1 calib_slope: 0.0398
- T1 calib_intercept: 0.3093
- T2 mae: 0.5681
- T2 smape: 0.4124

## Operational Notes / Limitations
- Dataset is e-commerce logistics proxy, not FedEx scan-level events.
- Facility/Lane definitions are approximations: facility=`Order Region`, lane=`Order Country→Customer Country`.
- Weekly aggregation reduces noise but can hide intra-week spikes.
- Threshold-based T1 label (≥0.8) is tuned for “high-risk” classification to avoid trivial positives.

## Next Steps (when FedEx data arrives)
- Replace facility with true origin facility, lane with origin→destination lane.
- Add scan/event features (handoff times, exception codes) and capacity covariates.
- Calibrate per-service level and incorporate cost proxy if available.
