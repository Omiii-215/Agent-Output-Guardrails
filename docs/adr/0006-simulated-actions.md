# ADR 0006 — Simulated execution through one gateway

- **Status:** Accepted
- **Owner:** Platform engineering
- **Blueprint:** `04-low-level-design.md` §6–8, diagrams 06 and 07

## Decision

- Every consequential action follows **proposal → preflight evaluation → approval request → independent decisions → intent → reservation → execution → reconciliation**.
- Proposals are frozen by the server; their digest is computed server-side. Approval requests and intents bind to that exact digest. Changing a material field requires a new proposal.
- The first release accepts only `mode = SIMULATED`. The simulator implements the same state machine as a future provider (`ACCEPTED`, `FAILED`, `UNKNOWN`, `SETTLED`) including lost responses and duplicate webhooks.
- `UNKNOWN` keeps the reservation and the stable provider idempotency key; status reconciliation resolves it. No retry path creates a fresh transfer.
- Simulation is labelled in the API, UI and audit records.

## Revisit when

A live provider integration passes concurrency, status-recovery, security and customer-authority gates.
