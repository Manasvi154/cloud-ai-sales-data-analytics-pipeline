from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app
from werkzeug.utils import secure_filename

from app.services.aws_clients import get_clients
from app.services.pipeline_stub import (
    get_job as get_stub_job,
    list_jobs as list_stub_jobs,
    start_pipeline as start_stub_pipeline,
)


class PipelineStartError(RuntimeError):
    """Raised when the AWS pipeline cannot be started and fallback is disabled."""


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _pipeline_mode() -> str:
    return str(current_app.config.get("PIPELINE_MODE", "stub")).strip().lower()


def _aws_mode_enabled() -> bool:
    return _pipeline_mode() == "aws"


def _allow_stub_fallback() -> bool:
    return bool(current_app.config.get("PIPELINE_ALLOW_STUB_FALLBACK", True))


def _drop_empty_values(values: dict) -> dict:
    return {key: value for key, value in values.items() if value not in ("", None)}


def _sanitize_metadata_value(value: str, limit: int = 512) -> str:
    normalized = " ".join((value or "").split())
    return normalized[:limit]


def _build_s3_upload_key(job_id: str, filename: str) -> str:
    raw_prefix = str(current_app.config.get("S3_RAW_UPLOAD_PREFIX", "raw/uploads")).strip("/")
    safe_name = secure_filename(filename) or "dataset.csv"
    return f"{raw_prefix}/{job_id}/{safe_name}"


def _execution_name(job_id: str) -> str:
    return f"{job_id}-{int(time.time())}"


def _coerce_decimal(value):
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: _coerce_decimal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_coerce_decimal(item) for item in value]
    return value


def _status_to_summary(status: str, stage: str) -> str:
    normalized_status = (status or "UNKNOWN").upper()
    if normalized_status == "SUCCEEDED":
        return "Pipeline completed successfully."
    if normalized_status == "FAILED":
        return "Pipeline failed. Check pipeline logs for details."
    return f"Pipeline is running ({stage or 'IN_PROGRESS'})."


def _normalize_job_for_ui(job: dict | None) -> dict | None:
    if not job:
        return None

    normalized = _coerce_decimal(job)
    status = str(normalized.get("status", "UNKNOWN")).upper()
    stage = str(normalized.get("stage", "UNKNOWN"))
    normalized["status"] = status
    normalized["stage"] = stage
    normalized.setdefault("created_at", "")
    normalized.setdefault("updated_at", "")
    normalized.setdefault("filename", "dataset.csv")
    normalized.setdefault("operation", "auto")
    normalized.setdefault("description", "")

    result = normalized.get("result") or {}
    if not isinstance(result, dict):
        result = {}
    result.setdefault("summary", _status_to_summary(status=status, stage=stage))
    result.setdefault("description", normalized.get("description", ""))
    result.setdefault("metrics", {})
    result.setdefault("insights", [])
    result.setdefault("recommendations", [])
    normalized["result"] = result
    return normalized


def _append_job_event(
    dynamodb_resource,
    job_id: str,
    status: str,
    stage: str,
    message: str,
) -> None:
    events_table_name = str(current_app.config.get("DYNAMODB_TABLE_EVENTS", "")).strip()
    if not events_table_name:
        return

    try:
        events_table = dynamodb_resource.Table(events_table_name)
        event_ts = _utcnow_iso()
        events_table.put_item(
            Item={
                "job_id": job_id,
                "event_ts": event_ts,
                "status": status,
                "stage": stage,
                "message": message,
            }
        )
    except (ClientError, BotoCoreError):
        current_app.logger.exception("Unable to append pipeline event for job %s", job_id)


