from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from evaluation.metrics import evaluate


def _aggregate_metric_dicts(metric_dicts: list[dict[str, float]]) -> dict[str, float]:
    if not metric_dicts:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "auc_roc": 0.0}

    keys = metric_dicts[0].keys()
    return {
        key: float(np.nanmean([metrics[key] for metrics in metric_dicts]))
        for key in keys
    }


def walk_forward_validate(
    df: pd.DataFrame,
    model_trainer_fn: Callable[[pd.DataFrame, pd.DataFrame], tuple[np.ndarray, np.ndarray]],
) -> dict[str, dict[str, float]]:
    """
    Strict walk-forward validation by year. No future data leakage.

    model_trainer_fn signature:
    model_trainer_fn(train_df, eval_df) -> (y_true, y_pred_prob)
    """
    if "date" not in df.columns:
        raise ValueError("Input dataframe must include a 'date' column.")

    data = df.copy()
    data["date"] = pd.to_datetime(data["date"])
    data["year"] = data["date"].dt.year
    data = data.sort_values(["date", "ward_id"]).reset_index(drop=True)

    train_base = data[(data["year"] >= 2005) & (data["year"] <= 2017)].copy()
    if train_base.empty:
        raise ValueError("No training data in years 2005-2017.")

    # Baseline train metrics
    y_train_true, y_train_prob = model_trainer_fn(train_base, train_base)
    train_metrics = evaluate(y_train_true, y_train_prob, metric_prefix="walk_forward_train")

    # Validation folds: 2018-2020
    val_metrics_by_year: list[dict[str, float]] = []
    for year in range(2018, 2021):
        fold_train = data[data["year"] <= (year - 1)].copy()
        fold_eval = data[data["year"] == year].copy()
        if fold_train.empty or fold_eval.empty:
            continue
        y_true, y_prob = model_trainer_fn(fold_train, fold_eval)
        metrics = evaluate(y_true, y_prob, metric_prefix=f"walk_forward_val_{year}")
        val_metrics_by_year.append(metrics)

    # Test folds: 2021-2023
    test_metrics_by_year: list[dict[str, float]] = []
    for year in range(2021, 2024):
        fold_train = data[data["year"] <= (year - 1)].copy()
        fold_eval = data[data["year"] == year].copy()
        if fold_train.empty or fold_eval.empty:
            continue
        y_true, y_prob = model_trainer_fn(fold_train, fold_eval)
        metrics = evaluate(y_true, y_prob, metric_prefix=f"walk_forward_test_{year}")
        test_metrics_by_year.append(metrics)

    return {
        "train_metrics": train_metrics,
        "val_metrics": _aggregate_metric_dicts(val_metrics_by_year),
        "test_metrics": _aggregate_metric_dicts(test_metrics_by_year),
    }
