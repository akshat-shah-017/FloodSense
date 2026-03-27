from __future__ import annotations

import time

from prefect import flow, get_run_logger

from tasks.feature_engineering import (
    log_pipeline_run_complete,
    log_pipeline_run_fail,
    log_pipeline_run_start,
)
from tasks.openweather_tasks import (
    check_emergency_threshold,
    compute_spi,
    fetch_openweather_forecast,
    interpolate_to_wards,
    update_forecast_features,
)


@flow(name="forecast_refresh")
def forecast_refresh(run_threshold_check: bool = True) -> dict[str, int | bool]:
    logger = get_run_logger()
    started_monotonic = time.monotonic()
    run_id = log_pipeline_run_start("forecast_refresh")

    try:
        forecast_payload = fetch_openweather_forecast()
        ward_forecast = interpolate_to_wards(forecast_payload)
        spi_df = compute_spi(ward_forecast)
        written_rows = update_forecast_features(spi_df)
        threshold_triggered = False
        if run_threshold_check:
            threshold_triggered = check_emergency_threshold(spi_df)

        log_pipeline_run_complete(run_id, started_monotonic)
        logger.info(
            "forecast_refresh completed. rows=%d, threshold_triggered=%s",
            written_rows,
            threshold_triggered,
        )
        return {
            "rows_written": int(written_rows),
            "threshold_triggered": bool(threshold_triggered),
        }
    except Exception as exc:
        log_pipeline_run_fail(run_id, started_monotonic, str(exc))
        logger.exception("forecast_refresh failed.")
        raise


if __name__ == "__main__":
    forecast_refresh()
