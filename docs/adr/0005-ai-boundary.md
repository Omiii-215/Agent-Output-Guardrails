# ADR 0005 — AI is bounded assistance

- **Status:** Accepted
- **Owner:** Platform engineering
- **Blueprint:** `02-system-architecture.md` §7, `03-technology-stack.md` §3, `04-low-level-design.md` §11

## Decision

- Model work is exposed only as named operations (`extract_invoice`, `summarize_findings`) with typed input/output schemas, size limits, timeouts and a recorded model/prompt version.
- Document text is untrusted data. Instructions embedded in a document ("ignore the approval policy") are flagged and never followed.
- Every extracted field must cite a locator that exists in the source; fabricated citations are rejected.
- Model output is a **suggestion**: it can pre-fill fields that a reviewer confirms, and explain findings that deterministic rules have already produced. It cannot change a policy outcome, grant a role or execute an action, and it holds no credentials.
- A model outage degrades extraction/explanations only. Missing critical fields hold the case; nothing silently passes.
- The default provider is a deterministic fake. The Bedrock adapter is selected by configuration only after evaluation.

## Revisit when

A validated use case needs semantic retrieval or a new bounded operation.
