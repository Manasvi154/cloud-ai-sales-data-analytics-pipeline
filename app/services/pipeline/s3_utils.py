import boto3
import os
import time
from .logger import get_logger

logger = get_logger()
# AWS CREDENTIALS

AWS_ACCESS_KEY = "AKIAWRMEX7MKRZNDDBJY"
AWS_SECRET_KEY = "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"
AWS_REGION = "ap-south-1"

BUCKET_NAME = "retail-sales-analytics-pipeline"

# S3 CLIENT

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)


# UPLOAD FILE TO S3 WITH RETRY

def upload_file(local_path, s3_key, retries=3):

    attempt = 0

    while attempt < retries:

        try:

            logger.info(f"Uploading {local_path} to S3 -> {s3_key}")

            s3_client.upload_file(local_path, BUCKET_NAME, s3_key)

            logger.info(f"S3 upload successful: {s3_key}")

            return True

        except Exception as e:

            attempt += 1

            logger.warning(f"S3 upload failed (attempt {attempt}) : {str(e)}")

            time.sleep(2)

    logger.error(f"S3 upload failed after {retries} attempts")

    return False


# DOWNLOAD FILE FROM S3 WITH RETRY

def download_file(s3_key, local_path, retries=3):

    attempt = 0

    while attempt < retries:

        try:

            logger.info(f"Downloading {s3_key} from S3")

            s3_client.download_file(BUCKET_NAME, s3_key, local_path)

            logger.info("S3 download successful")

            return True

        except Exception as e:

            attempt += 1

            logger.warning(f"S3 download failed (attempt {attempt}) : {str(e)}")

            time.sleep(2)

    logger.error("S3 download failed after retries")

    return False

