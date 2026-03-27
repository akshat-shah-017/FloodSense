from __future__ import annotations

import time

from prefect import flow, get_run_logger

from tasks.cwc_tasks import check_danger_threshold, check_freshness, fetch_cwc_gauge
from tasks.feature_engineering import (
    log_pipeline_run_complete,
    log_pipeline_run_fail,
    log_pipeline_run_start,
)


@flow(name="cwc_gauge_refresh")
def cwc_gauge_refresh() -> dict[str, int | bool]:
    logger = get_run_logger()
    started_monotonic = time.monotonic()
    run_id = log_pipeline_run_start("cwc_gauge_refresh")

    try:
        cwc_payload = fetch_cwc_gauge()
        stale = check_freshness(cwc_payload)
        danger = check_danger_threshold(cwc_payload)
        gauge_count = len(cwc_payload.get("gauges", []))

        log_pipeline_run_complete(run_id, started_monotonic)
        logger.info(
            "cwc_gauge_refresh completed. gauges=%d, stale=%s, danger=%s",
            gauge_count,
            stale,
            danger,
        )
        return {"gauges": gauge_count, "stale": bool(stale), "danger": bool(danger)}
    except Exception as exc:
        log_pipeline_run_fail(run_id, started_monotonic, str(exc))
        logger.exception("cwc_gauge_refresh failed.")
        raise


if __name__ == "__main__":
    cwc_gauge_refresh()
