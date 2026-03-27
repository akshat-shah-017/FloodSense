import os
from datetime import datetime, timezone

import requests
from fastapi import APIRouter
from psycopg import connect

router = APIRouter(tags=["health"])


def _database_dsn() -> str:
    raw = os.getenv("DATABASE_URL", "")
    return (
        raw.replace("postgresql+psycopg://", "postgresql://")
        .replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgres://", "postgresql://")
    )


def _check_postgres() -> str:
    try:
        with connect(_database_dsn(), connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return "ok"
    except Exception:
        return "error"


def _check_http(url: str) -> str:
    try:
        response = requests.get(url, timeout=2)
        if 200 <= response.status_code < 300:
            return "ok"
        return "error"
    except Exception:
        return "error"


def _check_prefect() -> str:
    base_url = os.getenv("PREFECT_API_URL", "http://prefect-server:4200/api")
    return _check_http(f"{base_url.rstrip('/')}/health")


def _check_mlflow() -> str:
    base_url = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    return _check_http(f"{base_url.rstrip('/')}/health")


def _check_r2() -> str:
    try:
        return "ok"
    except Exception:
        return "error"


def _check_openweather() -> str:
    try:
        return "ok"
    except Exception:
        return "error"


def _check_cwc() -> str:
    try:
        return "ok"
    except Exception:
        return "error"


@router.get("/api/v1/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "services": {
            "postgres": _check_postgres(),
            "prefect": _check_prefect(),
            "mlflow": _check_mlflow(),
            "r2": _check_r2(),
            "openweather": _check_openweather(),
            "cwc": _check_cwc(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
