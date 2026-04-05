from io import BytesIO
from pathlib import Path
from uuid import uuid4

from app import create_app


def _build_test_app(monkeypatch):
    db_dir = Path("instance/test_dbs")
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"auth_post_upload_pages_{uuid4().hex}.db"

    app = create_app(
        {
            "TESTING": True,
            "AUTH_DB_PATH": str(db_path),
            "OTP_RESEND_COOLDOWN_SECONDS": 0,
            "POST_UPLOAD_PAGES_ENABLED": False,
        }
    )
    monkeypatch.setattr("app.routes.auth.generate_otp_code", lambda: "123456")
    monkeypatch.setattr(
        "app.routes.auth.send_otp_email",
        lambda email, code: (True, "OTP email sent successfully."),
    )
    return app


def _login_verified_user(client):
    email = "post-pages@example.com"
    password = "StrongPass123"
    client.post(
        "/auth/register",
        data={"email": email, "password": password},
        follow_redirects=True,
    )
    client.post(
        "/auth/verify",
        data={"email": email, "otp": "123456"},
        follow_redirects=True,
    )


def test_upload_stays_on_when_post_upload_pages_are_disabled(monkeypatch):
    app = _build_test_app(monkeypatch)
    client = app.test_client()
    _login_verified_user(client)

    response = client.post(
        "/dataset/upload",
        data={
            "operation": "forecasting",
            "description": "upload flow check",
            "dataset": (BytesIO(b"col1,col2\n1,2\n"), "sample.csv"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Dataset accepted successfully." in response.data
    assert b"Upload Dataset" in response.data


def test_analysis_pages_redirect_when_post_upload_pages_are_disabled(monkeypatch):
    app = _build_test_app(monkeypatch)
    client = app.test_client()
    _login_verified_user(client)

    response = client.get("/analysis/history", follow_redirects=True)

    assert response.status_code == 200
    assert b"This section is currently unavailable." in response.data
    assert b"Upload Dataset" in response.data
