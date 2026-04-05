from __future__ import annotations

import os
import time
from datetime import UTC, datetime

import boto3

quicksight_client = boto3.client("quicksight")

aws_account_id = os.environ.get("QUICKSIGHT_AWS_ACCOUNT_ID", "").strip()
dataset_id = os.environ.get("QUICKSIGHT_DATASET_ID", "").strip()
dashboard_id = os.environ.get("QUICKSIGHT_DASHBOARD_ID", "").strip()
namespace = os.environ.get("QUICKSIGHT_NAMESPACE", "default").strip()
user_arn = os.environ.get("QUICKSIGHT_USER_ARN", "").strip()
allowed_domains = [d.strip() for d in os.environ.get("QUICKSIGHT_ALLOWED_DOMAINS", "").split(",") if d.strip()]


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _start_ingestion(job_id: str) -> str:
    if not aws_account_id or not dataset_id:
        return ""
    ingestion_id = f"{job_id}-{int(time.time())}"
    quicksight_client.create_ingestion(
        AwsAccountId=aws_account_id,
        DataSetId=dataset_id,
        IngestionId=ingestion_id,
    )
    return ingestion_id


def _build_embed_url() -> str:
    if not aws_account_id or not dashboard_id or not user_arn:
        return ""

    response = quicksight_client.generate_embed_url_for_registered_user(
        AwsAccountId=aws_account_id,
        UserArn=user_arn,
        ExperienceConfiguration={"Dashboard": {"InitialDashboardId": dashboard_id}},
        SessionLifetimeInMinutes=60,
        AllowedDomains=allowed_domains or None,
    )
    return response.get("EmbedUrl", "")


def handler(event, _context):
    job_id = str(event.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("job_id is required.")

    ingestion_id = ""
    dashboard_embed_url = ""

    try:
        ingestion_id = _start_ingestion(job_id=job_id)
    except Exception:
        ingestion_id = ""

    try:
        dashboard_embed_url = _build_embed_url()
    except Exception:
        dashboard_embed_url = ""

    output = {
        "job_id": job_id,
        "quicksight_ingestion_id": ingestion_id,
        "dashboard_embed_url": dashboard_embed_url,
        "quicksight_updated_at": _utcnow_iso(),
    }
    merged = dict(event)
    merged.update(output)
    return merged
