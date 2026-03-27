from __future__ import annotations

import json
import logging
import os
import statistics
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from psycopg import connect


BACKOFF_SCHEDULE_SECONDS = (30, 120, 480)


def get_database_dsn() -> str:
    raw = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/vyrus")
    return (
        raw.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def get_db_connection():
    return connect(get_database_dsn())


def log_pipeline_run_start(flow_name: str, reason: str | None = None) -> int:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_runs (flow_name, status, run_at, error_message)
                VALUES (%s, 'RUNNING', NOW(), %s)
                RETURNING id;
                """,
                (flow_name, reason),
            )
            run_id = cur.fetchone()[0]
        conn.commit()
    return run_id


def log_pipeline_run_complete(run_id: int, started_monotonic: float) -> None:
    duration = time.monotonic() - started_monotonic
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runs
                SET status = 'COMPLETE',
                    duration_seconds = %s
                WHERE id = %s;
                """,
                (duration, run_id),
            )
        conn.commit()


def log_pipeline_run_fail(run_id: int, started_monotonic: float, error_message: str) -> None:
    duration = time.monotonic() - started_monotonic
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runs
                SET status = 'FAILED',
                    duration_seconds = %s,
                    error_message = %s
                WHERE id = %s;
                """,
                (duration, error_message[:5000], run_id),
            )
        conn.commit()


def log_pipeline_note(flow_name: str, status: str, message: str) -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pipeline_runs (flow_name, status, run_at, error_message)
                VALUES (%s, %s, NOW(), %s);
                """,
                (flow_name, status, message[:5000]),
            )
        conn.commit()


def mark_source_status(status: str, ward_ids: list[int] | None = None) -> None:
    if status not in {"FRESH", "STALE", "DEGRADED"}:
        raise ValueError(f"Invalid source status: {status}")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if ward_ids:
                cur.execute(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (ward_id) id, computed_at
                        FROM ward_features
                        WHERE ward_id = ANY(%s)
                        ORDER BY ward_id, computed_at DESC
                    )
                    UPDATE ward_features wf
                    SET source_status = %s
                    FROM latest l
                    WHERE wf.id = l.id
                      AND wf.computed_at = l.computed_at;
                    """,
                    (ward_ids, status),
                )
            else:
                cur.execute(
                    """
                    WITH latest AS (
                        SELECT DISTINCT ON (ward_id) id, computed_at
                        FROM ward_features
                        ORDER BY ward_id, computed_at DESC
                    )
                    UPDATE ward_features wf
                    SET source_status = %s
                    FROM latest l
                    WHERE wf.id = l.id
                      AND wf.computed_at = l.computed_at;
                    """,
                    (status,),
                )
        conn.commit()


def mark_source_degraded(ward_ids: list[int] | None = None) -> None:
    mark_source_status("DEGRADED", ward_ids=ward_ids)


def retry_api_call(
    op_name: str,
    request_fn: Callable[[], Any],
    ward_ids: list[int] | None = None,
) -> Any:
    logger = logging.getLogger(__name__)
    attempts = len(BACKOFF_SCHEDULE_SECONDS) + 1
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return request_fn()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < attempts:
                sleep_for = BACKOFF_SCHEDULE_SECONDS[attempt - 1]
                logger.warning(
                    "%s failed (attempt %d/%d): %s. Retrying in %ss.",
                    op_name,
                    attempt,
                    attempts,
                    exc,
                    sleep_for,
                )
                time.sleep(sleep_for)
                continue
            logger.error("%s failed after %d attempts. Marking source as DEGRADED.", op_name, attempts)
            mark_source_degraded(ward_ids=ward_ids)
            raise

    if last_error:
        raise last_error
    raise RuntimeError(f"{op_name} failed for unknown reasons.")


def http_get_json(url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
    def _call() -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    return retry_api_call(f"GET {url}", _call)


def http_get_bytes(url: str, *, params: dict[str, Any] | None = None) -> bytes:
    def _call() -> bytes:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.content

    return retry_api_call(f"GET {url}", _call)


def http_get_text(url: str, *, params: dict[str, Any] | None = None) -> str:
    def _call() -> str:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.text

    return retry_api_call(f"GET {url}", _call)


def http_post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    def _call() -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            if not response.text.strip():
                return {}
            return response.json()

    return retry_api_call(f"POST {url}", _call)


def http_post_form(url: str, form_data: dict[str, Any]) -> dict[str, Any]:
    def _call() -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, data=form_data)
            response.raise_for_status()
            return response.json()

    return retry_api_call(f"POST {url}", _call)


def fetch_last_30_day_precip(ward_id: int) -> list[float]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(precip_observed, precip_realtime, 0.0) AS p
                FROM ward_features
                WHERE ward_id = %s
                  AND computed_at >= NOW() - INTERVAL '30 days'
                ORDER BY computed_at DESC;
                """,
                (ward_id,),
            )
            rows = cur.fetchall()
    return [float(row[0]) for row in rows]


def _spi_for_window(history: list[float], new_precip: float, window: int) -> float | None:
    if len(history) < 7 or len(history) < window:
        return None

    mean = statistics.fmean(history)
    std = statistics.pstdev(history)
    if std == 0:
        return None

    trailing = history[: max(window - 1, 0)]
    p_value = float(new_precip) + float(sum(trailing))
    return (p_value - mean) / std


def compute_spi_values(ward_id: int, new_precip: float) -> tuple[float | None, float | None, float | None]:
    history = fetch_last_30_day_precip(ward_id)
    spi_1 = _spi_for_window(history, new_precip, 1)
    spi_3 = _spi_for_window(history, new_precip, 3)
    spi_7 = _spi_for_window(history, new_precip, 7)
    return spi_1, spi_3, spi_7


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_cached_payload(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Cached payload is not valid JSON.") from exc


def host_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or url
