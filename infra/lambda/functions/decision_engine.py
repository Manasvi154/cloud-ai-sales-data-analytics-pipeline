from __future__ import annotations

import json
import os
import re
from typing import Any

import boto3

bedrock_model_id = os.environ.get("BEDROCK_MODEL_ID", "").strip()
bedrock_client = boto3.client("bedrock-runtime") if bedrock_model_id else None

TARGET_NAME_KEYWORDS = {
    "target",
    "label",
    "price",
    "sales",
    "output",
    "y",
    "revenue",
    "demand",
    "churn",
    "class",
}

OPERATION_TO_TASK = {
    "regression": "regression",
    "regression_analysis": "regression",
    "classification": "classification",
    "forecasting": "forecasting",
    "anomaly_detection": "classification",
    "segmentation": "classification",
}


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _extract_columns(event: dict) -> list[dict]:
    schema_summary = event.get("schema_summary", {})
    if isinstance(schema_summary, list):
        return schema_summary
    if isinstance(schema_summary, dict):
        columns = schema_summary.get("columns")
        if isinstance(columns, list):
            return columns
    return []


def _pick_target_candidate(columns: list[dict]) -> tuple[str, float]:
    if not columns:
        return "", 0.0

    scored: list[tuple[float, str]] = []
    for column in columns:
        name = _normalize_text(column.get("name"))
        dtype = _normalize_text(column.get("type") or column.get("dtype"))
        unique_count = float(column.get("unique_count", 0) or 0)
        variance = float(column.get("variance", 0) or 0)
        null_pct = float(column.get("null_pct", 0) or 0)
        score = 0.0

        if any(keyword in name for keyword in TARGET_NAME_KEYWORDS):
            score += 0.55
        if dtype in {"int", "integer", "float", "double", "long", "decimal", "numeric"}:
            score += 0.2
        if unique_count > 4:
            score += 0.1
        if variance > 0:
            score += 0.1
        if null_pct > 50:
            score -= 0.2

        scored.append((score, column.get("name", "")))

    scored.sort(reverse=True, key=lambda item: item[0])
    best_score, best_name = scored[0]
    return str(best_name), max(0.0, min(1.0, best_score))


def _infer_task_from_columns(columns: list[dict], target_column: str) -> tuple[str, float]:
    if not columns:
        return "regression", 0.45

    target = None
    target_lower = _normalize_text(target_column)
    for column in columns:
        if _normalize_text(column.get("name")) == target_lower:
            target = column
            break

    has_datetime = any(
        _normalize_text(col.get("type") or col.get("dtype"))
        in {"date", "timestamp", "datetime"}
        for col in columns
    )

    if target:
        dtype = _normalize_text(target.get("type") or target.get("dtype"))
        unique_count = float(target.get("unique_count", 0) or 0)
        if has_datetime and unique_count > 20:
            return "forecasting", 0.72
        if dtype in {"string", "category", "categorical", "bool", "boolean"}:
            return "classification", 0.7
        if unique_count <= 20:
            return "classification", 0.66
        return "regression", 0.68

    if has_datetime:
        return "forecasting", 0.6
    return "regression", 0.5


def _try_bedrock_inference(event: dict, fallback_target: str, fallback_task: str) -> dict | None:
    if not bedrock_client or not bedrock_model_id:
        return None

    schema_snippet = json.dumps(event.get("schema_summary", {}), ensure_ascii=True)[:5000]
    prompt = (
        "You are a data science planner.\n"
        "Given dataset schema and user operation, infer task_type and target_column.\n"
        "Return strict JSON with keys: task_type, target_column, confidence, reason.\n"
        "Allowed task_type values: regression, classification, forecasting.\n\n"
        f"user_operation: {event.get('operation', '')}\n"
        f"user_description: {event.get('description', '')}\n"
        f"heuristic_target: {fallback_target}\n"
        f"heuristic_task: {fallback_task}\n"
        f"schema_summary: {schema_snippet}\n"
    )

    response = bedrock_client.converse(
        modelId=bedrock_model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"temperature": 0.1, "maxTokens": 300},
    )
    content = response["output"]["message"]["content"][0]["text"]

    json_match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if not json_match:
        return None

    parsed = json.loads(json_match.group(0))
    if parsed.get("task_type") not in {"regression", "classification", "forecasting"}:
        return None
    parsed["confidence"] = float(parsed.get("confidence", 0.0))
    return parsed


def handler(event, _context):
    operation = _normalize_text(event.get("operation"))
    explicit_target = str(event.get("target_column", "")).strip()
    columns = _extract_columns(event)

    if explicit_target:
        inferred_task = OPERATION_TO_TASK.get(operation, "regression")
        result = {
            "job_id": event.get("job_id"),
            "task_type": inferred_task,
            "target_column": explicit_target,
            "confidence": 0.99,
            "source": "user_input",
            "reason": "Explicit target column provided in request.",
            "needs_user_confirmation": False,
        }
        merged = dict(event)
        merged.update({"decision": result})
        return merged

    target_candidate, target_conf = _pick_target_candidate(columns)
    task_from_operation = OPERATION_TO_TASK.get(operation, "")
    if task_from_operation:
        heuristic_task = task_from_operation
        task_conf = 0.9
    else:
        heuristic_task, task_conf = _infer_task_from_columns(columns, target_candidate)

    confidence = round(max(target_conf, task_conf), 3)
    source = "heuristic"
    reason = "Decision generated from operation hints and schema heuristics."

    try:
        llm_output = _try_bedrock_inference(
            event=event,
            fallback_target=target_candidate,
            fallback_task=heuristic_task,
        )
        if llm_output and float(llm_output.get("confidence", 0)) >= confidence:
            heuristic_task = llm_output.get("task_type", heuristic_task)
            target_candidate = llm_output.get("target_column", target_candidate)
            confidence = round(float(llm_output.get("confidence", confidence)), 3)
            source = "llm"
            reason = str(llm_output.get("reason", "LLM-inferred decision."))
    except Exception:
        # Bedrock assist is best-effort only.
        pass

    needs_confirmation = confidence < 0.45 or not target_candidate

    decision = {
        "job_id": event.get("job_id"),
        "task_type": heuristic_task,
        "target_column": target_candidate,
        "confidence": confidence,
        "source": source,
        "reason": reason,
        "needs_user_confirmation": needs_confirmation,
    }

    merged = dict(event)
    merged.update({"decision": decision})
    return merged
