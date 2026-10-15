# /// script
# requires-python = ">=3.12"
# dependencies = ["boto3", "httpx", "python-dotenv", "structlog"]
# ///
"""Upload and read back a tiny R2 test object; never display credentials.

Run: uv run --script scripts/check_r2_upload.py
Uses private root .env or process environment. Leaves its unique test object in the bucket.
S3_API_KEY is a Cloudflare R2 API token, not a standalone S3 secret access key.
"""

import argparse
import hashlib
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# boto3 is declared in the inline script metadata above, not in the project environment.
import boto3  # pyright: ignore[reportMissingImports]
import httpx
import structlog
from botocore.config import Config  # pyright: ignore[reportMissingImports]
from botocore.exceptions import BotoCoreError, ClientError  # pyright: ignore[reportMissingImports]
from dotenv import dotenv_values

log = structlog.get_logger()


def credentials(values: dict[str, str], account: str) -> tuple[str, str]:
    """Prefer explicit S3 credentials, otherwise privately derive them from the R2 token."""
    access = values.get("R2_ACCESS_KEY_ID") or values.get("S3_ACCESS_KEY_ID")
    secret = values.get("R2_SECRET_ACCESS_KEY") or values.get("S3_SECRET_ACCESS_KEY")
    if access and secret:
        return access, secret
    token = values.get("S3_API_KEY")
    if not token:
        raise ValueError("Set S3_API_KEY or both R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY")
    # Cloudflare: Access Key ID = token ID; S3 secret = SHA-256(token value).
    with httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0), follow_redirects=False) as client:
        for path in (f"accounts/{account}/tokens/verify", "user/tokens/verify"):
            response = client.get(
                f"https://api.cloudflare.com/client/v4/{path}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code != 200:
                continue
            data = response.json()
            result = data.get("result") or {}
            token_id = result.get("id")
            if data.get("success") and result.get("status") == "active" and token_id:
                return str(token_id), hashlib.sha256(token.encode()).hexdigest()
    raise ValueError(
        "S3_API_KEY could not be verified as an active Cloudflare token; supply R2 S3 credentials"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default="rent-monitor")
    parser.add_argument("--jurisdiction", choices=("default", "eu", "us", "fedramp"), default="default")
    args = parser.parse_args()
    structlog.configure(processors=[structlog.processors.JSONRenderer()])
    values = {
        key: value
        for key, value in dotenv_values(
            Path(__file__).resolve().parents[1] / ".env", interpolate=False
        ).items()
        if value
    }
    values.update(os.environ)
    account = values.get("S3_ACCOUNT_ID") or values.get("R2_ACCOUNT_ID", "")
    if not re.fullmatch(r"[0-9a-fA-F]{32}", account):
        log.error("r2_configuration_invalid", reason="Set a valid S3_ACCOUNT_ID or R2_ACCOUNT_ID")
        return 1
    suffix = "" if args.jurisdiction == "default" else f".{args.jurisdiction}"
    key = f"connection-tests/{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex}.txt"
    body = b"R2 upload and read-back connectivity test.\n"
    phase = "credentials"
    access = secret = ""
    try:
        access, secret = credentials(values, account)
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{account}{suffix}.r2.cloudflarestorage.com",
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            region_name="auto",
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=15,
                retries={"max_attempts": 2, "mode": "standard"},
                s3={"addressing_style": "path"},
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )
        phase = "upload"
        client.put_object(Bucket=args.bucket, Key=key, Body=body, ContentType="text/plain")
        log.info("r2_upload_succeeded", bucket=args.bucket, object_key=key, bytes=len(body))
        phase = "read_back"
        response = client.get_object(Bucket=args.bucket, Key=key)
        stream = response["Body"]
        try:
            received = stream.read(len(body) + 1)
        finally:
            stream.close()
        if received != body:
            raise ValueError("Read-back content did not match uploaded content")
        log.info(
            "r2_connection_verified",
            bucket=args.bucket,
            object_key=key,
            sha256=hashlib.sha256(body).hexdigest(),
        )
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", "unknown"))
        # Expose a useful diagnostic only after stripping credential values.
        reason = str(exc.response.get("Error", {}).get("Message", ""))
        for private_value in (access, secret, values.get("S3_API_KEY", ""), account):
            if private_value:
                reason = reason.replace(private_value, "[redacted]")
        log.error("r2_check_failed", phase=phase, error_code=code, reason=reason, object_key=key)
        return 1
    except (BotoCoreError, httpx.HTTPError, ValueError) as exc:
        # Raw provider exceptions may expose headers/URLs; emit only a safe category.
        log.error("r2_check_failed", phase=phase, error_type=type(exc).__name__, object_key=key)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
