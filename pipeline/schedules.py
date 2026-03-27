from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class DeploymentSpec:
    flow_entrypoint: str
    deployment_name: str
    cron: str
    timezone: str = "UTC"

    def to_prefect_deploy_command(self, work_pool: str) -> list[str]:
        return [
            "prefect",
            "deploy",
            self.flow_entrypoint,
            "--name",
            self.deployment_name,
            "--cron",
            self.cron,
            "--timezone",
            self.timezone,
            "--pool",
            work_pool,
            "--apply",
        ]


DEPLOYMENTS = [
    DeploymentSpec(
        flow_entrypoint="flows/nightly_imd_ingest.py:nightly_imd_ingest",
        deployment_name="nightly-imd-ingest",
        cron="20 20 * * *",  # 02:00 IST daily
        timezone="UTC",
    ),
    DeploymentSpec(
        flow_entrypoint="flows/forecast_refresh.py:forecast_refresh",
        deployment_name="forecast-refresh-every-3h",
        cron="0 */3 * * *",
        timezone="UTC",
    ),
    DeploymentSpec(
        flow_entrypoint="flows/cwc_gauge_refresh.py:cwc_gauge_refresh",
        deployment_name="cwc-gauge-refresh-hourly",
        cron="0 * * * *",
        timezone="UTC",
    ),
    DeploymentSpec(
        flow_entrypoint="flows/osm_land_use_refresh.py:osm_land_use_refresh",
        deployment_name="osm-land-use-refresh-weekly",
        cron="0 3 * * 0",
        timezone="UTC",
    ),
]


def print_deploy_commands(work_pool: str) -> None:
    for spec in DEPLOYMENTS:
        cmd = spec.to_prefect_deploy_command(work_pool)
        print(shlex.join(cmd))


def deploy_all(work_pool: str) -> None:
    for spec in DEPLOYMENTS:
        cmd = spec.to_prefect_deploy_command(work_pool)
        print(f"Deploying {spec.deployment_name} with cron '{spec.cron}' ...")
        subprocess.run(cmd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register FloodSense Prefect cron deployments."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Run prefect deploy commands (otherwise only print commands).",
    )
    parser.add_argument(
        "--pool",
        default=os.getenv("PREFECT_WORK_POOL", "default-agent-pool"),
        help="Prefect work pool name.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.apply:
        deploy_all(args.pool)
    else:
        print_deploy_commands(args.pool)


if __name__ == "__main__":
    main()
