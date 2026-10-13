# FinGuard — evidence and control platform for AI-assisted financial work

FinGuard is a working name. This repository implements the first release described in the [FinGuard blueprint](fintech-guardrails-blueprint/README.md): invoice preflight, one-to-one reconciliation investigation and **simulated** payment controls, built on a shared control platform that the other five modules will reuse.

> Status: prototype on synthetic data. No live provider integration, deployment, customer or performance result is claimed. Payments run against a simulator.

## What it does

```text
upload ─► quarantine & verify ─► extract (bounded AI, cited) ─► person confirms
   ─► frozen snapshot ─► deterministic policy checks ─► findings + evidence
   ─► proposal (server digest) ─► preflight ─► independent approval of that digest
   ─► intent ─► locked re-check + spend reservation ─► simulated execution
   ─► UNKNOWN? reconcile status, never resend ─► signed webhook ─► settled ─► audit export
```

| Area | Where | Guarantees tested |
|---|---|---|
| Tenancy | `backend/persistence`, `backend/identity` | Composite keys, PostgreSQL `FORCE ROW LEVEL SECURITY`, non-owner runtime role, 404 across tenants, membership re-checked every request |
| Evidence | `backend/evidence` | Hash/size/type/malware verification before parsing; signed short-lived grants; append-only evidence items |
| Policies | `backend/policies` | Typed declarative rules, regression scenarios, independent publisher, replayable evaluations; crashes are never a pass |
| M1 Invoices | `backend/modules/invoices` | Exact arithmetic, paid/open/similar duplicates, payee verification by a second person, versioned corrections |
| AI | `backend/ai`, `backend/adapters/models` | Schema-validated output, citations checked against source text, embedded instructions flagged, outage → manual entry |
| M5 Gateway | `backend/actions`, `backend/approvals` | Server-frozen payload digest, maker-checker, tiers, authority limits, expiry, staleness, emergency stop, no overspend under concurrency, lost responses reconciled without resubmission |
| M2 Reconciliation | `backend/modules/reconciliation` | Idempotent imports with lineage, exact one-to-one proposals only, exceptions for fees/splits/FX/ambiguity, one active allocation per row |
| Audit | `backend/telemetry/audit.py`, `backend/audit` | Append-only history, sealed purpose-scoped exports without restricted data |
| Web | `apps/web` | Reviewer UI typed from `contracts/openapi.json` |

Modules M3 (AML), M4 (chargebacks), M6 (underwriting), M7 (communications) and M8 (KYC/KYB) have input contracts and activation gates in `backend/modules/gated.py` but no evaluators, by design.

## Run it locally

Requirements: Python 3.12 with [uv](https://docs.astral.sh/uv/), Node 22.

```bash
uv sync
```

```bash
PYTHONPATH=. uv run python scripts/seed_demo.py
```

```bash
uv run uvicorn apps.api.main:app --port 8000
```

```bash
uv run python -m apps.worker.main
```

```bash
npm --prefix apps/web install && npm --prefix apps/web run dev
```

Open http://localhost:3000 and pick a persona (operator, approver, auditor, policy author/publisher, admin, or the second tenant's operator). Local development uses SQLite under `var/`; delete that folder to reseed.

With Docker instead (PostgreSQL with row-level security):

```bash
docker compose up --build
```

```bash
docker compose run --rm api python scripts/seed_demo.py
```

## Tests

```bash
uv run pytest
```

Runs against a real PostgreSQL 16 (embedded via `pgserver`, or `FINGUARD_TEST_DATABASE_URL` in CI) so row-level security, `SKIP LOCKED` claiming and concurrent reservations are exercised. `FINGUARD_TEST_BACKEND=sqlite uv run pytest` runs the same suite on SQLite (RLS and race tests skipped).

After API changes, regenerate the contract and client:

```bash
PYTHONPATH=. uv run python scripts/export_openapi.py && npm --prefix apps/web run gen:api
```

New migrations are generated against a fresh embedded PostgreSQL; add `rls.tenant_table(...)` for new tenant tables:

```bash
PYTHONPATH=. uv run python scripts/new_migration.py "describe change"
```

## Layout

```text
apps/api            FastAPI routes (thin: authenticate, validate, call services)
apps/worker         durable job runner
apps/web            Next.js reviewer app
backend/            shared platform + workflow modules (modular monolith)
contracts/          generated OpenAPI contract
migrations/         Alembic migrations incl. RLS policies and append-only triggers
infrastructure/     local Postgres init and the pilot AWS mapping
docs/adr/           architecture decision records
fintech-guardrails-blueprint/   product, architecture and design blueprint
```

See [docs/adr](docs/adr/README.md) for the decisions behind the code and [infrastructure](infrastructure/README.md) for deployment notes.
