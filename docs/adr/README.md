# Architecture decision records

Implementation-time decisions for FinGuard. Each record names an owner, the reason and the trigger that would make us revisit it (backlog item F-01). The product and design rationale lives in the [blueprint](../../fintech-guardrails-blueprint/README.md); these records capture how the code realises it.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-modular-monolith.md) | Modular monolith: one Python backend, API + worker processes, separate Next.js web app | Accepted |
| [0002](0002-money-and-digests.md) | Money as integer minor units; canonical JSON + SHA-256 digests computed server-side | Accepted |
| [0003](0003-tenant-isolation.md) | Composite `(organization_id, id)` keys, repository scoping, PostgreSQL RLS | Accepted |
| [0004](0004-durable-jobs.md) | PostgreSQL-backed jobs and outbox with leases instead of a broker | Accepted |
| [0005](0005-ai-boundary.md) | AI is bounded assistance behind typed adapters; it never decides or executes | Accepted |
| [0006](0006-simulated-actions.md) | First release executes payments only against a simulator through the M5 gateway | Accepted |

## Data classification

| Class | Examples | Handling |
|---|---|---|
| Restricted | Beneficiary bank details, credentials, provider secrets | Encrypted at rest; never logged; never sent to model providers |
| Confidential | Invoices, bank rows, vendor records, findings, approvals | Tenant-scoped; private object storage; minimised before model calls |
| Internal | Job metadata, trace IDs, rule codes, reason codes | May appear in redacted operational logs |
| Public | Product documentation, synthetic fixtures | No restriction |

## Environments

| Environment | Identity | Data | Providers |
|---|---|---|---|
| `development` | Development identity stub (`X-Dev-User` header), only when `FINGUARD_ENV=development` | Synthetic fixtures only | Local object store, fake model, payment simulator |
| `test` | Same stub, created per test | Generated per test | Fakes only |
| `staging` | OIDC (Cognito) — stub refuses to start | Synthetic or authorised minimised data | Evaluated adapters; payment simulator |
| `production` | OIDC (Cognito) — stub refuses to start | Customer data under signed terms | Live connectors stay disabled until their release gate |
