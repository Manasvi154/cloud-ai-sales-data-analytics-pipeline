from __future__ import annotations

import json
import os
import time
import urllib.parse
from datetime import UTC, datetime
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

s3_client = boto3.client("s3")
stepfunctions_client = boto3.client("stepfunctions")
dynamodb = boto3.resource("dynamodb")

jobs_table = dynamodb.Table(os.environ["JOBS_TABLE_NAME"])
events_table_name = os.environ.get("EVENTS_TABLE_NAME", "").strip()
events_table = dynamodb.Table(events_table_name) if events_table_name else None
state_machine_arn = os.environ["STATE_MACHINE_ARN"]
raw_upload_prefix = os.environ.get("RAW_UPLOAD_PREFIX", "raw/uploads/").strip()


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_prefix(prefix: str) -> str:
    cleaned = prefix.strip()
    if cleaned and not cleaned.endswith("/"):
        cleaned += "/"
    return cleaned


def _event_log(job_id: str, status: str, stage: str, message: str) -> None:
    if not events_table:
        return
    try:
        events_table.put_item(
            Item={
                "job_id": job_id,
                "event_ts": _utcnow_iso(),
                "status": status,
                "stage": stage,
                "message": message,
            }
        )
    except ClientError:
        pass


def _job_id_from_key(s3_key: str, prefix: str) -> str:
    normalized_prefix = _normalize_prefix(prefix)
    if normalized_prefix and s3_key.startswith(normalized_prefix):
        remainder = s3_key[len(normalized_prefix) :]
        return remainder.split("/", 1)[0]
    return ""


def _execution_name(job_id: str) -> str:
    short_id = job_id.replace("-", "")[:50]
    return f"{short_id}-{int(time.time())}"


def _safe_metadata_value(metadata: dict, key: str, fallback: str = "") -> str:
    value = metadata.get(key, fallback)
    if value is None:
        return fallback
    return str(value).strip()


def _upsert_job(
    *,
    job_id: str,
    user_id: str,
    filename: str,
    operation: str,
    description: str,
    bucket: str,
    s3_key: str,
) -> None:
    timestamp = _utcnow_iso()
    jobs_table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=(
            "SET user_id=:user_id, filename=:filename, operation=:operation, "
            "description=:description, s3_input_bucket=:s3_input_bucket, "
            "s3_input_key=:s3_input_key, #status=:status, #stage=:stage, "
            "updated_at=:updated_at, created_at=if_not_exists(created_at, :created_at)"
        ),
        ExpressionAttributeNames={"#status": "status", "#stage": "stage"},
        ExpressionAttributeValues={
            ":user_id": user_id,
            ":filename": filename,
            ":operation": operation,
            ":description": description,
            ":s3_input_bucket": bucket,
            ":s3_input_key": s3_key,
            ":status": "LAMBDA_TRIGGERED",
            ":stage": "S3_EVENT_RECEIVED",
            ":updated_at": timestamp,
            ":created_at": timestamp,
        },
    )
    _event_log(
        job_id=job_id,
        status="LAMBDA_TRIGGERED",
        stage="S3_EVENT_RECEIVED",
        message="S3 upload event captured. Starting Step Functions orchestration.",
    )


def _mark_execution_started(job_id: str, execution_arn: str) -> None:
    timestamp = _utcnow_iso()
    jobs_table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=(
            "SET #status=:status, #stage=:stage, execution_arn=:execution_arn, updated_at=:updated_at"
        ),
        ExpressionAttributeNames={"#status": "status", "#stage": "stage"},
        ExpressionAttributeValues={
            ":status": "ORCHESTRATION_STARTED",
            ":stage": "STEP_FUNCTIONS_STARTED",
            ":execution_arn": execution_arn,
            ":updated_at": timestamp,
        },
    )
    _event_log(
        job_id=job_id,
        status="ORCHESTRATION_STARTED",
        stage="STEP_FUNCTIONS_STARTED",
        message="Step Functions execution started from S3 trigger Lambda.",
    )


def handler(event, _context):
    prefix = _normalize_prefix(raw_upload_prefix)
    records = event.get("Records", [])
    processed: list[dict] = []

    for record in records:
        if record.get("eventSource") != "aws:s3":
            continue

        bucket_name = record["s3"]["bucket"]["name"]
        object_key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        if prefix and not object_key.startswith(prefix):
            continue

        head = s3_client.head_object(Bucket=bucket_name, Key=object_key)
        metadata = head.get("Metadata", {})

        derived_job_id = _job_id_from_key(object_key, prefix)
        job_id = _safe_metadata_value(metadata, "job-id", derived_job_id or str(uuid4()))
        user_id = _safe_metadata_value(metadata, "user-id", "unknown-user")
        filename = _safe_metadata_value(metadata, "original-filename", object_key.split("/")[-1])
        operation = _safe_metadata_value(metadata, "operation", "auto")
        description = _safe_metadata_value(metadata, "description", "")

        _upsert_job(
            job_id=job_id,
            user_id=user_id,
            filename=filename,
            operation=operation,
            description=description,
            bucket=bucket_name,
            s3_key=object_key,
        )

        execution_input = {
            "job_id": job_id,
            "user_id": user_id,
            "filename": filename,
            "operation": operation,
            "description": description,
            "s3_input_bucket": bucket_name,
            "s3_input_key": object_key,
            "created_at": _utcnow_iso(),
        }

        try:
            response = stepfunctions_client.start_execution(
                stateMachineArn=state_machine_arn,
                name=_execution_name(job_id),
                input=json.dumps(execution_input),
            )
            execution_arn = response["executionArn"]
            _mark_execution_started(job_id=job_id, execution_arn=execution_arn)
            processed.append({"job_id": job_id, "execution_arn": execution_arn, "status": "STARTED"})
        except ClientError as exc:
            _event_log(
                job_id=job_id,
                status="FAILED",
                stage="STEP_FUNCTIONS_START_FAILED",
                message=f"Unable to start Step Functions: {exc.response.get('Error', {}).get('Message', 'unknown error')}",
            )
            raise

    return {"processed_records": processed}
