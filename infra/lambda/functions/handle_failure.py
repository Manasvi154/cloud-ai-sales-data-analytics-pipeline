from __future__ import annotations

import os
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
jobs_table = dynamodb.Table(os.environ["JOBS_TABLE_NAME"])
events_table_name = os.environ.get("EVENTS_TABLE_NAME", "").strip()
events_table = dynamodb.Table(events_table_name) if events_table_name else None


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def handler(event, _context):
    job_id = str(event.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("job_id is required.")

    error_payload = event.get("error") or event.get("cause") or event
    error_message = str(error_payload)[:3000]
    stage = str(event.get("stage", "PIPELINE_FAILED"))
    timestamp = _utcnow_iso()

    jobs_table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=(
            "SET #status=:status, #stage=:stage, updated_at=:updated_at, "
            "error_message=:error_message, latest_message=:latest_message"
        ),
        ExpressionAttributeNames={"#status": "status", "#stage": "stage"},
        ExpressionAttributeValues={
            ":status": "FAILED",
            ":stage": stage,
            ":updated_at": timestamp,
            ":error_message": error_message,
            ":latest_message": "Pipeline failed. Review CloudWatch logs.",
        },
    )

    if events_table:
        try:
            events_table.put_item(
                Item={
                    "job_id": job_id,
                    "event_ts": timestamp,
                    "status": "FAILED",
                    "stage": stage,
                    "message": error_message,
                }
            )
        except ClientError:
            pass

    return {"job_id": job_id, "status": "FAILED", "stage": stage, "error_message": error_message}
