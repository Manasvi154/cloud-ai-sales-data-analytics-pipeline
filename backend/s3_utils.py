import boto3
import os

# AWS CREDENTIALS

AWS_ACCESS_KEY = "aceess_key"
AWS_SECRET_KEY = "secret_key"
AWS_REGION = "ap-south-1"

BUCKET_NAME = "retail-sales-analytics-pipeline"

# S3 CLIENT

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)


# UPLOAD FILE TO S3

def upload_file(local_path, s3_key):

    try:

        s3_client.upload_file(local_path, BUCKET_NAME, s3_key)

        print(f"Uploaded {local_path} to S3 -> {s3_key}")

    except Exception as e:

        print("S3 upload failed:", e)


# DOWNLOAD FILE FROM S3

def download_file(s3_key, local_path):

    try:

        s3_client.download_file(BUCKET_NAME, s3_key, local_path)

        print(f"Downloaded {s3_key} from S3")

    except Exception as e:

        print("S3 download failed:", e)

