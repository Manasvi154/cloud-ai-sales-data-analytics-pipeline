import os


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

    # AWS resources
    S3_BUCKET_DATASETS = os.getenv("S3_BUCKET_DATASETS", "")
    S3_RAW_UPLOAD_PREFIX = os.getenv("S3_RAW_UPLOAD_PREFIX", "raw/uploads")
    S3_PROCESSED_PREFIX = os.getenv("S3_PROCESSED_PREFIX", "processed/glue")
    DYNAMODB_TABLE_USERS = os.getenv("DYNAMODB_TABLE_USERS", "analytics_users")
    DYNAMODB_TABLE_JOBS = os.getenv("DYNAMODB_TABLE_JOBS", "analytics_jobs")
    DYNAMODB_TABLE_EVENTS = os.getenv("DYNAMODB_TABLE_EVENTS", "analytics_events")
    STEP_FUNCTION_ARN = os.getenv("STEP_FUNCTION_ARN", "")
    LAMBDA_TRIGGER_NAME = os.getenv("LAMBDA_TRIGGER_NAME", "")
    ATHENA_WORKGROUP = os.getenv("ATHENA_WORKGROUP", "primary")
    GLUE_DATABASE = os.getenv("GLUE_DATABASE", "analytics_raw")
    SAGEMAKER_ROLE_ARN = os.getenv("SAGEMAKER_ROLE_ARN", "")
    QUICKSIGHT_NAMESPACE = os.getenv("QUICKSIGHT_NAMESPACE", "default")
    PIPELINE_MODE = os.getenv("PIPELINE_MODE", "stub").strip().lower()
    PIPELINE_START_MODE = os.getenv("PIPELINE_START_MODE", "s3_event").strip().lower()
    PIPELINE_JOBS_USER_GSI = os.getenv("PIPELINE_JOBS_USER_GSI", "gsi_user_created_at")
    PIPELINE_STATUS_POLL_SECONDS = int(os.getenv("PIPELINE_STATUS_POLL_SECONDS", "3"))
    PIPELINE_ALLOW_STUB_FALLBACK = _env_flag("PIPELINE_ALLOW_STUB_FALLBACK", True)

    # Email/OTP placeholders for Phase 3
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_SENDER = os.getenv("SMTP_SENDER", os.getenv("SMTP_USERNAME", "no-reply@data-automation.local"))

    # Local authentication persistence for pre-AWS phases
    AUTH_DB_PATH = os.getenv("AUTH_DB_PATH", "instance/data_automation.db")
    OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
    OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "45"))
    POST_UPLOAD_PAGES_ENABLED = _env_flag("POST_UPLOAD_PAGES_ENABLED", False)
