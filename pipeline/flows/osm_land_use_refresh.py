from __future__ import annotations

import time

from prefect import flow, get_run_logger

from tasks.feature_engineering import (
    log_pipeline_run_complete,
    log_pipeline_run_fail,
    log_pipeline_run_start,
)
from tasks.osm_tasks import (
    compute_drain_density,
    compute_impervious_pct,
    fetch_osm_drainage,
    flag_changed_wards,
)


@flow(name="osm_land_use_refresh")
def osm_land_use_refresh() -> dict[str, int]:
    logger = get_run_logger()
    started_monotonic = time.monotonic()
    run_id = log_pipeline_run_start("osm_land_use_refresh")

    try:
        osm_payload = fetch_osm_drainage()
        impervious_df = compute_impervious_pct(osm_payload)
        drain_density_df = compute_drain_density(osm_payload)
        changed = flag_changed_wards(impervious_df, drain_density_df)

        log_pipeline_run_complete(run_id, started_monotonic)
        logger.info("osm_land_use_refresh completed. needs_retrain_count=%d", changed)
        return {"needs_retrain_count": int(changed)}
    except Exception as exc:
        log_pipeline_run_fail(run_id, started_monotonic, str(exc))
        logger.exception("osm_land_use_refresh failed.")
        raise


if __name__ == "__main__":
    osm_land_use_refresh()
