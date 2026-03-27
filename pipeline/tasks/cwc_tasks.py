from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from prefect import get_run_logger, task
from prefect.events import emit_event

from tasks.feature_engineering import (
    get_db_connection,
    http_get_text,
    mark_source_status,
    parse_cached_payload,
)


def _to_aware_datetime(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _normalize_gauge_record(item: dict[str, Any]) -> dict[str, Any]:
    level = float(item.get("level") or item.get("level_m") or item.get("gauge_level") or 0.0)
    danger = float(
        item.get("danger_level")
        or item.get("danger_level_m")
        or item.get("danger")
        or item.get("danger_mark")
        or 0.0
    )
    observed_at = (
        item.get("timestamp")
        or item.get("observed_at")
        or item.get("last_updated")
        or datetime.now(timezone.utc).isoformat()
    )
    return {
        "station": str(item.get("station") or item.get("name") or "unknown"),
        "level_m": level,
        "danger_level_m": danger,
        "observed_at": _to_aware_datetime(str(observed_at)).isoformat(),
        "ward_ids": item.get("ward_ids") or [],
    }


def _parse_cwc_text(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise ValueError("CWC response was empty.")

    if raw.startswith("{") or raw.startswith("["):
        payload = json.loads(raw)
        if isinstance(payload, dict):
            gauges = payload.get("gauges") or payload.get("data") or []
        else:
            gauges = payload
        normalized = [_normalize_gauge_record(item) for item in gauges if isinstance(item, dict)]
        return {
            "source": "cwc",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "gauges": normalized,
        }

    # HTML fallback parser: tries to extract simple rows with station + level + danger
    rows = re.findall(
        r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    )
    gauges: list[dict[str, Any]] = []
    for station, level_raw, danger_raw in rows:
        station_clean = re.sub(r"<[^>]+>", "", station).strip()
        level_clean = re.sub(r"[^0-9.\-]", "", re.sub(r"<[^>]+>", "", level_raw))
        danger_clean = re.sub(r"[^0-9.\-]", "", re.sub(r"<[^>]+>", "", danger_raw))
        if not station_clean or not level_clean:
            continue
        gauges.append(
            {
                "station": station_clean,
                "level_m": float(level_clean),
                "danger_level_m": float(danger_clean or 0.0),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "ward_ids": [],
            }
        )

    if not gauges:
        raise ValueError("Could not parse CWC response as JSON or HTML table rows.")

    return {
        "source": "cwc",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "gauges": gauges,
    }


@task(name="fetch_cwc_gauge")
def fetch_cwc_gauge() -> dict[str, Any]:
    logger = get_run_logger()
    cwc_url = os.getenv("CWC_FFWS_URL", "https://ffs.india-water.gov.in")

    try:
        raw = http_get_text(cwc_url)
        payload = _parse_cwc_text(raw)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_runs (flow_name, status, run_at, error_message)
                    VALUES ('cwc_gauge_cache', 'COMPLETE', NOW(), %s);
                    """,
                    (json.dumps(payload),),
                )
            conn.commit()
        logger.info("Fetched CWC gauges successfully (%d readings).", len(payload["gauges"]))
        return payload
    except Exception as exc:
        logger.warning("CWC fetch failed after retries: %s. Loading last cached reading.", exc)
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT error_message
                    FROM pipeline_runs
                    WHERE flow_name = 'cwc_gauge_cache'
                      AND status = 'COMPLETE'
                      AND error_message IS NOT NULL
                    ORDER BY run_at DESC
                    LIMIT 1;
                    """
                )
                row = cur.fetchone()
        if not row or not row[0]:
            raise RuntimeError("CWC fetch failed and no cached reading exists in DB.") from exc
        cached = parse_cached_payload(row[0])
        logger.info("Using cached CWC reading from DB.")
        return cached


@task(name="check_freshness")
def check_freshness(cwc_payload: dict[str, Any]) -> bool:
    logger = get_run_logger()
    gauges = cwc_payload.get("gauges") or []
    if not gauges:
        mark_source_status("STALE")
        logger.warning("No gauges available; marked source as STALE.")
        return True

    latest_observed = max(
        _to_aware_datetime(item.get("observed_at")) for item in gauges if isinstance(item, dict)
    )
    stale_threshold = datetime.now(timezone.utc) - timedelta(hours=2)
    if latest_observed >= stale_threshold:
        logger.info("CWC source is fresh (latest=%s).", latest_observed.isoformat())
        return False

    ward_ids: list[int] = []
    for gauge in gauges:
        ward_ids.extend([int(x) for x in gauge.get("ward_ids", []) if str(x).isdigit()])
    mark_source_status("STALE", ward_ids=ward_ids or None)
    logger.warning("CWC source is stale; marked ward_features source_status='STALE'.")
    return True


@task(name="check_danger_threshold")
def check_danger_threshold(cwc_payload: dict[str, Any]) -> bool:
    logger = get_run_logger()
    triggered: list[dict[str, Any]] = []
    for gauge in cwc_payload.get("gauges", []):
        level = float(gauge.get("level_m") or 0.0)
        danger = float(gauge.get("danger_level_m") or 0.0)
        if danger > 0 and level > 0.8 * danger:
            triggered.append(gauge)

    if not triggered:
        logger.info("No CWC gauge crossed 80%% danger threshold.")
        return False

    emit_event(
        event="emergency.cwc.danger",
        resource={"prefect.resource.id": "floodsense.cwc_gauge_refresh"},
        payload={"gauges": triggered, "rule": "level > 80% of danger"},
    )
    logger.warning("CWC danger threshold triggered by %d gauge(s).", len(triggered))
    return True
