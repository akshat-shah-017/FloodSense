from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
from prefect import get_run_logger, task
from shapely.geometry import Point

from tasks.feature_engineering import (
    compute_spi_values,
    get_db_connection,
    http_get_bytes,
    mark_source_degraded,
)
from tasks.r2_storage import upload_file


def _resolve_imd_columns(df: pd.DataFrame) -> tuple[str, str, str]:
    lat_candidates = ["lat", "latitude", "y"]
    lon_candidates = ["lon", "lng", "longitude", "x"]
    rain_candidates = ["rainfall", "rain_mm", "precip", "precip_mm", "value"]

    lat_col = next((c for c in df.columns if c.lower() in lat_candidates), None)
    lon_col = next((c for c in df.columns if c.lower() in lon_candidates), None)
    rain_col = next((c for c in df.columns if c.lower() in rain_candidates), None)

    if not lat_col or not lon_col or not rain_col:
        raise ValueError(
            "IMD CSV must include latitude/longitude/rainfall columns. "
            f"Found columns: {list(df.columns)}"
        )
    return lat_col, lon_col, rain_col


def _load_imd_points(local_path: str) -> gpd.GeoDataFrame:
    path = Path(local_path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        raw_df = pd.read_csv(path)
        lat_col, lon_col, rain_col = _resolve_imd_columns(raw_df)
        df = raw_df[[lat_col, lon_col, rain_col]].copy()
        df.columns = ["lat", "lon", "precip_observed"]
    elif suffix in {".nc", ".netcdf"}:
        try:
            import xarray as xr
        except ImportError as exc:
            raise RuntimeError(
                "xarray is required to parse NetCDF IMD files. Install xarray first."
            ) from exc

        ds = xr.open_dataset(path)
        lat_name = next((c for c in ds.coords if "lat" in c.lower()), None)
        lon_name = next((c for c in ds.coords if "lon" in c.lower()), None)
        if not lat_name or not lon_name:
            raise ValueError("Unable to locate latitude/longitude coordinates in NetCDF.")

        variable_name = None
        for candidate in ds.data_vars:
            dims = set(ds[candidate].dims)
            if lat_name in dims and lon_name in dims:
                variable_name = candidate
                break
        if not variable_name:
            raise ValueError("Unable to locate rainfall variable in NetCDF.")

        arr = ds[variable_name]
        if "time" in arr.dims:
            arr = arr.isel(time=0)
        df = arr.to_dataframe(name="precip_observed").reset_index()
        df = df[[lat_name, lon_name, "precip_observed"]].copy()
        df.columns = ["lat", "lon", "precip_observed"]
    else:
        raise ValueError(f"Unsupported IMD file format: {path.suffix}")

    df["precip_observed"] = pd.to_numeric(df["precip_observed"], errors="coerce").fillna(0.0)
    geometry = [Point(lon, lat) for lat, lon in zip(df["lat"], df["lon"], strict=False)]
    return gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")


@task(name="download_imd_file")
def download_imd_file() -> str:
    logger = get_run_logger()
    imd_url = os.getenv("IMD_DOWNLOAD_URL", "https://imdpune.gov.in/latest_rainfall.nc")
    ext = Path(imd_url).suffix or ".nc"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    local_path = Path("/tmp") / f"imd_{stamp}{ext}"

    payload = http_get_bytes(imd_url)
    local_path.write_bytes(payload)
    logger.info("Downloaded IMD file to %s (%d bytes)", local_path, len(payload))
    return str(local_path)


@task(name="spatial_join_to_wards")
def spatial_join_to_wards(local_file_path: str) -> pd.DataFrame:
    logger = get_run_logger()
    imd_gdf = _load_imd_points(local_file_path)

    with get_db_connection() as conn:
        wards_gdf = gpd.read_postgis(
            "SELECT ward_id, boundary FROM wards",
            conn,
            geom_col="boundary",
        )

    if wards_gdf.empty:
        raise RuntimeError("No ward boundaries found in database.")

    joined = gpd.sjoin(
        imd_gdf,
        wards_gdf[["ward_id", "boundary"]],
        how="inner",
        predicate="within",
    )
    aggregated = (
        joined.groupby("ward_id", as_index=False)["precip_observed"]
        .mean()
        .sort_values("ward_id")
        .reset_index(drop=True)
    )
    logger.info("Spatial join complete. %d ward rows generated.", len(aggregated))
    return aggregated


@task(name="upload_to_r2")
def upload_to_r2(local_file_path: str, r2_key: str) -> str:
    logger = get_run_logger()
    upload_file(local_file_path, r2_key)
    logger.info("Uploaded %s to R2 key %s", local_file_path, r2_key)
    return r2_key


@task(name="update_features_table")
def update_features_table(ward_precip_df: pd.DataFrame) -> int:
    logger = get_run_logger()
    if ward_precip_df.empty:
        logger.warning("No ward precipitation rows to write.")
        return 0

    now_ts = datetime.now(timezone.utc)
    rows: list[tuple] = []
    ward_ids: list[int] = []

    for row in ward_precip_df.itertuples(index=False):
        ward_id = int(row.ward_id)
        precip_observed = float(row.precip_observed)
        spi_1, spi_3, spi_7 = compute_spi_values(ward_id, precip_observed)
        rows.append(
            (
                ward_id,
                now_ts,
                spi_1,
                spi_3,
                spi_7,
                precip_observed,
                "FRESH",
            )
        )
        ward_ids.append(ward_id)

    insert_sql = """
        INSERT INTO ward_features (
            ward_id, computed_at, spi_1, spi_3, spi_7, precip_observed, source_status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s);
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(insert_sql, rows)
            conn.commit()
    except Exception:
        mark_source_degraded(ward_ids=ward_ids)
        raise

    logger.info("Inserted %d ward_features rows for IMD ingestion.", len(rows))
    return len(rows)
