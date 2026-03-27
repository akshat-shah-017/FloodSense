from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from psycopg import connect


FEATURE_COLUMNS = [
    "spi_1",
    "spi_3",
    "spi_7",
    "twi_mean",
    "impervious_pct",
    "drain_density",
    "dist_river_km",
    "population_density",
    "flood_freq_10yr",
    "precip_realtime",
]
TARGET_COLUMN = "label"


def _database_dsn() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vyrus")
    return (
        raw.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def _default_labels_path() -> Path:
    env_value = os.getenv("FLOOD_LABELS_CSV_PATH")
    if env_value:
        return Path(env_value)

    docker_default = Path("/app/data/indofloods_labels.csv")
    if docker_default.exists():
        return docker_default

    return Path(__file__).resolve().parents[2] / "data" / "indofloods_labels.csv"


def _load_labels_csv() -> pd.DataFrame:
    labels_path = _default_labels_path()
    if not labels_path.exists():
        raise FileNotFoundError(
            f"Flood labels CSV not found at '{labels_path}'. Set FLOOD_LABELS_CSV_PATH."
        )

    labels = pd.read_csv(labels_path)
    if "ward_id" not in labels.columns:
        raise ValueError("Labels CSV must include 'ward_id'.")

    date_col = None
    for candidate in ("date", "event_date", "flood_date"):
        if candidate in labels.columns:
            date_col = candidate
            break
    if date_col is None:
        raise ValueError("Labels CSV must include one of: date, event_date, flood_date.")

    if "label" not in labels.columns:
        labels["label"] = 1

    out = labels[["ward_id", date_col, "label"]].copy()
    out.rename(columns={date_col: "date"}, inplace=True)
    out["date"] = pd.to_datetime(out["date"], utc=True, errors="coerce").dt.date
    out = out.dropna(subset=["date"])
    out["ward_id"] = out["ward_id"].astype(int)
    out["label"] = out["label"].fillna(0).astype(int).clip(0, 1)
    out = out.groupby(["ward_id", "date"], as_index=False)["label"].max()
    return out


def load_training_data(city_id: str = "delhi") -> pd.DataFrame:
    """
    Load ward-level training features from PostGIS and join historical flood labels.

    Returns DataFrame columns:
    ward_id, date, spi_1, spi_3, spi_7, twi_mean, impervious_pct, drain_density,
    dist_river_km, population_density, flood_freq_10yr, precip_realtime,
    precip_observed, label
    """
    labels_df = _load_labels_csv()

    query = """
        SELECT
            wf.ward_id,
            DATE(wf.computed_at) AS date,
            AVG(wf.spi_1) AS spi_1,
            AVG(wf.spi_3) AS spi_3,
            AVG(wf.spi_7) AS spi_7,
            AVG(wf.twi_mean) AS twi_mean,
            AVG(wf.impervious_pct) AS impervious_pct,
            AVG(wf.drain_density) AS drain_density,
            AVG(wf.dist_river_km) AS dist_river_km,
            AVG(wf.population_density) AS population_density,
            AVG(wf.flood_freq_10yr) AS flood_freq_10yr,
            AVG(wf.precip_realtime) AS precip_realtime,
            AVG(wf.precip_observed) AS precip_observed
        FROM ward_features wf
        JOIN wards w
          ON w.ward_id = wf.ward_id
        WHERE w.city_id = %s
          AND wf.computed_at >= TIMESTAMPTZ '2005-01-01'
          AND wf.computed_at < TIMESTAMPTZ '2024-01-01'
        GROUP BY wf.ward_id, DATE(wf.computed_at)
        ORDER BY date, ward_id;
    """

    with connect(_database_dsn()) as conn:
        feature_df = pd.read_sql_query(query, conn, params=[city_id])

    feature_df["date"] = pd.to_datetime(feature_df["date"], utc=True, errors="coerce").dt.date
    merged = feature_df.merge(labels_df, on=["ward_id", "date"], how="left")
    merged["label"] = merged["label"].fillna(0).astype(int).clip(0, 1)

    required_columns = [
        "ward_id",
        "date",
        "spi_1",
        "spi_3",
        "spi_7",
        "twi_mean",
        "impervious_pct",
        "drain_density",
        "dist_river_km",
        "population_density",
        "flood_freq_10yr",
        "precip_realtime",
        "precip_observed",
        "label",
    ]
    out = merged[required_columns].copy()
    return out


def split_by_year(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if "date" not in df.columns:
        raise ValueError("Input dataframe must contain a 'date' column.")

    split_df = df.copy()
    split_df["year"] = pd.to_datetime(split_df["date"]).dt.year
    train_df = split_df[(split_df["year"] >= 2005) & (split_df["year"] <= 2017)].copy()
    val_df = split_df[(split_df["year"] >= 2018) & (split_df["year"] <= 2020)].copy()
    test_df = split_df[(split_df["year"] >= 2021) & (split_df["year"] <= 2023)].copy()

    return {
        "train": train_df.drop(columns=["year"]),
        "val": val_df.drop(columns=["year"]),
        "test": test_df.drop(columns=["year"]),
    }


def prepare_feature_target(
    split_df: pd.DataFrame,
    feature_columns: list[str] | None = None,
    target_column: str = TARGET_COLUMN,
) -> tuple[pd.DataFrame, pd.Series]:
    feature_cols = feature_columns or FEATURE_COLUMNS
    missing = [col for col in feature_cols + [target_column] if col not in split_df.columns]
    if missing:
        raise ValueError(f"Missing required columns in split dataframe: {missing}")

    X = split_df[feature_cols].copy()
    X = X.fillna(0.0)
    y = split_df[target_column].astype(int)
    return X, y
