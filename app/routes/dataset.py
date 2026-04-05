from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services.pipeline_service import PipelineStartError, start_pipeline

dataset_bp = Blueprint("dataset", __name__, url_prefix="/dataset")


@dataset_bp.route("/operation")
@login_required
def operation_selection():
    return render_template("operation_select.html")


@dataset_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload_dataset():
    default_operation = request.args.get("operation", "")

    if request.method == "POST":
        uploaded_file = request.files.get("dataset")
        operation = request.form.get("operation", "").strip()
        description = request.form.get("description", "").strip()

        if not uploaded_file or uploaded_file.filename == "":
            flash("Please choose a dataset file.", "error")
            return redirect(url_for("dataset.upload_dataset"))

        if not operation:
            flash("Please select an operation.", "error")
            return redirect(url_for("dataset.upload_dataset"))

        if not current_app.config.get("POST_UPLOAD_PAGES_ENABLED", False):
            flash("Dataset accepted successfully.", "success")
            return redirect(url_for("dataset.upload_dataset", operation=operation))

        try:
            job_id = start_pipeline(
                filename=uploaded_file.filename,
                file_stream=uploaded_file.stream,
                operation=operation,
                description=description,
                user_id=current_user.get_id(),
                content_type=uploaded_file.mimetype or "",
            )
        except PipelineStartError as exc:
            current_app.logger.exception("Unable to start pipeline for uploaded dataset.")
            flash(str(exc), "error")
            return redirect(url_for("dataset.upload_dataset", operation=operation))

        flash("Dataset accepted. Analytics pipeline started.", "success")
        return redirect(url_for("analysis.processing_status", job_id=job_id))

    return render_template("upload.html", default_operation=default_operation)
