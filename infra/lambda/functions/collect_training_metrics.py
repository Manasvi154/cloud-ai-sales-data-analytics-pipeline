from __future__ import annotations

import io
import json
import os
import tarfile
import urllib.parse
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3

sagemaker_client = boto3.client("sagemaker")
s3_client = boto3.client("s3")

metrics_file_name = os.environ.get("METRICS_FILE_NAME", "evaluation.json")


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


def _extract_training_job_name(event: dict) -> str:
    for key in ("training_job_name", "TrainingJobName"):
        if event.get(key):
            return str(event[key])
    if isinstance(event.get("training"), dict):
        training = event["training"]
        for key in ("TrainingJobName", "training_job_name"):
            if training.get(key):
                return str(training[key])
    if isinstance(event.get("SageMakerTraining"), dict):
        training = event["SageMakerTraining"]
        if training.get("TrainingJobName"):
            return str(training["TrainingJobName"])
    return ""


def _split_s3_uri(s3_uri: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(s3_uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def _read_metrics_from_model_artifact(model_artifact_uri: str) -> dict[str, Any]:
    bucket, key = _split_s3_uri(model_artifact_uri)
    obj = s3_client.get_object(Bucket=bucket, Key=key)
    blob = obj["Body"].read()

    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.name.endswith(metrics_file_name):
                handle = archive.extractfile(member)
                if handle:
                    raw = handle.read().decode("utf-8")
                    return json.loads(raw)
    return {}


def handler(event, _context):
    payload = _to_native(event)
    training_job_name = _extract_training_job_name(payload)
    if not training_job_name:
        raise ValueError("Training job name was not found in input payload.")

    describe = sagemaker_client.describe_training_job(TrainingJobName=training_job_name)
    model_artifact_uri = describe["ModelArtifacts"]["S3ModelArtifacts"]
    final_status = describe.get("TrainingJobStatus", "Unknown")

    metrics = {}
    try:
        metrics = _read_metrics_from_model_artifact(model_artifact_uri=model_artifact_uri)
    except Exception:
        # Keep pipeline moving even if metrics file is absent.
        metrics = {}

    output = {
        "job_id": payload.get("job_id"),
        "training_job_name": training_job_name,
        "training_job_status": final_status,
        "model_artifact_s3_uri": model_artifact_uri,
        "model_metrics": metrics,
        "metrics_collected_at": _utcnow_iso(),
    }

    merged = dict(payload)
    merged.update(output)
    return merged
