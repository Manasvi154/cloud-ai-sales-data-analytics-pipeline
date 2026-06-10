# Automated Cloud Data Analytics Platform

Production-style cloud analytics platform built with Flask + AWS services.  
Goal: user uploads dataset once, selects analysis, and the system handles pipeline execution end-to-end.

## Current Status
- Phases completed:
  - `Phase 1 - Architecture + Repo Setup`
  - `Phase 2 - Frontend UI Framework Hardening`
  - `Phase 3 - Authentication + OTP Verification`
- Local flow works with a stub orchestration engine.
- AWS orchestration wiring is planned for upcoming phases.

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

## Phase Roadmap
1. Architecture and repo setup
2. Frontend UI framework hardening
3. Authentication + OTP verification
4. Dataset upload + storage contracts
5. AWS integration (S3 + Step Functions + Lambda)
6. ML training pipeline (SageMaker)
7. GenAI insight engine
8. Dashboard visualization (QuickSight embedding)
9. Full automation orchestration + retries/monitoring
10. Report generation (PDF/CSV)
11. Deployment + production hardening

## Contributors
- Kunal: Backend, ML models, SageMaker, API integration
- Manasvi: Frontend, AWS pipeline, S3, IAM setup
