# ADR 0003 — Tenant isolation

- **Status:** Accepted
- **Owner:** Platform engineering / security
- **Blueprint:** `02-system-architecture.md` §8, `04-low-level-design.md` §4

## Decision

Isolation is enforced in layers, each tested with two synthetic organizations:

1. **Identity → membership.** The organization is resolved from a verified identity plus a server-side membership lookup. A client-supplied organization ID is never proof of membership.
2. **Keys.** Every tenant-owned table has a composite primary key `(organization_id, id)`; tenant-owned children reference parents through composite foreign keys, so a child cannot point at another tenant's parent.
3. **Repositories.** All tenant-owned reads go through `TenantSession` helpers that always filter by the verified organization. Cross-tenant lookups return `404`, not `403`, to avoid leaking existence.
4. **Database.** On PostgreSQL, migrations enable `FORCE ROW LEVEL SECURITY` with a policy on `current_setting('app.organization_id')`. The unit of work sets that value with `set_config(..., true)` (transaction-local). The runtime role is not the table owner and has no `BYPASSRLS`.
5. **Objects.** Object keys are prefixed with the organization ID, and download grants are re-authorised per request.

Tests run on SQLite by default (layers 1–3 and 5) and on PostgreSQL when `FINGUARD_TEST_DATABASE_URL` is set (adds layer 4).

## Revisit when

A contract requires dedicated tenant infrastructure.
