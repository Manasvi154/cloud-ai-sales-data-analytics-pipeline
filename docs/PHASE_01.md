# Phase 1: Event-Driven Ingestion Foundation

## 1) Architecture Explanation
Phase 1 now provides a fully automated ingestion start for every uploaded dataset.

Execution path:
`Flask Upload -> S3 raw/uploads/ -> S3 Event -> Lambda starter -> Step Functions -> DynamoDB status/events`

Design goals implemented:
- No manual runtime trigger after upload.
- Job state persisted for UI polling.
- Event timeline available for progress page.
- Clear contracts so later phases (Glue/SageMaker/LLM/QuickSight) can plug in without redesign.

## 2) Folder Structure Additions
```text
app/
  services/
    pipeline_service.py              # mode-aware launcher (stub/aws)
infra/
  cloudformation/
    phase1_event_driven_pipeline.yaml
  scripts/
    deploy_phase1.ps1
tests/
  test_phase1_pipeline_flow.py
```

## 3) Code Generation
Implemented in this phase:
- Upload route now starts pipeline via `pipeline_service` instead of directly using in-memory stub.
- `pipeline_service` supports:
  - `PIPELINE_MODE=stub` (local development)
  - `PIPELINE_MODE=aws` (S3 + DynamoDB + Step Functions)
- Job status API added:
  - `GET /analysis/api/jobs/<job_id>`
- Processing page now polls status API and auto-redirects to results on success.
- CloudFormation stack added for:
  - S3 bucket with upload prefix notification
  - DynamoDB jobs/events tables
  - S3-trigger Lambda
  - status updater Lambda
  - Phase 1 Step Functions state machine
- PowerShell deploy script added to deploy stack and auto-update `.env`.

## 4) Required Commands
Local setup:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
python run.py
```

Automated Phase 1 AWS deployment:
```powershell
powershell -ExecutionPolicy Bypass -File infra\scripts\deploy_phase1.ps1
```

Test suite:
```powershell
python -m pytest -q
```

## 5) Environment Contract
Minimum AWS mode variables (auto-populated by deploy script):
- `PIPELINE_MODE=aws`
- `PIPELINE_START_MODE=s3_event`
- `S3_BUCKET_DATASETS=<stack output>`
- `DYNAMODB_TABLE_JOBS=<stack output>`
- `DYNAMODB_TABLE_EVENTS=<stack output>`
- `STEP_FUNCTION_ARN=<stack output>`
- `LAMBDA_TRIGGER_NAME=<stack output>`
- `S3_RAW_UPLOAD_PREFIX=raw/uploads`

## 6) Data Contracts
### Upload metadata stored in S3 object metadata
- `job-id`
- `user-id`
- `operation`
- `description`
- `original-filename`

### DynamoDB jobs record
```json
{
  "job_id": "uuid",
  "user_id": "uuid",
  "filename": "sales.csv",
  "operation": "regression",
  "description": "optional user prompt",
  "status": "UPLOADED|RUNNING|ORCHESTRATION_STARTED|SUCCEEDED|FAILED",
  "stage": "S3_UPLOAD_COMPLETED|LAMBDA_TRIGGERED|STEP_FUNCTIONS_STARTED|PHASE_1_COMPLETED",
  "s3_input_bucket": "bucket-name",
  "s3_input_key": "raw/uploads/<job_id>/sales.csv",
  "execution_arn": "arn:aws:states:...",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

### DynamoDB events record
```json
{
  "job_id": "uuid",
  "event_ts": "ISO8601",
  "status": "RUNNING",
  "stage": "LAMBDA_TRIGGERED",
  "message": "S3 event received by Lambda."
}
```

## 7) Validation Checklist
1. Upload a CSV via `/dataset/upload`.
2. Confirm object appears in `s3://<bucket>/raw/uploads/<job_id>/`.
3. Confirm Lambda starter logs show Step Functions execution started.
4. Confirm job row in DynamoDB updates from `UPLOADED` -> `ORCHESTRATION_STARTED` -> `SUCCEEDED`.
5. Confirm processing page updates status automatically and navigates to results.
