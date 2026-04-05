from __future__ import annotations


def generate_report_markdown(job: dict) -> str:
    result = job.get("result", {})
    metrics = result.get("metrics", {})
    insights = result.get("insights", [])
    recommendations = result.get("recommendations", [])

    lines = [
        f"# Automated Analytics Report: {job.get('filename', 'dataset')}",
        "",
        f"- Job ID: `{job.get('job_id')}`",
        f"- Operation: `{job.get('operation')}`",
        f"- Status: `{job.get('status')}`",
        "",
        "## Key Metrics",
    ]
    lines.extend([f"- {key}: {value}" for key, value in metrics.items()])
    lines.append("")
    lines.append("## Insights")
    lines.extend([f"- {item}" for item in insights])
    lines.append("")
    lines.append("## Recommendations")
    lines.extend([f"- {item}" for item in recommendations])
    return "\n".join(lines)
