from __future__ import annotations

from collections import Counter

import mlflow
import pandas as pd
from imblearn.over_sampling import SMOTE


def _class_distribution(y) -> dict[str, int]:
    counts = Counter(int(v) for v in y)
    return {"class_0": counts.get(0, 0), "class_1": counts.get(1, 0)}


def apply_smote(
    X_train: pd.DataFrame,
    y_train: pd.Series,
) -> tuple[pd.DataFrame, pd.Series]:
    """
    Apply SMOTE with max flood:non-flood ratio of 1:3.
    Returns resampled (X_resampled, y_resampled).
    """
    if not isinstance(X_train, pd.DataFrame):
        raise TypeError("X_train must be a pandas DataFrame.")

    pre_dist = _class_distribution(y_train)
    mlflow.log_dict(pre_dist, "smote/class_distribution_pre.json")

    n_non_flood = pre_dist["class_0"]
    n_flood = pre_dist["class_1"]
    if n_non_flood == 0 or n_flood == 0:
        mlflow.log_param("smote_applied", False)
        mlflow.log_param("smote_reason", "single_class_training_data")
        return X_train.copy(), y_train.copy()

    current_ratio = n_flood / n_non_flood
    target_ratio = 1.0 / 3.0

    if current_ratio >= target_ratio:
        mlflow.log_param("smote_applied", False)
        mlflow.log_param("smote_reason", "ratio_already_at_or_above_target")
        mlflow.log_dict(pre_dist, "smote/class_distribution_post.json")
        return X_train.copy(), y_train.copy()

    smote = SMOTE(sampling_strategy=target_ratio, random_state=42, k_neighbors=5)
    X_resampled_np, y_resampled_np = smote.fit_resample(X_train, y_train)
    X_resampled = pd.DataFrame(X_resampled_np, columns=X_train.columns)
    y_resampled = pd.Series(y_resampled_np, name=y_train.name or "label")

    post_dist = _class_distribution(y_resampled)
    mlflow.log_param("smote_applied", True)
    mlflow.log_param("smote_target_ratio", target_ratio)
    mlflow.log_dict(post_dist, "smote/class_distribution_post.json")

    return X_resampled, y_resampled
