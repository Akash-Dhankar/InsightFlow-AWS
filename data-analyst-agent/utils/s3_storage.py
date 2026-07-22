"""
s3_storage.py – Optional S3 persistence for InsightFlow (Phase A).

Enabled when INSIGHTFLOW_S3_BUCKET is set. Local runs without the env var
keep the previous in-memory / download-only behavior.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

_BUCKET = os.getenv("INSIGHTFLOW_S3_BUCKET", "").strip()
_PREFIX = os.getenv("INSIGHTFLOW_S3_PREFIX", "insightflow").strip().strip("/")
_REGION = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION") or "us-east-1"

_client = None
_client_error: Optional[str] = None


def s3_enabled() -> bool:
    """True when a bucket is configured for artifact storage."""
    return bool(_BUCKET)


def s3_status() -> dict:
    """Sidebar-friendly status for S3 configuration and connectivity."""
    if not _BUCKET:
        return {
            "enabled": False,
            "ready": False,
            "bucket": "",
            "prefix": _PREFIX,
            "message": "S3 disabled (set INSIGHTFLOW_S3_BUCKET to enable)",
        }
    client = _get_client()
    if client is None:
        return {
            "enabled": True,
            "ready": False,
            "bucket": _BUCKET,
            "prefix": _PREFIX,
            "message": _client_error or "S3 client unavailable",
        }
    return {
        "enabled": True,
        "ready": True,
        "bucket": _BUCKET,
        "prefix": _PREFIX,
        "message": f"s3://{_BUCKET}/{_PREFIX}/",
    }


def _get_client():
    global _client, _client_error
    if not _BUCKET:
        return None
    if _client is not None:
        return _client
    try:
        import boto3

        _client = boto3.client("s3", region_name=_REGION)
        _client_error = None
        return _client
    except Exception as exc:  # pragma: no cover - env/runtime dependent
        _client_error = f"Could not create S3 client: {exc}"
        logger.warning(_client_error)
        return None


def _safe_name(name: str) -> str:
    base = os.path.basename(name or "file")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return cleaned or "file"


def _object_key(kind: str, filename: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S")
    safe = _safe_name(filename)
    return f"{_PREFIX}/{kind}/{stamp}_{safe}"


def upload_bytes(
    data: bytes,
    *,
    kind: str,
    filename: str,
    content_type: str,
) -> Optional[str]:
    """
    Upload bytes to S3. Returns the object key on success, None otherwise.
    Never raises — failures are logged so the UI keeps working.
    """
    if not s3_enabled():
        return None

    client = _get_client()
    if client is None:
        return None

    key = _object_key(kind, filename)
    try:
        client.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("Uploaded %s to s3://%s/%s", filename, _BUCKET, key)
        return key
    except Exception as exc:
        logger.exception("S3 upload failed for %s: %s", filename, exc)
        return None


def upload_fileobj(
    fileobj,
    *,
    kind: str,
    filename: str,
    content_type: str,
) -> Optional[str]:
    """Upload a file-like object (e.g. Streamlit UploadedFile or BytesIO)."""
    if not s3_enabled():
        return None
    try:
        if hasattr(fileobj, "getvalue"):
            data = fileobj.getvalue()
        else:
            pos = None
            if hasattr(fileobj, "tell") and hasattr(fileobj, "seek"):
                try:
                    pos = fileobj.tell()
                    fileobj.seek(0)
                except Exception:
                    pos = None
            data = fileobj.read()
            if pos is not None:
                try:
                    fileobj.seek(pos)
                except Exception:
                    pass
        if isinstance(data, str):
            data = data.encode("utf-8")
        return upload_bytes(
            data,
            kind=kind,
            filename=filename,
            content_type=content_type,
        )
    except Exception as exc:
        logger.exception("S3 fileobj upload failed for %s: %s", filename, exc)
        return None


def upload_csv(fileobj, filename: str) -> Optional[str]:
    return upload_fileobj(
        fileobj,
        kind="uploads",
        filename=filename,
        content_type="text/csv",
    )


def upload_pdf(buffer: BytesIO, filename: str = "insightflow_report.pdf") -> Optional[str]:
    return upload_fileobj(
        buffer,
        kind="reports",
        filename=filename,
        content_type="application/pdf",
    )


def upload_chart_png(buffer: BytesIO, filename: str) -> Optional[str]:
    return upload_fileobj(
        buffer,
        kind="charts",
        filename=filename,
        content_type="image/png",
    )
