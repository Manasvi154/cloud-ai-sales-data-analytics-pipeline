from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3

dynamodb = boto3.resource("dynamodb")
jobs_table = dynamodb.Table(os.environ["JOBS_TABLE_NAME"])
events_table_name = os.environ.get("EVENTS_TABLE_NAME", "").strip()
events_table = dynamodb.Table(events_table_name) if events_table_name else None


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _to_native(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: _to_native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_native(item) for item in value]
    return value


def _event_log(job_id: str, status: str, stage: str, message: str) -> None:
    if not events_table:
        return
    events_table.put_item(
        Item={
            "job_id": job_id,
            "event_ts": _utcnow_iso(),
            "status": status,
            "stage": stage,
            "message": message,
        }
    )


def handler(event, _context):
    payload = _to_native(event)
    job_id = str(payload.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("job_id is required.")

    status = str(payload.get("status", "SUCCEEDED")).upper()
    stage = str(payload.get("stage", "PIPELINE_COMPLETED"))
    timestamp = _utcnow_iso()

    result_payload = {
        "summary": payload.get("summary", "Pipeline completed."),
        "description": payload.get("description", ""),
        "metrics": payload.get("model_metrics", {}),
        "insights": payload.get("insights", []),
        "recommendations": payload.get("recommendations", []),
        "dashboard_embed_url": payload.get("dashboard_embed_url", ""),
        "task_type": payload.get("decision", {}).get("task_type", ""),
        "target_column": payload.get("decision", {}).get("target_column", ""),
        "model_artifact_s3_uri": payload.get("model_artifact_s3_uri", ""),
        "processed_data_s3_uri": payload.get("cleaned_data_s3_uri", ""),
    }

    jobs_table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=(
            "SET #status=:status, #stage=:stage, updated_at=:updated_at, "
            "completed_at=:completed_at, result=:result, latest_message=:latest_message"
        ),
        ExpressionAttributeNames={"#status": "status", "#stage": "stage"},
        ExpressionAttributeValues={
            ":status": status,
            ":stage": stage,
            ":updated_at": timestamp,
            ":completed_at": timestamp,
            ":result": result_payload,
            ":latest_message": "Pipeline completed successfully."
            if status == "SUCCEEDED"
            else "Pipeline finished with failure.",
        },
    )

    _event_log(
        job_id=job_id,
        status=status,
        stage=stage,
        message="Result artifacts persisted and ready for UI.",
    )

    output = dict(payload)
    output.update({"job_id": job_id, "status": status, "stage": stage, "result": result_payload})
    return output
