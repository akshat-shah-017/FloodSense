from __future__ import annotations

import tempfile
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


SCALER_ARTIFACT_DIR = "feature_scaler"
SCALER_ARTIFACT_FILE = "feature_scaler/scaler.joblib"


def fit_scaler(X_train: pd.DataFrame) -> MinMaxScaler:
    if not isinstance(X_train, pd.DataFrame):
        raise TypeError("X_train must be a pandas DataFrame.")

    scaler = MinMaxScaler()
    scaler.fit(X_train)

    with tempfile.TemporaryDirectory() as tmp_dir:
        local_path = Path(tmp_dir) / "scaler.joblib"
        payload = {
            "scaler": scaler,
            "feature_columns": list(X_train.columns),
        }
        joblib.dump(payload, local_path)
        mlflow.log_artifact(str(local_path), artifact_path=SCALER_ARTIFACT_DIR)

    return scaler


def transform(X: pd.DataFrame, scaler: MinMaxScaler) -> pd.DataFrame:
    if not isinstance(X, pd.DataFrame):
        raise TypeError("X must be a pandas DataFrame.")

    if not hasattr(scaler, "feature_names_in_"):
        raise ValueError("Scaler is missing fitted feature_names_in_.")

    expected_cols = list(scaler.feature_names_in_)
    actual_cols = list(X.columns)
    if expected_cols != actual_cols:
        raise ValueError(
            f"Feature column mismatch. Expected {expected_cols}, got {actual_cols}."
        )

    transformed = scaler.transform(X)
    return pd.DataFrame(transformed, columns=actual_cols, index=X.index)


def load_scaler_from_mlflow(run_id: str) -> MinMaxScaler:
    artifact_path = mlflow.artifacts.download_artifacts(
        run_id=run_id,
        artifact_path=SCALER_ARTIFACT_FILE,
    )
    payload = joblib.load(artifact_path)
    scaler = payload["scaler"] if isinstance(payload, dict) and "scaler" in payload else payload
    return scaler