def _start_pipeline_aws(
    *,
    filename: str,
    file_stream,
    operation: str,
    description: str,
    user_id: str,
    content_type: str = "",
) -> str:
    bucket_name = str(current_app.config.get("S3_BUCKET_DATASETS", "")).strip()
    jobs_table_name = str(current_app.config.get("DYNAMODB_TABLE_JOBS", "")).strip()
    step_function_arn = str(current_app.config.get("STEP_FUNCTION_ARN", "")).strip()
    start_mode = str(current_app.config.get("PIPELINE_START_MODE", "s3_event")).strip().lower()

    if not bucket_name:
        raise PipelineStartError("S3_BUCKET_DATASETS is required for PIPELINE_MODE=aws.")
    if not jobs_table_name:
        raise PipelineStartError("DYNAMODB_TABLE_JOBS is required for PIPELINE_MODE=aws.")
    if start_mode == "direct_step_function" and not step_function_arn:
        raise PipelineStartError(
            "STEP_FUNCTION_ARN is required when PIPELINE_START_MODE=direct_step_function."
        )

    clients = get_clients()
    s3_client = clients["s3"]
    dynamodb_resource = clients["dynamodb"]
    stepfunctions_client = clients["stepfunctions"]
    jobs_table = dynamodb_resource.Table(jobs_table_name)

    job_id = str(uuid4())
    created_at = _utcnow_iso()
    s3_input_key = _build_s3_upload_key(job_id=job_id, filename=filename)

    if hasattr(file_stream, "seek"):
        file_stream.seek(0)

    extra_args = {
        "Metadata": _drop_empty_values(
            {
                "job-id": job_id,
                "user-id": user_id,
                "operation": operation.lower(),
                "description": _sanitize_metadata_value(description),
                "original-filename": filename,
            }
        )
    }
    if content_type:
        extra_args["ContentType"] = content_type

    s3_client.upload_fileobj(
        Fileobj=file_stream,
        Bucket=bucket_name,
        Key=s3_input_key,
        ExtraArgs=extra_args,
    )

    job_item = _drop_empty_values(
        {
            "job_id": job_id,
            "user_id": user_id,
            "filename": filename,
            "operation": operation,
            "description": description,
            "status": "UPLOADED",
            "stage": "S3_UPLOAD_COMPLETED",
            "s3_input_bucket": bucket_name,
            "s3_input_key": s3_input_key,
            "created_at": created_at,
            "updated_at": created_at,
        }
    )
    jobs_table.put_item(Item=job_item)
    _append_job_event(
        dynamodb_resource=dynamodb_resource,
        job_id=job_id,
        status="UPLOADED",
        stage="S3_UPLOAD_COMPLETED",
        message="Dataset uploaded successfully to S3.",
    )

    if start_mode == "direct_step_function":
        execution_payload = {
            "job_id": job_id,
            "user_id": user_id,
            "filename": filename,
            "operation": operation,
            "description": description,
            "s3_input_bucket": bucket_name,
            "s3_input_key": s3_input_key,
            "created_at": created_at,
        }
        execution_response = stepfunctions_client.start_execution(
            stateMachineArn=step_function_arn,
            name=_execution_name(job_id),
            input=json.dumps(execution_payload),
        )
        execution_arn = execution_response["executionArn"]
        updated_at = _utcnow_iso()
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
                ":updated_at": updated_at,
            },
        )
        _append_job_event(
            dynamodb_resource=dynamodb_resource,
            job_id=job_id,
            status="ORCHESTRATION_STARTED",
            stage="STEP_FUNCTIONS_STARTED",
            message="Step Functions execution started directly by Flask.",
        )

    return job_id


def start_pipeline(
    *,
    filename: str,
    file_stream,
    operation: str,
    description: str,
    user_id: str,
    content_type: str = "",
) -> str:
    if not _aws_mode_enabled():
        return start_stub_pipeline(
            filename=filename,
            operation=operation,
            description=description,
            user_id=user_id,
        )

    try:
        return _start_pipeline_aws(
            filename=filename,
            file_stream=file_stream,
            operation=operation,
            description=description,
            user_id=user_id,
            content_type=content_type,
        )
    except PipelineStartError:
        raise
    except (ClientError, BotoCoreError, OSError, ValueError):
        current_app.logger.exception("AWS pipeline start failed.")
        if _allow_stub_fallback():
            current_app.logger.warning("Falling back to local pipeline stub.")
            return start_stub_pipeline(
                filename=filename,
                operation=operation,
                description=description,
                user_id=user_id,
            )
        raise PipelineStartError(
            "Unable to start AWS pipeline. Check bucket/table/role configuration."
        )


