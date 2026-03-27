import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.connection import get_db

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


def _fetch_openweather_forecast(
    api_key: str,
    lat: float,
    lon: float,
    forecast_url: str,
) -> dict[str, Any]:
    response = requests.get(
        forecast_url,
        params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
        timeout=12,
    )
    response.raise_for_status()
    return response.json()


def _summarize_forecast(payload: dict[str, Any]) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    horizon = now_utc + timedelta(hours=24)

    series: list[dict[str, Any]] = []
    for entry in payload.get("list", []):
        dt_utc = datetime.fromtimestamp(int(entry.get("dt", 0)), tz=timezone.utc)
        if dt_utc > horizon:
            continue
        precip_3h = float((entry.get("rain") or {}).get("3h", 0.0))
        series.append({"timestamp": dt_utc.isoformat(), "precip_3h_mm": precip_3h})

    if not series:
        return {
            "series_points": 0,
            "total_24h_mm": 0.0,
            "max_6hr_mm": 0.0,
            "next_3hr_mm": 0.0,
        }

    max_6hr_mm = 0.0
    for index, item in enumerate(series):
        current = float(item["precip_3h_mm"])
        nxt = float(series[index + 1]["precip_3h_mm"]) if index + 1 < len(series) else 0.0
        max_6hr_mm = max(max_6hr_mm, current + nxt)

    return {
        "series_points": len(series),
        "total_24h_mm": float(sum(item["precip_3h_mm"] for item in series)),
        "max_6hr_mm": float(max_6hr_mm),
        "next_3hr_mm": float(series[0]["precip_3h_mm"]),
    }


@router.get("/openweather")
async def get_openweather_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    city_lat = float(os.getenv("CITY_LAT", "28.7041"))
    city_lon = float(os.getenv("CITY_LON", "77.1025"))
    forecast_url = os.getenv(
        "OPENWEATHER_FORECAST_URL", "https://api.openweathermap.org/data/2.5/forecast"
    )

    latest_features_query = text(
        """
        WITH latest AS (
            SELECT DISTINCT ON (ward_id)
                ward_id,
                computed_at,
                precip_realtime
            FROM ward_features
            ORDER BY ward_id, computed_at DESC
        )
        SELECT
            MAX(computed_at) AS latest_feature_at,
            AVG(precip_realtime) AS avg_precip_realtime,
            MAX(precip_realtime) AS max_precip_realtime,
            COUNT(*) AS ward_count
        FROM latest
        """
    )
    latest_features_result = await db.execute(latest_features_query)
    latest_features = latest_features_result.mappings().first()

    snapshot: dict[str, Any] = {
        "configured": bool(api_key),
        "integration": "openweather_forecast",
        "city": {"lat": city_lat, "lon": city_lon},
        "latest_feature_at": (
            latest_features["latest_feature_at"].isoformat()
            if latest_features and latest_features["latest_feature_at"] is not None
            else None
        ),
        "avg_precip_realtime": (
            float(latest_features["avg_precip_realtime"])
            if latest_features and latest_features["avg_precip_realtime"] is not None
            else None
        ),
        "max_precip_realtime": (
            float(latest_features["max_precip_realtime"])
            if latest_features and latest_features["max_precip_realtime"] is not None
            else None
        ),
        "ward_count": int(latest_features["ward_count"]) if latest_features else 0,
    }

    if not api_key:
        snapshot["status"] = "not_configured"
        return snapshot

    try:
        payload = await run_in_threadpool(
            _fetch_openweather_forecast,
            api_key,
            city_lat,
            city_lon,
            forecast_url,
        )
        forecast_summary = _summarize_forecast(payload)
        snapshot.update(
            {
                "status": "live",
                "forecast": forecast_summary,
                "provider_city": payload.get("city", {}).get("name"),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    except Exception as exc:
        snapshot.update(
            {
                "status": "error",
                "error": str(exc)[:250],
            }
        )

    return snapshot

