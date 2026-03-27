from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

import mlflow
import mlflow.lightgbm
import mlflow.pytorch
import mlflow.xgboost
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from mlflow.tracking import MlflowClient

from evaluation.metrics import evaluate
from evaluation.walk_forward import walk_forward_validate
from models.combined_scorer import combine_scores
from models.ensemble import predict_ensemble, train_lgbm, train_xgb
from models.lstm import build_sequences, predict_lstm, train_lstm
from preprocessing.feature_builder import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    load_training_data,
    prepare_feature_target,
    split_by_year,
)
from preprocessing.scaler import fit_scaler, transform
from preprocessing.smote_handler import apply_smote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FloodSense ML training pipeline")
    parser.add_argument("--city_id", default="delhi", help="City id for model training")
    parser.add_argument(
        "--mlflow_experiment_name",
        default="floodsense-training",
        help="MLflow experiment name",
    )
    parser.add_argument(
        "--force-register",
        action="store_true",
        help="Force model registration even if threshold metrics are not met.",
    )
    return parser.parse_args()


def _hash_dataframe(df: pd.DataFrame) -> str:
    stable = df.sort_values(["ward_id", "date"]).reset_index(drop=True)
    values = stable.to_json(orient="split", date_format="iso").encode("utf-8")
    return hashlib.sha256(values).hexdigest()


def _align_for_combination(
    tabular_prob: np.ndarray,
    lstm_prob: np.ndarray,
    y_true: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    min_len = min(len(tabular_prob), len(lstm_prob), len(y_true))
    if min_len == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float), np.asarray([], dtype=int)
    return (
        np.asarray(tabular_prob[-min_len:], dtype=float),
        np.asarray(lstm_prob[-min_len:], dtype=float),
        np.asarray(y_true[-min_len:], dtype=int),
    )


def _register_models_if_eligible(
    run_id: str,
    city_id: str,
    test_metrics: dict[str, float],
    lstm_trained: bool,
    force_register: bool = False,
) -> None:
    f1 = float(test_metrics.get("f1", 0.0))
    auc = float(test_metrics.get("auc_roc", 0.0))
    eligible = force_register or (f1 > 0.80 and auc > 0.90)
    mlflow.log_param("model_registration_eligible", eligible)
    mlflow.log_param("model_registration_forced", force_register)
    if not eligible:
        return

    client = MlflowClient()
    model_specs = [
        ("lgbm_model", f"vyrus_lgbm_{city_id}"),
        ("xgb_model", f"vyrus_xgb_{city_id}"),
    ]
    if lstm_trained:
        model_specs.append(("lstm_model", f"vyrus_lstm_{city_id}"))

    for artifact_path, model_name in model_specs:
        model_uri = f"runs:/{run_id}/{artifact_path}"
        registered = mlflow.register_model(model_uri, model_name)
        client.set_model_version_tag(model_name, registered.version, "city_id", city_id)
        client.set_model_version_tag(model_name, registered.version, "source_run_id", run_id)


