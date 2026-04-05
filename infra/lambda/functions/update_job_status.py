from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError

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


def _clean_extra_fields(extra_fields: dict[str, Any] | None) -> dict[str, Any]:
    if not extra_fields:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in extra_fields.items():
        if value is None:
            continue
        cleaned[key] = value
    return cleaned


def _build_update_expression(fields: dict[str, Any]) -> tuple[str, dict[str, str], dict[str, Any]]:
    expression_parts: list[str] = []
    attr_names: dict[str, str] = {}
    attr_values: dict[str, Any] = {}
    for index, (field_name, field_value) in enumerate(fields.items()):
        name_key = f"#f{index}"
        value_key = f":v{index}"
        expression_parts.append(f"{name_key}={value_key}")
        attr_names[name_key] = field_name
        attr_values[value_key] = field_value
    return "SET " + ", ".join(expression_parts), attr_names, attr_values


def _put_event(job_id: str, status: str, stage: str, message: str, timestamp: str) -> None:
    if not events_table:
        return
    try:
        events_table.put_item(
            Item={
                "job_id": job_id,
                "event_ts": timestamp,
                "status": status,
                "stage": stage,
                "message": message,
            }
        )
    except ClientError:
        # Event logging should not break pipeline execution.
        pass


def handler(event, _context):
    payload = _to_native(event)
    job_id = str(payload.get("job_id", "")).strip()
    if not job_id:
        raise ValueError("job_id is required.")

    status = str(payload.get("status", "RUNNING")).upper()
    stage = str(payload.get("stage", "UNKNOWN_STAGE"))
    message = str(payload.get("message", f"Job moved to {stage}."))
    timestamp = _utcnow_iso()
    extra_fields = _clean_extra_fields(payload.get("extra_fields"))

    update_fields: dict[str, Any] = {
        "status": status,
        "stage": stage,
        "updated_at": timestamp,
        "latest_message": message,
    }
    update_fields.update(extra_fields)

    update_expression, attr_names, attr_values = _build_update_expression(update_fields)
    jobs_table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )

    _put_event(job_id=job_id, status=status, stage=stage, message=message, timestamp=timestamp)

    return {
        "job_id": job_id,
        "status": status,
        "stage": stage,
        "message": message,
        "updated_at": timestamp,
        "extra_fields": extra_fields,
    }


# Local smoke test:
# python -c "import json; from update_job_status import handler; print(handler({'job_id':'123','status':'RUNNING','stage':'TEST'}, None))"
