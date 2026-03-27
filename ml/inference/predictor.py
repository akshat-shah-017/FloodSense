from __future__ import annotations

import logging
import os
import time
from typing import Any

import mlflow
import mlflow.lightgbm
import mlflow.pytorch
import mlflow.xgboost
import numpy as np
import pandas as pd
from mlflow.tracking import MlflowClient
from psycopg import connect

from models.combined_scorer import combine_scores, score_to_risk
from models.ensemble import compute_shap_values, predict_ensemble
from models.lstm import predict_lstm
from preprocessing.feature_builder import FEATURE_COLUMNS
from preprocessing.scaler import load_scaler_from_mlflow, transform

logger = logging.getLogger(__name__)


def _database_dsn() -> str:
    db_url = (
        os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vyrus")
        .replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )
    return db_url


def _latest_model_version(model_name: str):
    client = MlflowClient()
    versions = client.search_model_versions(f"name='{model_name}'")
    if not versions:
        raise ValueError(f"No registered versions found for model '{model_name}'.")
    latest = max(versions, key=lambda mv: int(mv.version))
    return latest


def load_models(city_id: str = "delhi") -> dict[str, Any]:
    lgbm_name = f"vyrus_lgbm_{city_id}"
    xgb_name = f"vyrus_xgb_{city_id}"
    lstm_name = f"vyrus_lstm_{city_id}"

    lgbm_ver = _latest_model_version(lgbm_name)
    xgb_ver = _latest_model_version(xgb_name)
    lstm_ver = _latest_model_version(lstm_name)

    lgbm_model = mlflow.lightgbm.load_model(f"models:/{lgbm_name}/{lgbm_ver.version}")
    xgb_model = mlflow.xgboost.load_model(f"models:/{xgb_name}/{xgb_ver.version}")
    lstm_model = mlflow.pytorch.load_model(f"models:/{lstm_name}/{lstm_ver.version}")

    # scaler is loaded from the run that produced latest LightGBM version
    scaler = load_scaler_from_mlflow(lgbm_ver.run_id)

    return {
        "lgbm": lgbm_model,
        "xgb": xgb_model,
        "lstm": lstm_model,
        "scaler": scaler,
        "model_version": (
            f"lgbm_v{lgbm_ver.version}|xgb_v{xgb_ver.version}|lstm_v{lstm_ver.version}"
        ),
        "run_id": lgbm_ver.run_id,
    }


def _load_latest_features(city_id: str) -> pd.DataFrame:
    query = """
        SELECT DISTINCT ON (wf.ward_id)
            wf.ward_id,
            wf.computed_at,
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
        ORDER BY wf.ward_id, wf.computed_at DESC;
    """
    with connect(_database_dsn()) as conn:
        df = pd.read_sql_query(query, conn, params=[city_id])
    return df


def _load_all_ward_ids(city_id: str) -> list[int]:
    query = """
        SELECT ward_id
        FROM wards
        WHERE city_id = %s
        ORDER BY ward_id;
    """
    with connect(_database_dsn()) as conn:
        wards_df = pd.read_sql_query(query, conn, params=[city_id])
    return wards_df["ward_id"].astype(int).tolist()


def _load_recent_spi_series(city_id: str) -> pd.DataFrame:
    query = """
        SELECT
            wf.ward_id,
            wf.computed_at,
            wf.spi_1
        FROM ward_features wf
        JOIN wards w
          ON wf.ward_id = w.ward_id
        WHERE w.city_id = %s
          AND wf.computed_at >= NOW() - INTERVAL '30 days'
        ORDER BY wf.ward_id, wf.computed_at;
    """
    with connect(_database_dsn()) as conn:
        return pd.read_sql_query(query, conn, params=[city_id])


