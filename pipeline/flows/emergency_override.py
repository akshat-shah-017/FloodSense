from __future__ import annotations

import os
import time
from typing import Any

from prefect import flow, get_run_logger, task

from tasks.feature_engineering import (
    http_post_json,
    log_pipeline_note,
    log_pipeline_run_complete,
    log_pipeline_run_fail,
    log_pipeline_run_start,
)
from tasks.openweather_tasks import compute_spi, fetch_openweather_forecast, interpolate_to_wards


@task(name="run_model_inference")
def run_model_inference(reason: str) -> dict[str, Any]:
    base_url = os.getenv("FASTAPI_INTERNAL_URL", "http://fastapi:8000")
    url = f"{base_url.rstrip('/')}/api/v1/internal/predict"
    return http_post_json(url, {"trigger_reason": reason})


@flow(name="emergency_override")
def emergency_override(trigger_reason: str = "manual") -> dict[str, Any]:
    logger = get_run_logger()
    started_monotonic = time.monotonic()
    run_id = log_pipeline_run_start(
        "emergency_override", reason=f"override_trigger_reason={trigger_reason}"
    )

    try:
        # Run forecast_refresh steps 1-3 only to avoid event loops.
        forecast_payload = fetch_openweather_forecast()
        ward_forecast = interpolate_to_wards(forecast_payload)
        spi_df = compute_spi(ward_forecast)
        logger.info("Emergency override refreshed forecast inputs for %d wards.", len(spi_df))

        inference_response = run_model_inference(trigger_reason)
        log_pipeline_note(
            flow_name="emergency_override",
            status="COMPLETE",
            message=f"Triggered by {trigger_reason}; inference response: {inference_response}",
        )
        log_pipeline_run_complete(run_id, started_monotonic)
        return {
            "trigger_reason": trigger_reason,
            "forecast_rows": int(len(spi_df)),
            "inference_response": inference_response,
        }
    except Exception as exc:
        log_pipeline_run_fail(run_id, started_monotonic, str(exc))
        logger.exception("emergency_override failed.")
        raise


if __name__ == "__main__":
    emergency_override()
