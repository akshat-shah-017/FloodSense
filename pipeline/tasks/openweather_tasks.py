from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import geopandas as gpd
import pandas as pd
from prefect import get_run_logger, task
from prefect.events import emit_event

from tasks.feature_engineering import compute_spi_values, get_db_connection, http_get_json


@task(name="fetch_openweather_forecast")
def fetch_openweather_forecast() -> dict[str, Any]:
    logger = get_run_logger()
    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY is required.")

    lat = float(os.getenv("CITY_LAT", "28.7041"))
    lon = float(os.getenv("CITY_LON", "77.1025"))
    url = os.getenv(
        "OPENWEATHER_FORECAST_URL", "https://api.openweathermap.org/data/2.5/forecast"
    )
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
    }
    payload = http_get_json(url, params=params)

    now_utc = datetime.now(timezone.utc)
    horizon = now_utc + timedelta(hours=24)
    series: list[dict[str, Any]] = []
    for entry in payload.get("list", []):
        dt_utc = datetime.fromtimestamp(int(entry["dt"]), tz=timezone.utc)
        if dt_utc > horizon:
            continue
        precip_3h = float((entry.get("rain") or {}).get("3h", 0.0))
        series.append({"timestamp": dt_utc.isoformat(), "precip_3h_mm": precip_3h})

    if not series:
        raise RuntimeError("OpenWeather forecast payload had no usable points for next 24 hours.")

    max_6hr_mm = 0.0
    for i in range(len(series)):
        current = series[i]["precip_3h_mm"]
        nxt = series[i + 1]["precip_3h_mm"] if i + 1 < len(series) else 0.0
        max_6hr_mm = max(max_6hr_mm, float(current + nxt))

    total_24h_mm = float(sum(item["precip_3h_mm"] for item in series))
    logger.info(
        "OpenWeather forecast parsed (%d points, total_24h=%.2f, max_6hr=%.2f).",
        len(series),
        total_24h_mm,
        max_6hr_mm,
    )
    return {
        "city_lat": lat,
        "city_lon": lon,
        "series": series,
        "total_24h_mm": total_24h_mm,
        "max_6hr_mm": max_6hr_mm,
    }


@task(name="interpolate_to_wards")
def interpolate_to_wards(forecast_payload: dict[str, Any]) -> pd.DataFrame:
    logger = get_run_logger()
    precip_realtime = float(forecast_payload["max_6hr_mm"])

    with get_db_connection() as conn:
        wards_gdf = gpd.read_postgis(
            "SELECT ward_id, centroid FROM wards",
            conn,
            geom_col="centroid",
        )

    if wards_gdf.empty:
        raise RuntimeError("No wards found for OpenWeather interpolation.")

    result_df = pd.DataFrame(
        {
            "ward_id": wards_gdf["ward_id"].astype(int),
            "precip_realtime": precip_realtime,
        }
    )
    logger.info("Assigned city forecast to %d wards.", len(result_df))
    return result_df


@task(name="compute_spi")
def compute_spi(ward_forecast_df: pd.DataFrame) -> pd.DataFrame:
    logger = get_run_logger()
    if ward_forecast_df.empty:
        return ward_forecast_df

    records: list[dict[str, Any]] = []
    for row in ward_forecast_df.itertuples(index=False):
        ward_id = int(row.ward_id)
        precip_realtime = float(row.precip_realtime)
        spi_1, spi_3, spi_7 = compute_spi_values(ward_id, precip_realtime)
        records.append(
            {
                "ward_id": ward_id,
                "precip_realtime": precip_realtime,
                "spi_1": spi_1,
                "spi_3": spi_3,
                "spi_7": spi_7,
            }
        )

    out = pd.DataFrame(records)
    logger.info("SPI computed for %d wards.", len(out))
    return out


@task(name="update_forecast_features")
def update_forecast_features(spi_df: pd.DataFrame) -> int:
    logger = get_run_logger()
    if spi_df.empty:
        logger.warning("No forecast rows to persist.")
        return 0

    now_ts = datetime.now(timezone.utc)
    written = 0

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for row in spi_df.itertuples(index=False):
                ward_id = int(row.ward_id)
                cur.execute(
                    """
                    WITH latest AS (
                        SELECT id, computed_at
                        FROM ward_features
                        WHERE ward_id = %s
                        ORDER BY computed_at DESC
                        LIMIT 1
                    )
                    UPDATE ward_features wf
                    SET spi_1 = %s,
                        spi_3 = %s,
                        spi_7 = %s,
                        precip_realtime = %s,
                        source_status = 'FRESH'
                    FROM latest l
                    WHERE wf.id = l.id
                      AND wf.computed_at = l.computed_at
                    RETURNING wf.id;
                    """,
                    (
                        ward_id,
                        row.spi_1,
                        row.spi_3,
                        row.spi_7,
                        row.precip_realtime,
                    ),
                )
                updated = cur.fetchone()
                if updated:
                    written += 1
                    continue

                cur.execute(
                    """
                    INSERT INTO ward_features (
                        ward_id, computed_at, spi_1, spi_3, spi_7, precip_realtime, source_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'FRESH');
                    """,
                    (
                        ward_id,
                        now_ts,
                        row.spi_1,
                        row.spi_3,
                        row.spi_7,
                        row.precip_realtime,
                    ),
                )
                written += 1
        conn.commit()

    logger.info("Forecast feature rows updated/inserted: %d", written)
    return written


@task(name="check_emergency_threshold")
def check_emergency_threshold(spi_df: pd.DataFrame) -> bool:
    logger = get_run_logger()
    if spi_df.empty:
        return False

    threshold = float(os.getenv("OPENWEATHER_EMERGENCY_MM_6H", "100"))
    triggered = spi_df[spi_df["precip_realtime"] > threshold]
    if triggered.empty:
        logger.info("No emergency threshold breach for OpenWeather.")
        return False

    ward_ids = triggered["ward_id"].astype(int).tolist()
    max_precip = float(triggered["precip_realtime"].max())
    emit_event(
        event="emergency.flood.threshold",
        resource={"prefect.resource.id": "floodsense.forecast_refresh"},
        payload={
            "ward_ids": ward_ids,
            "threshold_mm_6h": threshold,
            "observed_max_mm_6h": max_precip,
        },
    )
    logger.warning(
        "Emergency flood threshold breached by wards=%s (max=%.2fmm/6h).",
        ward_ids,
        max_precip,
    )
    return True
