from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.frozen import FrozenEstimator

from lightgbm import LGBMClassifier, LGBMRegressor

@dataclass
class PreparedData:
    X_train: pd.DataFrame
    X_val: pd.DataFrame
    X_test: pd.DataFrame
    ycls_train: np.ndarray
    ycls_val: np.ndarray
    ycls_test: np.ndarray
    yreg_train: np.ndarray
    yreg_val: np.ndarray
    yreg_test: np.ndarray

def _split_by_last_weeks(panel: pd.DataFrame, cfg: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # time split by week_start
    weeks = sorted(panel["week_start"].unique())
    test_weeks = int(cfg["split"]["test_weeks"])
    val_weeks = int(cfg["split"]["val_weeks"])

    test_set = set(weeks[-test_weeks:])
    val_set = set(weeks[-(test_weeks + val_weeks):-test_weeks])

    train = panel.loc[~panel["week_start"].isin(test_set | val_set)].copy()
    val = panel.loc[panel["week_start"].isin(val_set)].copy()
    test = panel.loc[panel["week_start"].isin(test_set)].copy()
    return train, val, test

def prepare_xy(panel: pd.DataFrame, cfg: dict) -> Tuple[PreparedData, Dict[str, List[str]]]:
    train, val, test = _split_by_last_weeks(panel, cfg)

    # features
    id_cols = ["facility", "lane", "week_start"]
    target_cols = ["y_cls", "y_reg", "delay_prob", "delay_p90", "delay_mean", "shipments"]
    drop_cols = set(id_cols + target_cols)

    # keep shipping-mode proportions + lag/roll + seasonality + market
    feature_cols = [c for c in panel.columns if c not in drop_cols]
    X_train = train[feature_cols].copy()
    X_val = val[feature_cols].copy()
    X_test = test[feature_cols].copy()

    ycls_train = train["y_cls"].to_numpy()
    ycls_val = val["y_cls"].to_numpy()
    ycls_test = test["y_cls"].to_numpy()

    yreg_train = train["y_reg"].to_numpy()
    yreg_val = val["y_reg"].to_numpy()
    yreg_test = test["y_reg"].to_numpy()

    # identify categorical columns
    cat_cols = []
    for c in X_train.columns:
        if X_train[c].dtype == "object":
            cat_cols.append(c)

    num_cols = [c for c in X_train.columns if c not in cat_cols]

    for c in num_cols:
        X_train[c] = pd.to_numeric(X_train[c], errors="coerce")
        X_val[c] = pd.to_numeric(X_val[c], errors="coerce")
        X_test[c] = pd.to_numeric(X_test[c], errors="coerce")

    meta = {"cat_cols": cat_cols, "num_cols": num_cols, "feature_cols": feature_cols}
    return PreparedData(X_train, X_val, X_test, ycls_train, ycls_val, ycls_test, yreg_train, yreg_val, yreg_test), meta

# def make_preprocessor(cat_cols: List[str], num_cols: List[str]) -> ColumnTransformer:
#     return ColumnTransformer(
#         transformers=[
#             ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
#             ("num", "passthrough", num_cols),
#         ],
#         remainder="drop",
#         sparse_threshold=0.3,
#     )

def make_preprocessor(cat_cols: List[str], num_cols: List[str]) -> ColumnTransformer:
    cat_pipe = Pipeline(steps=[
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("ohe", OneHotEncoder(handle_unknown="ignore")),
    ])

    num_pipe = Pipeline(steps=[
        ("impute", SimpleImputer(strategy="median")),
        # Scaling not required, but helps GLM stability; safe with sparse? yes because this is numeric branch.
        ("scale", StandardScaler(with_mean=False)),
    ])

    return ColumnTransformer(
        transformers=[
            ("cat", cat_pipe, cat_cols),
            ("num", num_pipe, num_cols),
        ],
        remainder="drop",
        sparse_threshold=0.3,
    )

def train_baseline_moving_average(panel: pd.DataFrame) -> pd.DataFrame:
    # Predict current week using last week and 4-week rolling mean within facility/lane
    panel = panel.sort_values(["facility", "lane", "week_start"]).copy()
    g = panel.groupby(["facility", "lane"], group_keys=False)

    panel["pred_prob_naive"] = g["delay_prob"].shift(1)
    panel["pred_prob_ma4"] = g["delay_prob"].shift(1).rolling(4).mean()

    panel["pred_p90_naive"] = g["delay_p90"].shift(1)
    panel["pred_p90_ma4"] = g["delay_p90"].shift(1).rolling(4).mean()

    return panel

def train_glm_models(data: PreparedData, meta: Dict[str, Any], cfg: dict):
    prep = make_preprocessor(meta["cat_cols"], meta["num_cols"])

    clf = Pipeline(steps=[
        ("prep", prep),
        ("model", LogisticRegression(
            C=float(cfg["models"]["glm"]["cls_C"]),
            max_iter=2000,
            n_jobs=None
        )),
    ])

    reg = Pipeline(steps=[
        ("prep", prep),
        ("model", Ridge(alpha=float(cfg["models"]["glm"]["reg_alpha"]))),
    ])

    clf.fit(data.X_train, data.ycls_train)
    reg.fit(data.X_train, data.yreg_train)

    return clf, reg

def train_lgbm_models(data: PreparedData, meta: Dict[str, Any], cfg: dict):
    prep = make_preprocessor(meta["cat_cols"], meta["num_cols"])

    cls_params = cfg["models"]["lgbm"]["cls"]
    reg_params = cfg["models"]["lgbm"]["reg"]

    base_clf = LGBMClassifier(**cls_params)
    clf_pipe = Pipeline(steps=[("prep", prep), ("model", base_clf)])

    # Fit uncalibrated on train, then calibrate using val
    clf_pipe.fit(data.X_train, data.ycls_train)

    # Calibration operates on estimator with predict_proba; we calibrate the *whole pipeline*
    # method = cfg["calibration"]["method"]
    # calib = CalibratedClassifierCV(clf_pipe, method=method, cv="prefit")
    # calib.fit(data.X_val, data.ycls_val)

    # ---- Calibration (new sklearn API)
    method = cfg["calibration"]["method"]

    # Freeze the already-fitted pipeline
    frozen_clf = FrozenEstimator(clf_pipe)

    calib = CalibratedClassifierCV(
        estimator=frozen_clf,
        method=method
    )

    # Fit ONLY on validation data
    calib.fit(data.X_val, data.ycls_val)

    reg_pipe = Pipeline(steps=[("prep", prep), ("model", LGBMRegressor(**reg_params))])
    reg_pipe.fit(data.X_train, data.yreg_train)

    return calib, reg_pipe
