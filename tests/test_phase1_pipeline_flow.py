from io import BytesIO
from pathlib import Path
from uuid import uuid4

from app import create_app


def _build_test_app(monkeypatch):
    db_dir = Path("instance/test_dbs")
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"phase1_pipeline_{uuid4().hex}.db"

    app = create_app(
        {
            "TESTING": True,
            "AUTH_DB_PATH": str(db_path),
            "OTP_RESEND_COOLDOWN_SECONDS": 0,
            "POST_UPLOAD_PAGES_ENABLED": True,
            "PIPELINE_MODE": "stub",
        }
    )
    monkeypatch.setattr("app.routes.auth.generate_otp_code", lambda: "123456")
    monkeypatch.setattr(
        "app.routes.auth.send_otp_email",
        lambda email, code: (True, "OTP email sent successfully."),
    )
    return app


def _login_verified_user(client, email: str):
    client.post(
        "/auth/register",
        data={"email": email, "password": "StrongPass123"},
        follow_redirects=True,
    )
    client.post(
        "/auth/verify",
        data={"email": email, "otp": "123456"},
        follow_redirects=True,
    )


def test_upload_creates_job_and_status_api_returns_payload(monkeypatch):
    app = _build_test_app(monkeypatch)
    client = app.test_client()
    _login_verified_user(client, email="phase1-flow@example.com")

    upload_response = client.post(
        "/dataset/upload",
        data={
            "operation": "regression",
            "description": "Phase 1 automated orchestration test",
            "dataset": (BytesIO(b"feature,target\n1,3\n2,5\n"), "phase1.csv"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )

    assert upload_response.status_code == 302
    location = upload_response.headers.get("Location", "")
    assert "/analysis/processing/" in location
    job_id = location.rsplit("/", 1)[-1]

    status_response = client.get(f"/analysis/api/jobs/{job_id}")
    assert status_response.status_code == 200

    payload = status_response.get_json()
    assert payload["job"]["job_id"] == job_id
    assert payload["job"]["status"] == "SUCCEEDED"
    assert payload["is_terminal"] is True
    assert payload["results_url"].endswith(f"/analysis/results/{job_id}")
