# Automated Cloud Data Analytics Platform

Production-style cloud analytics platform built with Flask + AWS services.  
Goal: user uploads dataset once, selects analysis, and the system handles pipeline execution end-to-end.

## Current Status
- Phases completed:
  - `Phase 1 - Event-driven ingestion foundation (S3 -> Lambda -> Step Functions)`
  - `Phase 2 - Frontend UI Framework Hardening`
  - `Phase 3 - Authentication + OTP Verification`
- Local flow works with a stub orchestration engine.
- AWS ingestion foundation is now automated via CloudFormation + deployment script.
- Glue, SageMaker, LLM insights, and QuickSight phases are still pending.

## Tech Stack
- Frontend: Flask + Jinja + TailwindCSS + JS animations
- Backend: Python Flask APIs
- Auth: Flask-Login + Flask-Bcrypt + OTP email verification (implemented with local persistence)
- Database: DynamoDB (target, not yet wired in Phase 1)
- Cloud: S3, Lambda, Step Functions, Glue, Athena, SageMaker, QuickSight
- Data validation: Great Expectations (planned)
- ML: Linear Regression, Random Forest, Prophet, Isolation Forest (planned)
- GenAI Insight Engine: narrative business recommendations (planned)

## Architecture
See full architecture doc: [docs/architecture.md](docs/architecture.md)

High-level pipeline:
`Dataset Upload -> S3 -> Step Functions -> Lambda -> Glue -> Athena -> Feature Engineering -> SageMaker -> GenAI -> QuickSight -> API Response`

## Repository Layout
```text
app/
  routes/         # Flask blueprints
  services/       # AWS adapters + pipeline/report services
  templates/      # Jinja pages + reusable macros
  static/         # CSS/JS
docs/
  architecture.md
  PHASE_01.md
  PHASE_02.md
  PHASE_03.md
  MANASVI_PIPELINE_RUNBOOK.md
infra/
  stepfunctions/
  lambda/payload_examples/
  athena/
tests/
run.py
requirements.txt
DevInstructions.txt
ToDo.txt
MANASVI_CODEX_CONTEXT.md
manasvi.md
```

## Local Setup
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env
python run.py
```

App URL: `http://127.0.0.1:5000`

## Run Tests
```powershell
python -m pytest -q
```

## Required AWS Prep
1. Configure AWS credentials (`aws configure`) for an IAM principal that can deploy CloudFormation + IAM + Lambda + Step Functions + DynamoDB + S3.
2. Deploy the Phase 1 stack (fully automated):
```powershell
powershell -ExecutionPolicy Bypass -File infra\scripts\deploy_phase1.ps1
```
3. The script auto-updates `.env` with stack outputs and enables AWS pipeline mode.

## Transfer Pack For Manasvi
- [MANASVI_CODEX_CONTEXT.md](MANASVI_CODEX_CONTEXT.md)
- [manasvi.md](manasvi.md)
- [docs/MANASVI_PIPELINE_RUNBOOK.md](docs/MANASVI_PIPELINE_RUNBOOK.md)

## Phase Documents
- [docs/PHASE_01.md](docs/PHASE_01.md)
- [docs/PHASE_02.md](docs/PHASE_02.md)
- [docs/PHASE_03.md](docs/PHASE_03.md)
- [docs/MANASVI_PIPELINE_RUNBOOK.md](docs/MANASVI_PIPELINE_RUNBOOK.md)

## Complete Build Guide
- [FULL_PROJECT_CLICK_BY_CLICK.txt](FULL_PROJECT_CLICK_BY_CLICK.txt)

## Phase Roadmap
1. S3 upload + Lambda trigger + Step Functions start
2. Glue ETL and data quality pipeline
3. Baseline ML training (Linear Regression)
4. Decision engine and task routing
5. LLM-driven insight generation
6. QuickSight dashboards and embedding
7. Full retries, alarms, and production hardening

## Contributors
- Kunal: Frontend, ML models, SageMaker, API integration
- Manasvi: AWS pipeline, Lambda, Step Functions, Glue, Athena, IAM setup