def _build_lstm_inference_sequences(
    recent_spi_df: pd.DataFrame,
    ward_ids: list[int],
    seq_len: int = 7,
) -> np.ndarray:
    seq_map: dict[int, np.ndarray] = {}
    for ward_id, ward_df in recent_spi_df.groupby("ward_id"):
        values = ward_df["spi_1"].fillna(0.0).astype(float).to_numpy()
        if len(values) >= seq_len:
            seq = values[-seq_len:]
        elif len(values) == 0:
            seq = np.zeros(seq_len, dtype=np.float32)
        else:
            pad = np.full(seq_len - len(values), values[0], dtype=np.float32)
            seq = np.concatenate([pad, values.astype(np.float32)])
        seq_map[int(ward_id)] = seq.reshape(seq_len, 1)

    X_seq = []
    for ward_id in ward_ids:
        X_seq.append(seq_map.get(int(ward_id), np.zeros((seq_len, 1), dtype=np.float32)))
    return np.asarray(X_seq, dtype=np.float32)


def predict_all_wards(city_id: str = "delhi") -> list[dict[str, Any]]:
    t0 = time.time()
    all_ward_ids = _load_all_ward_ids(city_id)
    if not all_ward_ids:
        logger.warning("No wards found for city_id=%s", city_id)
        return []

    records: list[dict[str, Any]] = []
    latest_df = _load_latest_features(city_id)
    if not latest_df.empty:
        bundle = load_models(city_id=city_id)
        recent_spi = _load_recent_spi_series(city_id)

        ward_ids = latest_df["ward_id"].astype(int).tolist()
        X = latest_df[FEATURE_COLUMNS].fillna(0.0)
        X_scaled = transform(X, bundle["scaler"])

        ensemble_prob = predict_ensemble(bundle["lgbm"], bundle["xgb"], X_scaled)
        seq_len = int(os.getenv("LSTM_SEQ_LEN", "7"))
        X_seq = _build_lstm_inference_sequences(recent_spi, ward_ids, seq_len=seq_len)
        lstm_prob = predict_lstm(bundle["lstm"], X_seq)
        combined_prob = combine_scores(ensemble_prob, lstm_prob, tabular_weight=0.6, lstm_weight=0.4)
        risk_score, risk_tier, ci_lower, ci_upper = score_to_risk(combined_prob)

        shap_df = compute_shap_values(bundle["lgbm"], X_scaled, top_n=5)
        if len(shap_df) != len(latest_df):
            shap_df = shap_df.reindex(range(len(latest_df))).fillna(value=np.nan)

        for idx, ward_id in enumerate(ward_ids):
            row = {
                "ward_id": int(ward_id),
                "risk_score": float(risk_score[idx]),
                "ci_lower": float(ci_lower[idx]),
                "ci_upper": float(ci_upper[idx]),
                "risk_tier": str(risk_tier[idx]),
                "model_version": bundle["model_version"],
            }
            if idx < len(shap_df):
                for rank in range(1, 6):
                    row[f"shap_feature_{rank}"] = shap_df.iloc[idx].get(f"shap_feature_{rank}")
                    row[f"shap_value_{rank}"] = (
                        None
                        if pd.isna(shap_df.iloc[idx].get(f"shap_value_{rank}"))
                        else float(shap_df.iloc[idx].get(f"shap_value_{rank}"))
                    )
            records.append(row)
    else:
        logger.warning(
            "No ward_features found for city_id=%s; generating NO_DATA fallback predictions.",
            city_id,
        )

    predicted_ward_ids = {int(record["ward_id"]) for record in records}
    missing_ward_ids = [ward_id for ward_id in all_ward_ids if ward_id not in predicted_ward_ids]
    for ward_id in missing_ward_ids:
        logger.warning("Ward %s has no features — using fallback NO_DATA prediction", ward_id)
        records.append(
            {
                "ward_id": int(ward_id),
                "risk_score": 0.0,
                "ci_lower": 0.0,
                "ci_upper": 0.0,
                "risk_tier": "UNKNOWN",
                "shap_feature_1": "no_data",
                "shap_value_1": 0.0,
                "shap_feature_2": "no_data",
                "shap_value_2": 0.0,
                "shap_feature_3": "no_data",
                "shap_value_3": 0.0,
                "model_version": "fallback",
                "source_status": "NO_DATA",
            }
        )

    records.sort(key=lambda row: int(row["ward_id"]))

    elapsed = time.time() - t0
    if elapsed > 60:
        logger.warning("inference took %.2fs (>60s target).", elapsed)
    return records
