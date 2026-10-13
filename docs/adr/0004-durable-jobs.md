# ADR 0004 — Durable jobs and outbox in PostgreSQL

- **Status:** Accepted
- **Owner:** Platform engineering
- **Blueprint:** `02-system-architecture.md` §9, `04-low-level-design.md` §9

## Decision

- A business state change and its follow-up `job` / `outbox_event` rows are written in the same transaction.
- Workers claim jobs with `FOR UPDATE SKIP LOCKED` (PostgreSQL) in a short transaction, receive a `lease_token` and `lease_until`, and may complete a job only while their token is current.
- Transient failures retry with exponential backoff and jitter up to `max_attempts`, then move to `DEAD` for visible operator action. Invalid input and authorization failures are not retried.
- A reaper returns jobs with expired leases to the ready queue.
- Consumers are idempotent; event receipts are unique per `(consumer, organization_id, event_id)`.

## Reason

Recoverable work with a single data service. No in-process background task carries financial state.

## Revisit when

Queue contention, backlog or long-running workflow complexity is measured to exceed what the table queue handles.
