#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from psycopg import connect
from scipy.stats import norm, rankdata

try:
    from tqdm import tqdm
except Exception:  # noqa: BLE001
    tqdm = None


MONSOON_MONTHS = {6, 7, 8, 9}


def _database_dsn() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/vyrus")
    return (
        raw.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def _normalize_token(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def _find_column(columns: Iterable[object], candidates: list[str]) -> str | None:
    lookup = {_normalize_token(col): str(col) for col in columns}
    for candidate in candidates:
        key = _normalize_token(candidate)
        if key in lookup:
            return lookup[key]
    return None


def _extract_year_from_filename(path: Path) -> int | None:
    match = re.search(r"(19|20)\d{2}", path.name)
    if match:
        return int(match.group(0))
    return None


class ProgressReporter:
    def __init__(self, total: int, desc: str) -> None:
        self.total = max(int(total), 1)
        self.desc = desc
        self.done = 0
        self.next_percent = 10
        self._bar = None
        if tqdm is not None:
            self._bar = tqdm(total=self.total, desc=desc, unit="step")
        else:
            print(f"{desc}: 0% complete")

    def update(self, n: int = 1) -> None:
        self.done += int(n)
        if self._bar is not None:
            self._bar.update(n)
            return

        percent = int((self.done / self.total) * 100)
        while percent >= self.next_percent and self.next_percent <= 100:
            print(f"{self.desc}: {self.next_percent}% complete")
            self.next_percent += 10

    def close(self) -> None:
        if self._bar is not None:
            self._bar.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare ward-daily flood training labels from IMD NetCDF + IFI impacts data."
    )
    parser.add_argument(
        "--imd-dir",
        required=True,
        help="Path to directory containing IMD NetCDF files.",
    )
    parser.add_argument(
        "--labels-csv",
        required=True,
        help="Path to IFI-Impacts flood labels CSV.",
    )
    parser.add_argument(
        "--ward-geojson",
        required=True,
        help="Path to Delhi ward boundaries GeoJSON.",
    )
    parser.add_argument(
        "--output",
        default="data/indofloods_labels.csv",
        help="Output path for generated labels CSV.",
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="If set, insert computed ward-daily features into PostGIS ward_features.",
    )
    parser.add_argument(
        "--city-id",
        default="delhi",
        help="City ID to use in PostGIS lookups/inserts.",
    )
    return parser.parse_args()


def _assign_surrogate_ids(wards: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    wards = wards.copy()
    numeric_ward_numbers = pd.to_numeric(wards["ward_number"], errors="coerce")
    if numeric_ward_numbers.notna().all() and not numeric_ward_numbers.astype(int).duplicated().any():
        wards["ward_id"] = numeric_ward_numbers.astype(int)
    else:
        wards["ward_id"] = np.arange(1, len(wards) + 1, dtype=int)
    return wards


def _fill_missing_ward_ids(wards: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    wards = wards.copy()
    existing = (
        pd.to_numeric(wards["ward_id"], errors="coerce")
        .dropna()
        .astype(int)
        .tolist()
    )
    next_id = (max(existing) + 1) if existing else 1
    for idx in wards.index[wards["ward_id"].isna()]:
        wards.at[idx, "ward_id"] = next_id
        next_id += 1
    return wards


def _map_ward_ids_from_db(
    wards: gpd.GeoDataFrame,
    city_id: str,
    required: bool,
) -> gpd.GeoDataFrame:
    wards = wards.copy()
    wards["name_key"] = wards["ward_name"].map(_normalize_token)
    wards["number_key"] = wards["ward_number"].map(_normalize_token)

    try:
        with connect(_database_dsn()) as conn:
            db_wards = pd.read_sql_query(
                """
                SELECT ward_id, ward_name, ward_number
                FROM wards
                WHERE city_id = %s
                ORDER BY ward_id;
                """,
                conn,
                params=[city_id],
            )
    except Exception as exc:  # noqa: BLE001
        if required:
            raise RuntimeError(
                f"Unable to load ward IDs from PostGIS for city_id='{city_id}': {exc}"
            ) from exc
        print(
            f"Warning: unable to load ward IDs from PostGIS ({exc}). "
            "Falling back to surrogate ward IDs."
        )
        return _assign_surrogate_ids(wards)

    if db_wards.empty:
        message = f"No wards found in PostGIS for city_id='{city_id}'."
        if required:
            raise RuntimeError(message)
        print(f"Warning: {message} Falling back to surrogate ward IDs.")
        return _assign_surrogate_ids(wards)

    db_wards["name_key"] = db_wards["ward_name"].map(_normalize_token)
    db_wards["number_key"] = db_wards["ward_number"].map(_normalize_token)

    name_map = (
        db_wards.loc[db_wards["name_key"] != ""]
        .drop_duplicates(subset=["name_key"])
        .set_index("name_key")["ward_id"]
        .to_dict()
    )
    number_map = (
        db_wards.loc[db_wards["number_key"] != ""]
        .drop_duplicates(subset=["number_key"])
        .set_index("number_key")["ward_id"]
        .to_dict()
    )

    wards["ward_id"] = wards["name_key"].map(name_map)
    missing_mask = wards["ward_id"].isna()
    wards.loc[missing_mask, "ward_id"] = wards.loc[missing_mask, "number_key"].map(number_map)

    missing_count = int(wards["ward_id"].isna().sum())
    if missing_count:
        sample = wards.loc[wards["ward_id"].isna(), "ward_name"].head(5).tolist()
        if required:
            raise RuntimeError(
                f"Failed to map {missing_count} ward IDs from PostGIS. "
                f"Sample unmatched wards: {sample}"
            )
        print(
            f"Warning: failed to map {missing_count} ward IDs from PostGIS. "
            "Filling missing values with surrogate IDs."
        )
        wards = _fill_missing_ward_ids(wards)

    wards["ward_id"] = pd.to_numeric(wards["ward_id"], errors="coerce")
    if wards["ward_id"].isna().any():
        if required:
            raise RuntimeError("Ward ID mapping produced non-numeric ward_id values.")
        print("Warning: non-numeric ward IDs detected; replacing with surrogate IDs.")
        wards = _assign_surrogate_ids(wards)
    else:
        wards["ward_id"] = wards["ward_id"].astype(int)

    if wards["ward_id"].duplicated().any():
        duplicate_count = int(wards["ward_id"].duplicated().sum())
        print(
            f"Warning: detected {duplicate_count} duplicate ward_id geometries after mapping. "
            "Keeping first geometry per ward_id."
        )
        wards = wards.sort_values("ward_id").drop_duplicates(subset=["ward_id"], keep="first")

    return wards


def load_ward_boundaries(path: Path, city_id: str, require_db_ids: bool) -> gpd.GeoDataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Ward GeoJSON not found: {path}")

    wards = gpd.read_file(path)
    if wards.empty:
        raise ValueError(f"No ward features found in GeoJSON: {path}")

    expected_ward_count = int(os.getenv("WARD_TARGET_COUNT", "250"))
    if len(wards) != expected_ward_count:
        print(
            f"Warning: expected {expected_ward_count} ward features, found {len(wards)} in '{path}'."
        )

    if wards.crs is None:
        wards = wards.set_crs("EPSG:4326")
    elif str(wards.crs).upper() != "EPSG:4326":
        wards = wards.to_crs("EPSG:4326")

    name_col = _find_column(wards.columns, ["ward_name", "name", "ward"])
    number_col = _find_column(
        wards.columns,
        ["ward_number", "ward_no", "ward_num", "wardno", "ward_code", "wardid"],
    )

    if not name_col:
        raise ValueError("Unable to find ward name column in GeoJSON.")

    wards = wards.copy()
    wards["ward_name"] = wards[name_col].fillna("").astype(str).str.strip()
    if number_col:
        wards["ward_number"] = wards[number_col].fillna("").astype(str).str.strip()
    else:
        wards["ward_number"] = ""

    wards = wards.loc[wards["ward_name"] != ""].copy()
    wards = wards.loc[wards.geometry.notna() & (~wards.geometry.is_empty)].copy()
    if len(wards) > expected_ward_count:
        print(
            f"Info: limiting wards to first {expected_ward_count} geometries "
            f"for city_id='{city_id}'."
        )
        wards = wards.iloc[:expected_ward_count].copy()

    wards = _map_ward_ids_from_db(wards, city_id=city_id, required=require_db_ids)

    columns = ["ward_id", "ward_name", "ward_number", "geometry"]
    wards = wards[columns].copy()
    wards = wards.sort_values("ward_id").reset_index(drop=True)

    print(
        f"Loaded {len(wards)} ward geometries with {wards['ward_id'].nunique()} unique ward IDs."
    )
    return wards


def _find_lat_lon_names(ds: xr.Dataset) -> tuple[str, str]:
    coord_names = list(ds.coords) + list(ds.dims)
    lat_name = _find_column(coord_names, ["lat", "latitude", "y"])
    lon_name = _find_column(coord_names, ["lon", "longitude", "lng", "x"])

    if not lat_name:
        lat_name = next((name for name in coord_names if "lat" in str(name).lower()), None)
    if not lon_name:
        lon_name = next((name for name in coord_names if "lon" in str(name).lower()), None)

    if not lat_name or not lon_name:
        raise ValueError(
            "Could not infer latitude/longitude coordinate names from dataset "
            f"(coords/dims={coord_names})."
        )
    return lat_name, lon_name


def _select_rainfall_var(ds: xr.Dataset, lat_name: str, lon_name: str) -> str:
    preferred = _find_column(ds.data_vars, ["rf", "RAINFALL", "rainfall", "precip", "precipitation"])
    if preferred:
        return preferred

    for var_name in ds.data_vars:
        dims = set(ds[var_name].dims)
        if lat_name in dims and lon_name in dims:
            return var_name

    raise ValueError(f"No rainfall variable found in dataset. Variables={list(ds.data_vars)}")


def _find_time_dim(data: xr.DataArray) -> str | None:
    for dim in data.dims:
        if "time" in dim.lower():
            return dim
    return None


def _resolve_time_values(data: xr.DataArray, time_dim: str, file_path: Path) -> list[date]:
    n_steps = int(data.sizes.get(time_dim, 0))
    parsed = (
        pd.to_datetime(data[time_dim].values, errors="coerce", utc=True).to_series().reset_index(drop=True)
        if time_dim in data.coords
        else pd.Series([pd.NaT] * n_steps)
    )
    year_hint = _extract_year_from_filename(file_path)

    out: list[date] = []
    for i in range(n_steps):
        ts = parsed.iloc[i] if i < len(parsed) else pd.NaT
        if pd.isna(ts):
            fallback_year = year_hint if year_hint is not None else 1970
            out.append((datetime(fallback_year, 1, 1) + timedelta(days=i)).date())
        else:
            out.append(pd.Timestamp(ts).date())
    return out


def _build_point_mapping(
    lat_values: np.ndarray,
    lon_values: np.ndarray,
    wards: gpd.GeoDataFrame,
) -> pd.DataFrame:
    if lat_values.ndim == 1 and lon_values.ndim == 1:
        lat_grid, lon_grid = np.meshgrid(lat_values, lon_values, indexing="ij")
    elif lat_values.ndim == 2 and lon_values.ndim == 2 and lat_values.shape == lon_values.shape:
        lat_grid, lon_grid = lat_values, lon_values
    else:
        raise ValueError(
            "Unsupported latitude/longitude shape. Expected 1D lat/lon or matching 2D arrays, "
            f"got lat={lat_values.shape}, lon={lon_values.shape}"
        )

    points = gpd.GeoDataFrame(
        {"point_index": np.arange(lat_grid.size, dtype=np.int64)},
        geometry=gpd.points_from_xy(lon_grid.reshape(-1), lat_grid.reshape(-1)),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, wards[["ward_id", "geometry"]], how="inner", predicate="within")
    if joined.empty:
        raise ValueError("Spatial join returned 0 IMD grid points within ward boundaries.")

    mapping = (
        joined[["point_index", "ward_id"]]
        .drop_duplicates(subset=["point_index"])
        .reset_index(drop=True)
    )
    return mapping


def _count_total_timesteps(nc_paths: list[Path]) -> int:
    total = 0
    for path in nc_paths:
        with xr.open_dataset(path) as ds:
            lat_name, lon_name = _find_lat_lon_names(ds)
            rain_var = _select_rainfall_var(ds, lat_name=lat_name, lon_name=lon_name)
            data = ds[rain_var]
            time_dim = _find_time_dim(data)
            total += int(data.sizes.get(time_dim, 1)) if time_dim else 1
    return total


def process_imd_files(imd_dir: Path, wards: gpd.GeoDataFrame) -> pd.DataFrame:
    if not imd_dir.exists() or not imd_dir.is_dir():
        raise FileNotFoundError(f"IMD directory not found: {imd_dir}")

    nc_paths = sorted(
        [
            *imd_dir.glob("*.nc"),
            *imd_dir.glob("*.NC"),
            *imd_dir.glob("*.netcdf"),
            *imd_dir.glob("*.NETCDF"),
        ]
    )
    if not nc_paths:
        raise FileNotFoundError(f"No NetCDF files found in directory: {imd_dir}")

    total_steps = _count_total_timesteps(nc_paths)
    progress = ProgressReporter(total=total_steps, desc="Processing IMD")

    ward_index = pd.DataFrame({"ward_id": sorted(wards["ward_id"].unique())})
    frames: list[pd.DataFrame] = []

    try:
        for nc_path in nc_paths:
            with xr.open_dataset(nc_path) as ds:
                lat_name, lon_name = _find_lat_lon_names(ds)
                rain_var = _select_rainfall_var(ds, lat_name=lat_name, lon_name=lon_name)
                data = ds[rain_var]
                time_dim = _find_time_dim(data)

                if time_dim is None:
                    data = data.expand_dims(time=[0])
                    time_dim = "time"

                if lat_name not in data.dims or lon_name not in data.dims:
                    raise ValueError(
                        f"Rainfall variable '{rain_var}' in {nc_path.name} does not include "
                        f"lat/lon dims ({lat_name}, {lon_name})."
                    )

                data = data.transpose(time_dim, lat_name, lon_name)
                time_values = _resolve_time_values(data, time_dim=time_dim, file_path=nc_path)
                mapping = _build_point_mapping(
                    np.asarray(ds[lat_name].values),
                    np.asarray(ds[lon_name].values),
                    wards,
                )
                point_idx = mapping["point_index"].to_numpy(dtype=np.int64)
                ward_ids = mapping["ward_id"].to_numpy(dtype=np.int64)

                for i in range(int(data.sizes[time_dim])):
                    precip_grid = np.asarray(data.isel({time_dim: i}).values, dtype=float).reshape(-1)
                    mapped_precip = precip_grid[point_idx]

                    daily = pd.DataFrame(
                        {
                            "ward_id": ward_ids,
                            "precip_observed_mm": mapped_precip,
                        }
                    )
                    daily["precip_observed_mm"] = (
                        pd.to_numeric(daily["precip_observed_mm"], errors="coerce")
                        .replace([np.inf, -np.inf], np.nan)
                        .fillna(0.0)
                    )
                    agg = daily.groupby("ward_id", as_index=False)["precip_observed_mm"].mean()
                    agg = ward_index.merge(agg, on="ward_id", how="left")
                    agg["precip_observed_mm"] = agg["precip_observed_mm"].fillna(0.0)
                    agg["date"] = time_values[i]
                    frames.append(agg[["ward_id", "date", "precip_observed_mm"]])

                    progress.update(1)
    finally:
        progress.close()

    if not frames:
        return pd.DataFrame(columns=["ward_id", "date", "precip_observed_mm"])

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.date
    out["precip_observed_mm"] = (
        pd.to_numeric(out["precip_observed_mm"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    out = out.dropna(subset=["date"])
    out = out.sort_values(["ward_id", "date"]).reset_index(drop=True)

    n_records = len(out)
    n_wards = int(out["ward_id"].nunique()) if not out.empty else 0
    n_years = int(pd.to_datetime(out["date"]).dt.year.nunique()) if not out.empty else 0
    print(f"Loaded {n_records} IMD records for {n_wards} wards across {n_years} years.")

    return out


def compute_spi_features(ward_daily_df: pd.DataFrame) -> pd.DataFrame:
    if ward_daily_df.empty:
        empty = ward_daily_df.copy()
        empty["spi_1"] = 0.0
        empty["spi_3"] = 0.0
        empty["spi_7"] = 0.0
        return empty

    out_frames: list[pd.DataFrame] = []

    for ward_id, group in ward_daily_df.groupby("ward_id", sort=False):
        ward_group = group.sort_values("date").copy()
        precip = (
            pd.to_numeric(ward_group["precip_observed_mm"], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .to_numpy(dtype=float)
        )

        n = len(precip)
        if n == 0:
            spi_1 = np.array([], dtype=float)
            spi_3 = np.array([], dtype=float)
            spi_7 = np.array([], dtype=float)
        else:
            mean_p = float(np.mean(precip))
            std_p = float(np.std(precip, ddof=0))
            if std_p <= 0:
                spi_1 = np.zeros(n, dtype=float)
            else:
                z_scores = (precip - mean_p) / std_p
                probs = rankdata(z_scores, method="average") / (n + 1.0)
                spi_1 = norm.ppf(probs)
                spi_1 = np.nan_to_num(spi_1, nan=0.0, posinf=0.0, neginf=0.0)

            spi_3 = (
                pd.Series(spi_1)
                .rolling(window=3, min_periods=3)
                .mean()
                .fillna(0.0)
                .to_numpy(dtype=float)
            )
            spi_7 = (
                pd.Series(spi_1)
                .rolling(window=7, min_periods=7)
                .mean()
                .fillna(0.0)
                .to_numpy(dtype=float)
            )

        ward_group["spi_1"] = spi_1
        ward_group["spi_3"] = spi_3
        ward_group["spi_7"] = spi_7
        out_frames.append(ward_group)

    out = pd.concat(out_frames, ignore_index=True)
    out["spi_1"] = pd.to_numeric(out["spi_1"], errors="coerce").fillna(0.0)
    out["spi_3"] = pd.to_numeric(out["spi_3"], errors="coerce").fillna(0.0)
    out["spi_7"] = pd.to_numeric(out["spi_7"], errors="coerce").fillna(0.0)
    out = out.sort_values(["ward_id", "date"]).reset_index(drop=True)
    return out


def _extract_years(series: pd.Series) -> pd.Series:
    numeric_years = pd.to_numeric(series, errors="coerce")
    numeric_years = numeric_years.where((numeric_years >= 1900) & (numeric_years <= 2100))
    if int(numeric_years.notna().sum()) > 0:
        return numeric_years.astype("Int64")

    parsed_dates = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return parsed_dates.dt.year.astype("Int64")


def _extract_delhi_flood_years(labels_df: pd.DataFrame) -> set[int]:
    state_col = _find_column(labels_df.columns, ["state", "state_name", "statecode", "states"])
    if state_col is None:
        state_col = next((str(c) for c in labels_df.columns if "state" in str(c).lower()), None)
    if state_col is None:
        raise ValueError("Could not find a 'state' column in labels CSV.")

    delhi_mask = labels_df[state_col].astype(str).map(_normalize_token).str.contains("delhi", na=False)
    delhi_rows = labels_df.loc[delhi_mask].copy()
    if delhi_rows.empty:
        return set()

    year_col = _find_column(delhi_rows.columns, ["year", "flood_year", "event_year"])
    year_series: pd.Series
    if year_col is not None:
        year_series = _extract_years(delhi_rows[year_col])
    else:
        date_col = _find_column(
            delhi_rows.columns,
            [
                "start_date",
                "start date",
                "date",
                "event_date",
                "flood_date",
                "from_date",
            ],
        )
        if date_col is None:
            raise ValueError(
                "Could not infer year from labels CSV (no year/date column available)."
            )
        year_series = _extract_years(delhi_rows[date_col])

    years = {int(y) for y in year_series.dropna().astype(int).tolist()}
    return years


def build_labels(
    ward_daily_df: pd.DataFrame,
    labels_csv_path: Path,
) -> pd.DataFrame:
    if not labels_csv_path.exists():
        raise FileNotFoundError(f"Labels CSV not found: {labels_csv_path}")

    labels_raw = pd.read_csv(labels_csv_path, low_memory=False)
    delhi_flood_years = _extract_delhi_flood_years(labels_raw)

    if not delhi_flood_years:
        print("Warning: no Delhi flood years found in labels CSV. Labels will be all 0.")

    working = ward_daily_df[["ward_id", "date", "precip_observed_mm"]].copy()
    working["date"] = pd.to_datetime(working["date"], errors="coerce")
    working["precip_observed_mm"] = (
        pd.to_numeric(working["precip_observed_mm"], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    ward_thresholds = (
        working.groupby("ward_id")["precip_observed_mm"]
        .quantile(0.75)
        .rename("ward_p75")
    )
    working = working.join(ward_thresholds, on="ward_id")

    in_flood_year = working["date"].dt.year.isin(delhi_flood_years)
    in_monsoon = working["date"].dt.month.isin(MONSOON_MONTHS)
    high_precip = working["precip_observed_mm"] > working["ward_p75"]

    working["label"] = (in_flood_year & in_monsoon & high_precip).astype(int)
    labels_df = working[["ward_id", "date", "label"]].copy()
    labels_df["date"] = labels_df["date"].dt.date
    labels_df["label"] = labels_df["label"].fillna(0).astype(int).clip(0, 1)

    flood_count = int(labels_df["label"].sum())
    total = len(labels_df)
    non_flood_count = total - flood_count
    flood_pct = (100.0 * flood_count / total) if total else 0.0
    print(f"Flood events: {flood_count} ({flood_pct:.1f}%), Non-flood: {non_flood_count}")
    if total and (flood_pct < 3.0 or flood_pct > 8.0):
        print(
            "Warning: flood event ratio is outside target range 3-8%. "
            "Consider adjusting the threshold heuristic."
        )

    return labels_df


def write_labels_csv(
    feature_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    output_path: Path,
) -> pd.DataFrame:
    merged = feature_df[["ward_id", "date"]].merge(
        labels_df,
        on=["ward_id", "date"],
        how="left",
    )
    merged["label"] = merged["label"].fillna(0).astype(int).clip(0, 1)
    merged = merged.sort_values(["ward_id", "date"]).reset_index(drop=True)
    merged["date"] = pd.to_datetime(merged["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    merged = merged.dropna(subset=["date"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False, columns=["ward_id", "date", "label"])
    print(f"Written {len(merged)} rows to {output_path}")
    return merged


def seed_ward_features(feature_df: pd.DataFrame) -> None:
    insert_sql = """
    INSERT INTO ward_features (
        ward_id,
        computed_at,
        spi_1,
        spi_3,
        spi_7,
        precip_observed,
        precip_realtime,
        source_status
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """

    total_rows = len(feature_df)
    inserted = 0
    next_progress_log = 50_000
    batch: list[tuple] = []

    with connect(_database_dsn()) as conn:
        with conn.cursor() as cur:
            for row in feature_df.itertuples(index=False):
                ts = pd.to_datetime(row.date, errors="coerce")
                if pd.isna(ts):
                    continue

                computed_at = datetime(
                    ts.year,
                    ts.month,
                    ts.day,
                    12,
                    0,
                    tzinfo=timezone.utc,
                )

                precip = float(getattr(row, "precip_observed_mm", 0.0) or 0.0)
                spi_1 = float(getattr(row, "spi_1", 0.0) or 0.0)
                spi_3 = float(getattr(row, "spi_3", 0.0) or 0.0)
                spi_7 = float(getattr(row, "spi_7", 0.0) or 0.0)

                batch.append(
                    (
                        int(row.ward_id),
                        computed_at,
                        spi_1,
                        spi_3,
                        spi_7,
                        precip,
                        precip,  # placeholder until realtime stream is wired
                        "FRESH",
                    )
                )

                if len(batch) >= 5000:
                    cur.executemany(insert_sql, batch)
                    conn.commit()
                    inserted += len(batch)
                    batch.clear()

                    while inserted >= next_progress_log:
                        print(f"Inserted {inserted}/{total_rows} rows into ward_features...")
                        next_progress_log += 50_000

            if batch:
                cur.executemany(insert_sql, batch)
                conn.commit()
                inserted += len(batch)
                while inserted >= next_progress_log:
                    print(f"Inserted {inserted}/{total_rows} rows into ward_features...")
                    next_progress_log += 50_000

    print(f"Inserted {inserted} rows into ward_features.")


def main() -> int:
    args = parse_args()

    wards = load_ward_boundaries(
        path=Path(args.ward_geojson),
        city_id=args.city_id,
        require_db_ids=args.seed_db,
    )

    ward_daily = process_imd_files(Path(args.imd_dir), wards)
    if ward_daily.empty:
        raise RuntimeError("No ward-daily IMD records were produced.")

    ward_daily = compute_spi_features(ward_daily)
    labels = build_labels(ward_daily, Path(args.labels_csv))
    write_labels_csv(ward_daily, labels, Path(args.output))

    if args.seed_db:
        seed_ward_features(ward_daily)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
