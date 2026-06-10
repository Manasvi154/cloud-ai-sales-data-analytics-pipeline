from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required
from flask import request

from app.services.pipeline_stub import get_job, list_jobs
from app.services.report_service import generate_report_markdown

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")

from app.services.report_service import generate_dashboard_data
import os
import pandas as pd


import boto3

def get_quicksight_embed_url(dashboard_id):
    client = boto3.client(
        "quicksight",
        region_name="ap-south-1"
    )

    response = client.get_dashboard_embed_url(
        AwsAccountId="",
        DashboardId=dashboard_id,
        IdentityType="QUICKSIGHT",
        UserArn="arn:aws:quicksight:ap-south-1:449639349013:user/default/449639349013",
        SessionLifetimeInMinutes=60,
        UndoRedoDisabled=False,
        ResetDisabled=False
    )

    return response["EmbedUrl"]
    

@analysis_bp.route("/dashboard/<job_id>")
@login_required
def dashboard(job_id):
    job = get_job(job_id)

    if not job:
        abort(404)

    if job.get("status") != "SUCCEEDED":
        return render_template("dashboard.html", job=job, error="Pipeline failed.")

    operation = job.get("operation")

    if operation == "business_analysis":
        dashboard_id = "291d134d-2932-44af-ba41-fe24353ef014"
    else:
        dashboard_id = "9d847aa9-98c4-461d-8375-91f1d6bc8bc4"

    embed_url = get_quicksight_embed_url(dashboard_id)

    return render_template(
        "dashboard.html",
        job=job,
        embed_url=embed_url
    )

@analysis_bp.route("/processing/<job_id>")
@login_required
def processing_status(job_id: str):
    job = get_job(job_id)
    if not job:
        abort(404)
    return render_template("processing.html", job=job)


# ==============================
# RESULTS (FIXED VERSION)
# ==============================
@analysis_bp.route("/results/<job_id>")
@login_required
def results(job_id: str):
    job = get_job(job_id)

    if not job:
        abort(404)

    if job.get("status") == "FAILED":
        return render_template("results.html", job=job, error="Pipeline failed")

    # ==============================
    # LOAD PROCESSED DATA ✅ (FIX)
    # ==============================
    processed_path = job.get("processed_path")

    if not processed_path or not os.path.exists(processed_path):
        return render_template("results.html", job=job, error="Processed data not found")

    df = pd.read_csv(processed_path)

    # ==============================
    # HANDLE COLUMN NAME ISSUES (SAFE)
    # ==============================
    df.columns = df.columns.str.strip().str.lower()

    # Try to fix common naming mismatches
    if "units sold" in df.columns:
        df.rename(columns={"units sold": "units_sold"}, inplace=True)

    # ==============================
    # FILTER VALUES FROM UI
    # ==============================
    category = "all"
    region = "all"
    year = "all"

    if job["operation"] == "business_analysis":
        category = request.args.get("category", "all")
        region = request.args.get("region", "all")
        year = request.args.get("year", "all")

    # ==============================
    # YEAR EXTRACTION
    # ==============================
    if "date" in df.columns:
        df["year"] = pd.to_datetime(df["date"], errors="coerce").dt.year

    # ==============================
    # APPLY FILTERS
    # ==============================
    if category != "all" and "category" in df.columns:
        df = df[df["category"] == category]

    if region != "all" and "region" in df.columns:
        df = df[df["region"] == region]

    if year != "all" and "year" in df.columns:
        df = df[df["year"] == int(year)]

    # ==============================
    # UNITS CALCULATION (SAFE)
    # ==============================
    if "units_sold" in df.columns:
        total_units = df["units_sold"].sum()
        avg_units = df["units_sold"].mean()
    else:
        total_units = 0
        avg_units = 0

    # ==============================
    # REVENUE CALCULATION
    # ==============================
    if "price" in df.columns and "units_sold" in df.columns:
        df["revenue"] = df["units_sold"] * df["price"]
    else:
        df["revenue"] = 0

    total_revenue = df["revenue"].sum()
    avg_revenue = df["revenue"].mean()

    # ==============================
    # ATTACH FILTERED RESULTS
    # ==============================
    job["result"]["filtered_units"] = {
        "total": int(total_units),
        "avg": round(float(avg_units), 2)
    }

    job["result"]["filtered_revenue"] = {
        "total": round(float(total_revenue), 2),
        "avg": round(float(avg_revenue), 2)
    }

    # ==============================
    # DROPDOWN VALUES (FROM FULL DATA)
    # ==============================
    full_df = pd.read_csv(processed_path)

    full_df.columns = full_df.columns.str.strip().str.lower()

    job["result"]["category_list"] = sorted(full_df.get("category", []).dropna().unique().tolist()) if "category" in full_df else []
    job["result"]["region_list"] = sorted(full_df.get("region", []).dropna().unique().tolist()) if "region" in full_df else []

    if "date" in full_df.columns:
        full_df["year"] = pd.to_datetime(full_df["date"], errors="coerce").dt.year
        job["result"]["year_list"] = sorted(full_df["year"].dropna().unique().tolist())
    else:
        job["result"]["year_list"] = []

    return render_template("results.html", job=job)


