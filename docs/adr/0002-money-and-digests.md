# ADR 0002 — Money and canonical digests

- **Status:** Accepted
- **Owner:** Platform engineering
- **Blueprint:** `04-low-level-design.md` §2, §6

## Decision

- Payable and settled amounts are signed integers in **minor units** plus an ISO 4217 currency code. The currency exponent comes from a fixed table (`INR`=2, `JPY`=0, `KWD`=3 …). Binary floating point is rejected at every boundary.
- Quantities, unit prices and tax rates are `Decimal`. Line totals are quantised once, with an explicit rounding mode (`ROUND_HALF_UP` by default, configurable per policy).
- API JSON carries minor-unit amounts as **strings** so JavaScript clients do not lose precision.
- Snapshots, policies and action proposals are serialised with a versioned canonical JSON algorithm (`canon-v1`: sorted keys, no insignificant whitespace, UTF-8, decimals/ints as strings) and hashed with SHA-256. The server computes every digest; a digest supplied by a client is an unknown field and is rejected.

## Reason

Exact, reproducible arithmetic and an approval that can be bound to one exact payload.

## Revisit when

Multicurrency customers need FX legs, or a provider requires a different canonical form for request signing.
