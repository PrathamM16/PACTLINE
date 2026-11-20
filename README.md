# PACTLINE

Talk. Agree. Execute. Follow through.

Hackathon entry for Build with Agora, Bengaluru 2026, track: Real-Time Conversational AI Meets Agentic Workflows (solo).

## Sign-in is required
Register an account in the app first. See docs/SETUP.md, docs/TEST_REPORT.md and docs/FAQ_CHECK.md.

## What this repository contains today

This is a vertical slice, not the finished product. See docs/STATUS.md for the exact verified / unverified / not-built breakdown. Read it before the demo.

- backend/app/domain: commitment ledger with dispute and resolution history, approval gate, workflow state machine, webhook HMAC verification, audit log
- backend/app/devops: pipeline spec validation, Jenkinsfile generator and validator, approval-enforcing DevOps tools
- backend/app/integrations: Jenkins client, SonarQube Cloud client, Agora token and agent adapter
- backend/app/api/main.py: FastAPI application
- backend/app/database/models.py: SQLAlchemy models for PostgreSQL
- frontend: Angular standalone app with Voice room, Pipeline builder, Integrations pages
- render.yaml: Render blueprint (API, static site, PostgreSQL)

## Run the verified tests (no installs needed, Python 3.11+)

    cd backend
    python3 -m unittest discover -s tests -t .

## Deploy

See docs/DEPLOYMENT.md. Nothing in the deployed product requires your laptop, WSL or local Docker.