@analysis_bp.route("/report/<job_id>")
@login_required
def report(job_id: str):
    job = get_job(job_id)
    if not job:
        abort(404)

    import json
    import pandas as pd
    import os

    result = job.get("result", {})

    # convert string → dict
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except:
            result = {}

    metrics = result.get("metrics") or {}
    category_sales = result.get("category_sales") or {}
    region_sales = result.get("region_sales") or {}
    monthly_sales = result.get("monthly_sales") or {}
    filtered_revenue = result.get("filtered_revenue") or {}

    # =========================
    # LOAD DATASET (REAL VALUES)
    # =========================
    processed_path = job.get("processed_path")

    if processed_path and os.path.exists(processed_path):
        df = pd.read_csv(processed_path)
        row_count = len(df)
        column_count = len(df.columns)
    else:
        row_count = 0
        column_count = 0

    # =========================
    # DERIVED VALUES
    # =========================

    # --- TOTAL SALES ---
    if metrics.get("total_sales"):
        total_sales = metrics.get("total_sales")
    elif category_sales:
        total_sales = sum(category_sales.values())
    elif "units_sold" in df.columns:
        total_sales = df["units_sold"].sum()
    else:
        total_sales = 0


    # --- AVG SALES ---
    if metrics.get("avg_sales"):
        avg_sales = metrics.get("avg_sales")
    elif "units_sold" in df.columns and row_count:
        avg_sales = df["units_sold"].mean()
    else:
        avg_sales = 0


    # --- CATEGORY / REGION SALES (fallback to df) ---
    if not category_sales and "category" in df.columns:
        category_sales = df.groupby("category")["units_sold"].sum().to_dict()

    if not region_sales and "region" in df.columns:
        region_sales = df.groupby("region")["units_sold"].sum().to_dict()


    # --- TOP VALUES ---
    top_category = max(category_sales, key=category_sales.get) if category_sales else "N/A"
    top_region = max(region_sales, key=region_sales.get) if region_sales else "N/A"
    lowest_category = min(category_sales, key=category_sales.get) if category_sales else "N/A"


    # --- COUNTS ---
    category_count = len(category_sales)
    region_count = len(region_sales)


    # --- PERFORMANCE GAP ---
    if category_sales:
        performance_gap = max(category_sales.values()) - min(category_sales.values())
    else:
        performance_gap = 0

    # =========================
    # REVENUE FALLBACK LOGIC
    # =========================

    # =========================
    # REVENUE FALLBACK (SMART DETECTION)
    # =========================

    total_revenue = 0
    avg_revenue = 0

    # Try pipeline first
    if filtered_revenue and filtered_revenue.get("total"):
        total_revenue = filtered_revenue.get("total")
        avg_revenue = filtered_revenue.get("avg", 0)

    else:
        # Detect price column dynamically
        possible_price_cols = ["unit_price", "price", "selling_price", "Unit Price"]

        price_col = None
        for col in possible_price_cols:
            if col in df.columns:
                price_col = col
                break

        if price_col and "units_sold" in df.columns:
            df["revenue"] = df["units_sold"] * df[price_col]
            total_revenue = df["revenue"].sum()
            avg_revenue = df["revenue"].mean()
        else:
            print("⚠️ No price column found. Revenue cannot be calculated.")
   
    def format_currency(value):
        try:
            return f"₹{float(value):,.2f}"
        except:
            return "₹0.00"


    # months num to str 

    def convert_month_numbers(text):
        month_map = {
            "1": "January", "2": "February", "3": "March",
            "4": "April", "5": "May", "6": "June",
            "7": "July", "8": "August", "9": "September",
            "10": "October", "11": "November", "12": "December"
        }

        if "Peak sales months are" in text:
            numbers = text.split("are")[-1].strip().split(",")

            month_names = []
            for num in numbers:
                num = num.strip()
                if num in month_map:
                    month_names.append(month_map[num])

            if month_names:
                return f"Peak sales months are {', '.join(month_names)}."

        return text
    
    insights = result.get("insights", [])

    # Convert insights
    insights = [convert_month_numbers(i) for i in insights]

    # =========================
    # REPORT OBJECT
    # =========================
    report = {
        "title": f"Analytics Report: {job.get('filename', '')}",

        "executive_summary": f"Processed {row_count} rows using {job.get('operation', '')} mode.",

        "operation": job.get("operation", ""),
        "status": job.get("status", ""),

        "sections": {
            "dataset_overview": [
                f"Rows used in analysis: {row_count}",
                f"Columns found in dataset: {column_count}",
                f"Categories: {category_count}",
                f"Regions: {region_count}"
            ],

            "preprocessing": [
                "Duplicate rows removed",
                "Missing values handled using imputation",
                "Outliers detected and treated",
                "Date columns standardized",
                "New features created (month, region, category)",
                "Data validated for consistency"
            ],

            "mode_sections": [
                {
                    "title": "Key Metrics",
                    "items": [
                        f"Total Sales: {int(total_sales)}",
                        f"Average Sales: {round(avg_sales, 2)}",
                        f"Top Category: {top_category}",
                        f"Top Region: {top_region}",
                        f"Category Count: {category_count}",
                        f"Region Count: {region_count}",
                        f"Performance Gap: {int(performance_gap)}",
                        f"Business Health: Stable" if performance_gap < 10000 else "High Variance"
                    ]
                },

                {
                    "title": "Sales Distribution",
                    "items": [
                        f"Top Category: {top_category}",
                        f"Top Region: {top_region}",
                        f"Lowest Category: {lowest_category}"
                    ]
                }
            ]
        },

        "insights": insights,
        "recommendations": result.get("recommendations", []),

        "dashboard": {
            "kpis": [
                {"label": "Total Sales", "display_value": int(total_sales)},
                {"label": "Average Sales", "display_value": round(avg_sales, 2)},
                {"label": "Total Revenue", "display_value": format_currency(result.get("filtered_revenue", {}).get("total", 0))},
                {"label": "Avg Revenue", "display_value": format_currency(result.get("filtered_revenue", {}).get("avg", 0))}
            ],
            "charts": []
        }
    }

    return render_template("report.html", job=job, report=report)


@analysis_bp.route("/history")
@login_required
def history():
    jobs = list_jobs(user_id=current_user.get_id())
    return render_template("history.html", jobs=jobs)
