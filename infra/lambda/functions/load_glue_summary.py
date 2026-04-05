from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import boto3

s3_client = boto3.client("s3")

processed_bucket = os.environ["PROCESSED_BUCKET"]
summary_prefix = os.environ.get("GLUE_SUMMARY_PREFIX", "processed/summaries").strip("/")


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def handler(event, _context):
    job_id = str(event.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("job_id is required.")

    summary_key = f"{summary_prefix}/{job_id}.json"
    response = s3_client.get_object(Bucket=processed_bucket, Key=summary_key)
    summary_body = response["Body"].read().decode("utf-8")
    summary = json.loads(summary_body)

    output = {
        "job_id": job_id,
        "summary_loaded_at": _utcnow_iso(),
        "preprocessing_summary": summary,
        "schema_summary": summary.get("schema_summary", {}),
        "cleaned_data_s3_uri": summary.get("cleaned_data_s3_uri", ""),
        "feature_data_s3_uri": summary.get("feature_data_s3_uri", ""),
        "target_column_candidates": summary.get("target_column_candidates", []),
    }

    merged = dict(event)
    merged.update(output)
    return merged
