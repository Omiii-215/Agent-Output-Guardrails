# Infrastructure

Nothing in this repository has been deployed. This folder holds what the local
stack needs and the intended pilot mapping from the
[architecture blueprint](../fintech-guardrails-blueprint/02-system-architecture.md).

## Local

`docker compose up --build` runs PostgreSQL 16, a one-shot migration job
(`scripts/db_bootstrap.py`), the API, the worker and the web app.
`postgres/init.sql` creates the `finguard_app` login; migrations create the
NOLOGIN `app_runtime` role with row-level security, and the bootstrap grants it
to the login. The owner credentials are used only for migrations.

## Pilot mapping (AWS, proposed `ap-south-1`)

| Component | Service | Notes |
|---|---|---|
| Web, API, worker | ECS Fargate (images from ECR) | Same backend image; worker runs `python -m apps.worker.main` |
| Database | RDS for PostgreSQL 16 | Private subnets, encryption, tested restore; runtime user ≠ owner |
| Documents/exports | Private S3 | Block Public Access; replace `LocalObjectStore` with an S3 adapter using presigned URLs |
| Identity | Cognito (OIDC) | Set `FINGUARD_OIDC_ISSUER/AUDIENCE`; the dev stub refuses to start outside development |
| Secrets | Secrets Manager + KMS | `FINGUARD_*_SECRET`, `FINGUARD_FIELD_ENCRYPTION_KEY` |
| AI | Bedrock via `BedrockModelProvider` | Model, inference profile and guardrail chosen after evaluation; no implicit cross-region inference |
| Observability | CloudWatch + OpenTelemetry | Trace IDs already propagate; logs pass through the redaction filter |

Terraform for these resources is deliberately not written yet: region, data
processing locations and customer requirements must be confirmed first
(backlog O-01/O-02). Live payment connectors remain disabled (ADR 0006).