def _build_walk_forward_trainer():
    def trainer(train_df: pd.DataFrame, eval_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        X_train = train_df[FEATURE_COLUMNS].fillna(0.0)
        y_train = train_df[TARGET_COLUMN].astype(int)
        X_eval = eval_df[FEATURE_COLUMNS].fillna(0.0)
        y_eval = eval_df[TARGET_COLUMN].astype(int).to_numpy()

        model = LGBMClassifier(
            n_estimators=200,
            learning_rate=0.05,
            num_leaves=31,
            objective="binary",
            random_state=42,
        )
        model.fit(X_train, y_train)
        y_prob = model.predict_proba(X_eval)[:, 1]
        return y_eval, y_prob

    return trainer


def main() -> None:
    args = parse_args()
    mlflow.set_experiment(args.mlflow_experiment_name)

    with mlflow.start_run(run_name=f"train_{args.city_id}_{datetime.now(timezone.utc).isoformat()}"):
        mlflow.set_tag("city_id", args.city_id)
        mlflow.set_tag("pipeline_phase", "phase_4_training")

        df = load_training_data(city_id=args.city_id)
        splits = split_by_year(df)
        train_df, val_df, test_df = splits["train"], splits["val"], splits["test"]

        X_train, y_train = prepare_feature_target(train_df)
        X_val, y_val = prepare_feature_target(val_df)
        X_test, y_test = prepare_feature_target(test_df)

        X_train_smote, y_train_smote = apply_smote(X_train, y_train)
        scaler = fit_scaler(X_train_smote)

        X_train_scaled = transform(X_train_smote, scaler)
        X_val_scaled = transform(X_val, scaler)
        X_test_scaled = transform(X_test, scaler)

        lgbm_model = train_lgbm(X_train_scaled, y_train_smote, X_val_scaled, y_val)
        xgb_model = train_xgb(X_train_scaled, y_train_smote, X_val_scaled, y_val)
        ensemble_val_prob = predict_ensemble(lgbm_model, xgb_model, X_val_scaled)
        ensemble_test_prob = predict_ensemble(lgbm_model, xgb_model, X_test_scaled)

        lstm_seq_len = int(os.getenv("LSTM_SEQ_LEN", "7"))
        lstm_epochs = int(os.getenv("LSTM_EPOCHS", "50"))
        mlflow.log_param("lstm_seq_len_config", lstm_seq_len)
        mlflow.log_param("lstm_epochs_config", lstm_epochs)
        lstm_train_X, lstm_train_y = build_sequences(
            train_df[["ward_id", "date", "spi_1", "label"]],
            seq_len=lstm_seq_len,
        )
        lstm_val_X, lstm_val_y = build_sequences(
            val_df[["ward_id", "date", "spi_1", "label"]],
            seq_len=lstm_seq_len,
        )
        lstm_test_X, lstm_test_y = build_sequences(
            test_df[["ward_id", "date", "spi_1", "label"]],
            seq_len=lstm_seq_len,
        )

        lstm_model = None
        combined_val_metrics: dict[str, float]
        combined_test_metrics: dict[str, float]

        if len(lstm_train_X) > 0 and len(lstm_val_X) > 0:
            lstm_model = train_lstm(
                lstm_train_X,
                lstm_train_y,
                lstm_val_X,
                lstm_val_y,
                epochs=lstm_epochs,
                lr=0.001,
            )
            lstm_val_prob = predict_lstm(lstm_model, lstm_val_X)
            lstm_test_prob = predict_lstm(lstm_model, lstm_test_X)

            val_tab, val_lstm, y_val_aligned = _align_for_combination(
                ensemble_val_prob, lstm_val_prob, y_val.to_numpy()
            )
            test_tab, test_lstm, y_test_aligned = _align_for_combination(
                ensemble_test_prob, lstm_test_prob, y_test.to_numpy()
            )

            val_combined_prob = combine_scores(val_tab, val_lstm, tabular_weight=0.6, lstm_weight=0.4)
            test_combined_prob = combine_scores(test_tab, test_lstm, tabular_weight=0.6, lstm_weight=0.4)
            combined_val_metrics = evaluate(y_val_aligned, val_combined_prob, metric_prefix="combined_val")
            combined_test_metrics = evaluate(y_test_aligned, test_combined_prob, metric_prefix="combined_test")
        else:
            combined_val_metrics = evaluate(y_val, ensemble_val_prob, metric_prefix="combined_val")
            combined_test_metrics = evaluate(y_test, ensemble_test_prob, metric_prefix="combined_test")

        walk_forward_metrics = walk_forward_validate(df, _build_walk_forward_trainer())
        mlflow.log_dict(walk_forward_metrics, "evaluation/walk_forward_metrics.json")

        mlflow.lightgbm.log_model(lgbm_model, artifact_path="lgbm_model")
        mlflow.xgboost.log_model(xgb_model, artifact_path="xgb_model")
        if lstm_model is not None:
            mlflow.pytorch.log_model(lstm_model, artifact_path="lstm_model")

        # Drift reference artifact (training distributions for PSI checks)
        feature_samples = {
            feature: train_df[feature].fillna(0.0).astype(float).head(10000).tolist()
            for feature in FEATURE_COLUMNS
        }
        mlflow.log_dict({"feature_samples": feature_samples}, "drift/training_feature_stats.json")

        lineage = {
            "training_data_hash": _hash_dataframe(df[["ward_id", "date"] + FEATURE_COLUMNS + [TARGET_COLUMN]]),
            "feature_set_version": os.environ.get("FEATURE_SET_VERSION", "v1.0"),
            "date_range": {
                "start": str(pd.to_datetime(df["date"]).min().date()),
                "end": str(pd.to_datetime(df["date"]).max().date()),
            },
            "evaluation_metrics": {
                "combined_val_metrics": combined_val_metrics,
                "combined_test_metrics": combined_test_metrics,
                "walk_forward_metrics": walk_forward_metrics,
            },
        }
        mlflow.log_dict(lineage, "data_lineage.json")

        run_id = mlflow.active_run().info.run_id
        _register_models_if_eligible(
            run_id=run_id,
            city_id=args.city_id,
            test_metrics=combined_test_metrics,
            lstm_trained=lstm_model is not None,
            force_register=args.force_register,
        )


if __name__ == "__main__":
    main()
