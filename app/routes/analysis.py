from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from app.services.pipeline_service import get_job, get_job_events, list_jobs
from app.services.report_service import generate_report_markdown

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")


def _redirect_if_post_upload_pages_disabled():
    if not current_app.config.get("POST_UPLOAD_PAGES_ENABLED", False):
        flash(
            "This section is currently unavailable.",
            "info",
        )
        return redirect(url_for("dataset.upload_dataset"))
    return None


@analysis_bp.route("/processing/<job_id>")
@login_required
def processing_status(job_id: str):
    unavailable_redirect = _redirect_if_post_upload_pages_disabled()
    if unavailable_redirect:
        return unavailable_redirect
    job = get_job(job_id)
    if not job or job.get("user_id") != current_user.get_id():
        abort(404)
    events = get_job_events(job_id=job_id)
    return render_template(
        "processing.html",
        job=job,
        events=events,
        poll_seconds=current_app.config.get("PIPELINE_STATUS_POLL_SECONDS", 3),
    )


@analysis_bp.route("/api/jobs/<job_id>")
@login_required
def job_status_api(job_id: str):
    if not current_app.config.get("POST_UPLOAD_PAGES_ENABLED", False):
        return jsonify({"error": "Post-upload pages are disabled."}), 403

    job = get_job(job_id)
    if not job or job.get("user_id") != current_user.get_id():
        return jsonify({"error": "Job not found."}), 404

    status = (job.get("status") or "UNKNOWN").upper()
    is_terminal = status in {"SUCCEEDED", "FAILED"}
    payload = {
        "job": job,
        "events": get_job_events(job_id=job_id),
        "is_terminal": is_terminal,
        "results_url": url_for("analysis.results", job_id=job_id),
        "dashboard_url": url_for("analysis.dashboard", job_id=job_id),
        "report_url": url_for("analysis.report", job_id=job_id),
    }
    return jsonify(payload)


@analysis_bp.route("/results/<job_id>")
@login_required
def results(job_id: str):
    unavailable_redirect = _redirect_if_post_upload_pages_disabled()
    if unavailable_redirect:
        return unavailable_redirect
    job = get_job(job_id)
    if not job or job.get("user_id") != current_user.get_id():
        abort(404)
    if job.get("status") not in {"SUCCEEDED", "FAILED"}:
        flash("Pipeline is still running. Showing live progress instead.", "info")
        return redirect(url_for("analysis.processing_status", job_id=job_id))
    return render_template("results.html", job=job)


@analysis_bp.route("/dashboard/<job_id>")
@login_required
def dashboard(job_id: str):
    unavailable_redirect = _redirect_if_post_upload_pages_disabled()
    if unavailable_redirect:
        return unavailable_redirect
    job = get_job(job_id)
    if not job or job.get("user_id") != current_user.get_id():
        abort(404)
    if job.get("status") not in {"SUCCEEDED", "FAILED"}:
        flash("Dashboard is available after processing completes.", "info")
        return redirect(url_for("analysis.processing_status", job_id=job_id))
    return render_template("dashboard.html", job=job)


@analysis_bp.route("/report/<job_id>")
@login_required
def report(job_id: str):
    unavailable_redirect = _redirect_if_post_upload_pages_disabled()
    if unavailable_redirect:
        return unavailable_redirect
    job = get_job(job_id)
    if not job or job.get("user_id") != current_user.get_id():
        abort(404)
    if job.get("status") not in {"SUCCEEDED", "FAILED"}:
        flash("Report will be available after processing completes.", "info")
        return redirect(url_for("analysis.processing_status", job_id=job_id))
    report_body = generate_report_markdown(job)
    return render_template("report.html", job=job, report_body=report_body)


@analysis_bp.route("/history")
@login_required
def history():
    unavailable_redirect = _redirect_if_post_upload_pages_disabled()
    if unavailable_redirect:
        return unavailable_redirect
    jobs = list_jobs(user_id=current_user.get_id())
    return render_template("history.html", jobs=jobs)
