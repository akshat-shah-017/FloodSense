from __future__ import annotations

import time
from datetime import datetime, timezone

from prefect import flow, get_run_logger

from tasks.feature_engineering import (
    log_pipeline_run_complete,
    log_pipeline_run_fail,
    log_pipeline_run_start,
)
from tasks.imd_tasks import (
    download_imd_file,
    spatial_join_to_wards,
    update_features_table,
    upload_to_r2,
)


@flow(name="nightly_imd_ingest")
def nightly_imd_ingest() -> int:
    logger = get_run_logger()
    started_monotonic = time.monotonic()
    run_id = log_pipeline_run_start("nightly_imd_ingest")

    try:
        local_file = download_imd_file()
        utc_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r2_key = f"imd/{utc_day}.nc"
        upload_to_r2(local_file, r2_key)

        ward_precip_df = spatial_join_to_wards(local_file)
        inserted = update_features_table(ward_precip_df)

        log_pipeline_run_complete(run_id, started_monotonic)
        logger.info("nightly_imd_ingest completed with %d rows written.", inserted)
        return int(inserted)
    except Exception as exc:
        log_pipeline_run_fail(run_id, started_monotonic, str(exc))
        logger.exception("nightly_imd_ingest failed.")
        raise


if __name__ == "__main__":
    nightly_imd_ingest()
