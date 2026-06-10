from __future__ import annotations
import pandas as pd

def generate_dashboard_data(file_path):
    df = pd.read_csv(file_path)

    # ---- KPI CALCULATIONS ----
    total_sales = df['units_sold'].sum()
    avg_sales = df['units_sold'].mean()

    top_category = df.groupby('category')['units_sold'].sum().idxmax()
    top_region = df.groupby('region')['units_sold'].sum().idxmax()

    # ---- EXISTING LOGIC ----
    df['date'] = pd.to_datetime(df['date'])

    monthly = df.groupby(df['date'].dt.to_period('M'))['units_sold'].sum()

    category = df.groupby('category')['units_sold'].sum()
    region = df.groupby('region')['units_sold'].sum()

    return {
        # KPI
        "total_sales": int(total_sales),
        "avg_sales": round(avg_sales, 2),
        "top_category": top_category,
        "top_region": top_region,

        # Charts
        "monthly_labels": monthly.index.astype(str).tolist(),
        "monthly_values": monthly.values.tolist(),

        "category_labels": category.index.tolist(),
        "category_values": category.values.tolist(),

        "region_labels": region.index.tolist(),
        "region_values": region.values.tolist()
    }

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
