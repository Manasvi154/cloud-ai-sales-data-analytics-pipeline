from __future__ import annotations

from app.services.pipeline.data_pipeline import run_pipeline

from datetime import UTC, datetime
from random import randint, uniform
from uuid import uuid4

JOBS: dict[str, dict] = {}


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_stub_result(operation: str, description: str) -> dict:
    op_label = operation.replace("_", " ").title()
    return {
        "summary": f"{op_label} completed successfully.",
        "description": description or "No custom analysis description was provided.",
        "metrics": {
            "rows_processed": randint(5000, 50000),
            "accuracy": round(uniform(0.78, 0.97), 3),
            "anomaly_rate": round(uniform(0.01, 0.08), 3),
            "forecast_horizon_days": randint(7, 60),
        },
        "insights": [
            "Top 20% customer segment contributes most of the revenue variance.",
            "Recent trend indicates stable growth with moderate seasonality.",
            "Isolation Forest highlighted a compact anomaly cluster in recent periods.",
        ],
        "recommendations": [
            "Prioritize retention campaigns for high-value user cohorts.",
            "Set automated anomaly alerts for the identified feature group.",
            "Re-train models weekly to keep forecast drift under control.",
        ],
    }


def start_pipeline(filename: str, operation: str, description: str, user_id: str) -> str:
    job_id = str(uuid4())
    created_at = _utcnow_iso()
    try:
        # Run your actual pipeline
        pipeline_output = run_pipeline(filename)

        result = {
            "summary": "Pipeline executed successfully.",
            "description": description or "Real analytics generated.",
            "metrics": pipeline_output["metrics"],
            "insights": pipeline_output["insights"],
            "monthly_sales": pipeline_output["monthly_sales"],
            "recommendations": [
                "Focus on high-performing categories.",
                "Optimize inventory for top regions.",
                "Use ML forecasting for demand planning."
            ],
        }

        status = "SUCCEEDED"

    except Exception as e:

        result = {
            "summary": "Pipeline execution failed.",
            "description": str(e),
            "metrics": {},
            "insights": [],
            "recommendations": []
        }

        status = "FAILED"

    # Phase 1 behavior: complete instantly with deterministic shape.
    JOBS[job_id] = {
        "job_id": job_id,
        "user_id": user_id,
        "filename": filename,
        "operation": operation,
        "description": description,
        "status": status,
        "created_at": created_at,
        "updated_at": _utcnow_iso(),
        "result": result,
    }
    return job_id


def get_job(job_id: str) -> dict | None:
    return JOBS.get(job_id)


def list_jobs(user_id: str) -> list[dict]:
    jobs = [job for job in JOBS.values() if job["user_id"] == user_id]
    return sorted(jobs, key=lambda item: item["created_at"], reverse=True)
