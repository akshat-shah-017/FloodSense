from __future__ import annotations

import math
from typing import Any

import mlflow
import numpy as np
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score


def evaluate(
    y_true,
    y_pred_prob,
    threshold: float = 0.5,
    metric_prefix: str | None = None,
) -> dict[str, float]:
    y_true_arr = np.asarray(y_true).astype(int)
    y_prob_arr = np.asarray(y_pred_prob).astype(float)
    y_pred_arr = (y_prob_arr >= threshold).astype(int)

    precision = precision_score(y_true_arr, y_pred_arr, zero_division=0)
    recall = recall_score(y_true_arr, y_pred_arr, zero_division=0)
    f1 = f1_score(y_true_arr, y_pred_arr, zero_division=0)

    try:
        auc_roc = roc_auc_score(y_true_arr, y_prob_arr)
    except ValueError:
        auc_roc = float("nan")

    metrics = {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "auc_roc": float(auc_roc),
    }

    prefix = f"{metric_prefix}_" if metric_prefix else ""
    for key, value in metrics.items():
        if not math.isnan(value):
            mlflow.log_metric(f"{prefix}{key}", value)

    return metrics
