from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from app.services.pipeline_stub import get_job, list_jobs
from app.services.report_service import generate_report_markdown

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")

from app.services.report_service import generate_dashboard_data
import os

@analysis_bp.route("/dashboard/<job_id>")
@login_required
def dashboard(job_id: str):
    job = get_job(job_id)
    if not job:
        abort(404)

    # Path to processed dataset
    processed_folder = "data/processed"

    files = [f for f in os.listdir(processed_folder) if f.endswith("_processed.csv")]

    latest_file = max(
        [os.path.join(processed_folder, f) for f in files],
        key=os.path.getctime
    )

    processed_path = latest_file

    chart_data = generate_dashboard_data(processed_path)

    return render_template(
        "dashboard.html",
        job=job,
        chart_data=chart_data
    )

@analysis_bp.route("/processing/<job_id>")
@login_required
def processing_status(job_id: str):
    job = get_job(job_id)
    if not job:
        abort(404)
    return render_template("processing.html", job=job)


@analysis_bp.route("/results/<job_id>")
@login_required
def results(job_id: str):
    job = get_job(job_id)
    if not job:
        abort(404)
    return render_template("results.html", job=job)


@analysis_bp.route("/report/<job_id>")
@login_required
def report(job_id: str):
    job = get_job(job_id)
    if not job:
        abort(404)
    report_body = generate_report_markdown(job)
    return render_template("report.html", job=job, report_body=report_body)


@analysis_bp.route("/history")
@login_required
def history():
    jobs = list_jobs(user_id=current_user.get_id())
    return render_template("history.html", jobs=jobs)
