from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
from mlflow.tracking import MlflowClient
from psycopg import connect

from preprocessing.feature_builder import FEATURE_COLUMNS


LOGGER = logging.getLogger(__name__)


def _database_dsn() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vyrus")
    return (
        raw.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def compute_psi(expected, actual, buckets: int = 10) -> float:
    expected_arr = np.asarray(expected, dtype=float)
    actual_arr = np.asarray(actual, dtype=float)
    expected_arr = expected_arr[np.isfinite(expected_arr)]
    actual_arr = actual_arr[np.isfinite(actual_arr)]

    if expected_arr.size == 0 or actual_arr.size == 0:
        return 0.0

    # Build bins on expected distribution to keep reference stable.
    quantiles = np.linspace(0.0, 1.0, buckets + 1)
    breakpoints = np.quantile(expected_arr, quantiles)
    breakpoints[0] = -np.inf
    breakpoints[-1] = np.inf
    breakpoints = np.unique(breakpoints)
    if breakpoints.size < 3:
        return 0.0

    expected_counts, _ = np.histogram(expected_arr, bins=breakpoints)
    actual_counts, _ = np.histogram(actual_arr, bins=breakpoints)

    epsilon = 1e-6
    expected_pct = np.maximum(expected_counts / max(expected_arr.size, 1), epsilon)
    actual_pct = np.maximum(actual_counts / max(actual_arr.size, 1), epsilon)
    psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
    return float(psi)


def _latest_city_run_id(city_id: str) -> str:
    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "floodsense-training")
    client = MlflowClient()
    exp = client.get_experiment_by_name(experiment_name)
    if exp is None:
        raise ValueError(f"MLflow experiment not found: {experiment_name}")

    runs = client.search_runs(
        experiment_ids=[exp.experiment_id],
        filter_string=f"tags.city_id = '{city_id}' and attributes.status = 'FINISHED'",
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    if not runs:
        raise ValueError(f"No FINISHED MLflow runs found for city_id={city_id}.")
    return runs[0].info.run_id


def _load_training_feature_stats(run_id: str) -> dict[str, list[float]]:
    artifact = mlflow.artifacts.download_artifacts(
        run_id=run_id,
        artifact_path="drift/training_feature_stats.json",
    )
    payload = json.loads(Path(artifact).read_text(encoding="utf-8"))
    stats = payload.get("feature_samples", {})
    if not stats:
        raise ValueError("training_feature_stats artifact missing 'feature_samples'.")
    return {k: list(v) for k, v in stats.items()}


def _load_actual_last_30_days(city_id: str) -> pd.DataFrame:
    query = """
        SELECT
            wf.spi_1,
            wf.spi_3,
            wf.spi_7,
            wf.twi_mean,
            wf.impervious_pct,
            wf.drain_density,
            wf.dist_river_km,
            wf.population_density,
            wf.flood_freq_10yr,
            wf.precip_realtime
        FROM ward_features wf
        JOIN wards w
          ON wf.ward_id = w.ward_id
        WHERE w.city_id = %s
          AND wf.computed_at >= NOW() - INTERVAL '30 days';
    """
    with connect(_database_dsn()) as conn:
        return pd.read_sql_query(query, conn, params=[city_id])


def run_psi_check(city_id: str = "delhi") -> dict[str, Any]:
    run_id = _latest_city_run_id(city_id)
    training_samples = _load_training_feature_stats(run_id)
    actual_df = _load_actual_last_30_days(city_id)

    drift_features: list[str] = []
    psi_scores: dict[str, float] = {}
    for feature in FEATURE_COLUMNS:
        expected = training_samples.get(feature, [])
        actual = actual_df.get(feature, pd.Series(dtype=float)).fillna(0.0).tolist()
        psi_value = compute_psi(expected, actual, buckets=10)
        psi_scores[feature] = psi_value
        if psi_value > 0.20:
            drift_features.append(feature)

    try:
        mlflow.set_experiment(experiment_name="vyrus_drift_monitoring")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        with mlflow.start_run(run_name=f"psi_drift_check_{timestamp}"):
            for feature, psi_value in psi_scores.items():
                mlflow.log_metric(f"psi_{feature}", psi_value)
    except Exception as exc:
        LOGGER.warning(
            "MLflow logging unavailable for PSI check city=%s: %s",
            city_id,
            exc,
        )

    if drift_features:
        LOGGER.warning("PSI drift detected for city=%s on features=%s", city_id, drift_features)

    return {
        "drift_detected": bool(drift_features),
        "features": drift_features,
        "psi_scores": psi_scores,
        "reference_run_id": run_id,
    }
