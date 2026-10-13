# ADR 0001 — Modular monolith

- **Status:** Accepted
- **Owner:** Platform engineering
- **Blueprint:** `02-system-architecture.md` §3, `04-low-level-design.md` §1

## Decision

One Python codebase (`backend/`) holds the shared platform (identity, evidence, cases, policies, approvals, actions, audit) and the workflow modules (`backend/modules/*`). It is deployed as two processes:

- `apps/api` — FastAPI request handling. Route handlers validate input and call services; they never mutate financial tables directly.
- `apps/worker` — claims durable jobs (extraction, evaluation, imports, execution, exports).

`apps/web` is a separate Next.js application that talks only to the API.

Module rules:

- Workflow modules implement the `ModuleEvaluator` protocol (`validate_inputs`, `evaluate`) and own their domain tables.
- M5 (agent payment control gateway) is `backend/actions/`, shared by every module. `backend/adapters/payments/` contains transport only.
- Modules call each other through services or committed outbox events, never by writing each other's tables.

## Reason

Shared transactions for decision + approval + outbox, one deployment to operate, and a team of one or two builders.

## Revisit when

Measured load, fault isolation or a customer data boundary justifies splitting a component. Document processing and live execution are the likely first candidates.
