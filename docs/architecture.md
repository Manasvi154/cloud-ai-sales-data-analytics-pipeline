# Cloud Analytics Platform Architecture

## End-to-End Flow
1. User registers/logs in.
2. User uploads dataset + selects operation.
3. Flask API uploads to S3 (`raw/uploads/<job_id>/...`) and writes initial job metadata.
4. S3 event triggers Lambda starter, which starts Step Functions and updates status records.
5. Step Functions orchestrates Lambda, Glue ETL, Athena SQL, feature engineering, and SageMaker training/inference.
6. Model outputs are transformed by the GenAI Insight Engine into business-readable recommendations.
7. QuickSight dashboard is generated/updated.
8. Final artifacts (insights, dashboard links, downloadable report) are returned to Flask.
9. User sees status, results, dashboard, and history.

## Primary AWS Data Path
`Upload -> S3 -> Lambda trigger -> Step Functions -> Glue -> Athena -> SageMaker -> GenAI -> QuickSight -> API response`

## System Components
- `Flask Web + API`: session/auth, uploads, status APIs, history, report pages.
- `DynamoDB`: users, job metadata, execution status, links to artifacts.
- `S3`: raw uploads, transformed datasets, model outputs, generated reports.
- `Step Functions`: orchestration backbone with retries and failure routing.
- `Lambda`: event handlers and control-plane functions.
- `Glue`: schema discovery, ETL jobs, catalog updates.
- `Athena`: ad-hoc/templated analytics queries.
- `SageMaker`: model training/inference jobs.
- `QuickSight`: BI dashboards and embeddings.
- `GenAI Insight Engine`: transforms numerical output into actionable narrative.

## Security Model (Target)
- IAM least privilege for each service role.
- App secrets in AWS Secrets Manager / Parameter Store.
- S3 bucket policies scoped to service roles and prefixes.
- Signed URLs for dataset/report access.
- Audit trail through CloudWatch + CloudTrail + DynamoDB job logs.

## Team Split
- `Kunal`: Frontend, ML models, SageMaker integration, API integration.
- `Manasvi`: AWS pipeline (Lambda, Step Functions, Glue, Athena), IAM policy setup.
- Mandatory handoff: Manasvi must provide Kunal IAM access with scoped permissions for integration/testing.

## Phase 1 Scope
- S3 upload contract from Flask UI/backend.
- Event-driven starter path: S3 -> Lambda -> Step Functions.
- Persistent job + event tracking in DynamoDB.
- Processing page status polling via API endpoint.
