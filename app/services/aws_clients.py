from __future__ import annotations

import boto3
from botocore.config import Config as BotoConfig
from flask import current_app


def create_session():
    return boto3.session.Session(region_name=current_app.config["AWS_REGION"])


def get_clients() -> dict[str, object]:
    session = create_session()
    client_config = BotoConfig(
        retries={"max_attempts": 4, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60,
    )
    return {
        "s3": session.client("s3", config=client_config),
        "dynamodb": session.resource("dynamodb"),
        "stepfunctions": session.client("stepfunctions", config=client_config),
        "lambda": session.client("lambda", config=client_config),
        "glue": session.client("glue", config=client_config),
        "athena": session.client("athena", config=client_config),
        "sagemaker": session.client("sagemaker", config=client_config),
        "quicksight": session.client("quicksight", config=client_config),
    }