def _get_job_aws(job_id: str) -> dict | None:
    jobs_table_name = str(current_app.config.get("DYNAMODB_TABLE_JOBS", "")).strip()
    if not jobs_table_name:
        raise PipelineStartError("DYNAMODB_TABLE_JOBS is required for PIPELINE_MODE=aws.")

    clients = get_clients()
    jobs_table = clients["dynamodb"].Table(jobs_table_name)
    response = jobs_table.get_item(Key={"job_id": job_id})
    return _normalize_job_for_ui(response.get("Item"))


def get_job(job_id: str) -> dict | None:
    if not _aws_mode_enabled():
        return _normalize_job_for_ui(get_stub_job(job_id))

    try:
        return _get_job_aws(job_id)
    except (PipelineStartError, ClientError, BotoCoreError):
        current_app.logger.exception("Unable to fetch job %s from AWS.", job_id)
        if _allow_stub_fallback():
            return _normalize_job_for_ui(get_stub_job(job_id))
        return None


def _list_jobs_aws(user_id: str) -> list[dict]:
    jobs_table_name = str(current_app.config.get("DYNAMODB_TABLE_JOBS", "")).strip()
    if not jobs_table_name:
        raise PipelineStartError("DYNAMODB_TABLE_JOBS is required for PIPELINE_MODE=aws.")

    clients = get_clients()
    jobs_table = clients["dynamodb"].Table(jobs_table_name)
    index_name = str(current_app.config.get("PIPELINE_JOBS_USER_GSI", "")).strip()

    items = []
    if index_name:
        try:
            query_response = jobs_table.query(
                IndexName=index_name,
                KeyConditionExpression=Key("user_id").eq(user_id),
                ScanIndexForward=False,
            )
            items = query_response.get("Items", [])
        except ClientError:
            current_app.logger.exception(
                "Unable to query jobs by GSI '%s'. Falling back to table scan.", index_name
            )

    if not items:
        scan_response = jobs_table.scan(FilterExpression=Attr("user_id").eq(user_id))
        items = scan_response.get("Items", [])

    normalized = [_normalize_job_for_ui(item) for item in items]
    return sorted(
        [item for item in normalized if item],
        key=lambda job: job.get("created_at", ""),
        reverse=True,
    )


def list_jobs(user_id: str) -> list[dict]:
    if not _aws_mode_enabled():
        return [_normalize_job_for_ui(job) for job in list_stub_jobs(user_id=user_id)]

    try:
        return _list_jobs_aws(user_id=user_id)
    except (PipelineStartError, ClientError, BotoCoreError):
        current_app.logger.exception("Unable to list jobs from AWS for user %s.", user_id)
        if _allow_stub_fallback():
            return [_normalize_job_for_ui(job) for job in list_stub_jobs(user_id=user_id)]
        return []


def get_job_events(job_id: str, limit: int = 25) -> list[dict]:
    if not _aws_mode_enabled():
        job = _normalize_job_for_ui(get_stub_job(job_id))
        if not job:
            return []
        return [
            {
                "job_id": job_id,
                "event_ts": job.get("updated_at"),
                "status": job.get("status"),
                "stage": job.get("stage"),
                "message": "Local stub pipeline completed.",
            }
        ]

    events_table_name = str(current_app.config.get("DYNAMODB_TABLE_EVENTS", "")).strip()
    if not events_table_name:
        return []

    try:
        clients = get_clients()
        events_table = clients["dynamodb"].Table(events_table_name)
        response = events_table.query(
            KeyConditionExpression=Key("job_id").eq(job_id),
            ScanIndexForward=False,
            Limit=max(1, limit),
        )
        events = [_coerce_decimal(item) for item in response.get("Items", [])]
        events.reverse()
        return events
    except (ClientError, BotoCoreError):
        current_app.logger.exception("Unable to fetch events for job %s.", job_id)
        return []
