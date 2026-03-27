from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import boto3


def _r2_endpoint() -> str:
    account_id = os.getenv("CLOUDFLARE_R2_ACCOUNT_ID", "")
    if not account_id:
        raise ValueError("CLOUDFLARE_R2_ACCOUNT_ID is required for R2 operations.")
    return f"https://{account_id}.r2.cloudflarestorage.com"


def _r2_bucket() -> str:
    return os.getenv("R2_RAW_BUCKET", "vyrus-raw")


def r2_client():
    access_key = os.getenv("CLOUDFLARE_R2_ACCESS_KEY", "")
    secret_key = os.getenv("CLOUDFLARE_R2_SECRET_KEY", "")
    if not access_key or not secret_key:
        raise ValueError(
            "CLOUDFLARE_R2_ACCESS_KEY and CLOUDFLARE_R2_SECRET_KEY must be configured."
        )

    return boto3.client(
        "s3",
        endpoint_url=_r2_endpoint(),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def upload_file(local_path: str | Path, r2_key: str) -> str:
    path = Path(local_path)
    if not path.exists():
        raise FileNotFoundError(f"Local file not found for upload: {path}")

    client = r2_client()
    client.upload_file(str(path), _r2_bucket(), r2_key)
    return r2_key


def upload_json(data_dict: dict[str, Any], r2_key: str) -> str:
    payload = json.dumps(data_dict, separators=(",", ":")).encode("utf-8")
    client = r2_client()
    client.put_object(
        Bucket=_r2_bucket(),
        Key=r2_key,
        Body=payload,
        ContentType="application/json",
    )
    return r2_key


def download_file(r2_key: str, local_path: str | Path) -> str:
    path = Path(local_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    client = r2_client()
    client.download_file(_r2_bucket(), r2_key, str(path))
    return str(path)


def generate_signed_url(r2_key: str, expiry_seconds: int = 86400) -> str:
    client = r2_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": _r2_bucket(), "Key": r2_key},
        ExpiresIn=expiry_seconds,
    )
