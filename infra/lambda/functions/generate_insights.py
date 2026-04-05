from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import boto3

bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "").strip()
bedrock_client = boto3.client("bedrock-runtime") if bedrock_model_id else None


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


def _llm_insights(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not bedrock_client or not bedrock_model_id:
        return None

    prompt = (
        "You are a senior analytics consultant.\n"
        "Return strict JSON with keys: summary, key_findings, recommendations.\n"
        "key_findings and recommendations must be arrays of short bullet strings.\n"
        f"task_type: {payload.get('decision', {}).get('task_type', '')}\n"
        f"target_column: {payload.get('decision', {}).get('target_column', '')}\n"
        f"model_metrics: {json.dumps(payload.get('model_metrics', {}), ensure_ascii=True)}\n"
        f"preprocessing_summary: {json.dumps(payload.get('preprocessing_summary', {}), ensure_ascii=True)[:5000]}\n"
        f"user_description: {payload.get('description', '')}\n"
    )

    response = bedrock_client.converse(
        modelId=bedrock_model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0.2, "maxTokens": 600},
    )
    raw_text = response["output"]["message"]["content"][0]["text"]
    json_match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not json_match:
        return None

    parsed = json.loads(json_match.group(0))
    summary = str(parsed.get("summary", "")).strip()
    key_findings = parsed.get("key_findings", [])
    recommendations = parsed.get("recommendations", [])
    if not isinstance(key_findings, list) or not isinstance(recommendations, list):
        return None

    return {
        "summary": summary,
        "insights": [str(item) for item in key_findings][:8],
        "recommendations": [str(item) for item in recommendations][:8],
        "insight_source": "llm",
    }


def _fallback_insights(payload: dict[str, Any]) -> dict[str, Any]:
    decision = payload.get("decision", {})
    model_metrics = payload.get("model_metrics", {})
    task_type = decision.get("task_type", "regression")
    target_column = decision.get("target_column", "target")

    summary = f"{task_type.title()} pipeline completed for '{target_column}'."
    insights = [
        f"Model training completed for {task_type} task.",
        "Preprocessing and feature engineering finished successfully.",
    ]
    if isinstance(model_metrics, dict) and model_metrics:
        first_metric = next(iter(model_metrics.items()))
        insights.append(f"Primary metric: {first_metric[0]} = {first_metric[1]}.")

    recommendations = [
        "Review top predictive features before production rollout.",
        "Schedule periodic retraining to prevent model drift.",
        "Monitor input schema changes and null-rate spikes.",
    ]
    return {
        "summary": summary,
        "insights": insights,
        "recommendations": recommendations,
        "insight_source": "fallback",
    }


def handler(event, _context):
    payload = _to_native(event)
    insight_bundle = None

    try:
        insight_bundle = _llm_insights(payload)
    except Exception:
        insight_bundle = None

    if not insight_bundle:
        insight_bundle = _fallback_insights(payload)

    output = {
        "job_id": payload.get("job_id"),
        "summary": insight_bundle["summary"],
        "insights": insight_bundle["insights"],
        "recommendations": insight_bundle["recommendations"],
        "insight_source": insight_bundle["insight_source"],
        "insights_generated_at": _utcnow_iso(),
    }

    merged = dict(payload)
    merged.update(output)
    return merged
