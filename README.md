# FinGuard — evidence and control platform for AI-assisted financial work

FinGuard is a working name. This repository implements the first release described in the [FinGuard blueprint](fintech-guardrails-blueprint/README.md): invoice preflight, one-to-one reconciliation investigation and **simulated** payment controls, built on a shared control platform that the other five modules will reuse.

> Status: prototype on synthetic data. No live provider integration, deployment, customer or performance result is claimed.

## Layout

```text
apps/            api (FastAPI), worker (job runner), web (Next.js)
backend/         shared platform + workflow modules (modular monolith)
docs/adr/        architecture decision records
fintech-guardrails-blueprint/   product, architecture and design blueprint
```

See [docs/adr](docs/adr/README.md) for the decisions that shape the code.
