# FinGuard: product, engineering and startup blueprint

Prepared 9–10 October 2026. **FinGuard is a working name only.**

This package defines a proposed single web application with eight financial workflow modules, its architecture and implementation contracts, and a route from prototype to a startup. It is a design package: no working application, live provider integration, cloud deployment, paying customer, or performance result is claimed.

## Start here

**Visual companion:** [16 diagram images and editable sources](diagrams/README.md) · [Offline image gallery](diagrams/index.html) · [Download all diagrams](finguard-diagrams.zip).

**Product:** a shared evidence and control platform for AI-assisted financial work.

**Initial customer hypothesis:** India-based midsize B2B distributors/wholesalers whose finance teams review invoices and reconcile bank/accounting records.

**Initial buyer:** CFO, finance head or controller. **Daily users:** accounts-payable staff, accountants and financial reviewers.

**First release:** invoice checks, one-to-one reconciliation investigation, and simulated payment approvals. All eight modules are designed; the other five are enabled only after separate customer and domain validation.

**Value to prove:** less review effort, fewer material errors, reliable evidence, and clear ownership of decisions at an economically viable cost.

**Important competitive finding:** established products already offer AI summaries, rules, approvals and audit records. The opportunity must be demonstrated for a specific buyer and integration combination. No claim of market superiority is established by this plan.

## Map to the requested deliverables

| Requested item | Document | What is inside |
|---|---|---|
| 1. A proper problem statement for all features in one app | [Product and problem](01-product-and-problem.md) | Unified problem statement, root causes, eight module problems, requirements, acceptance conditions and scope |
| 2. System architecture and high-level design | [System architecture / HLD](02-system-architecture.md) | Context and container diagrams, data flows, module boundaries, cloud mapping, trust boundaries and recovery targets |
| 3. Technologies and overall stack | [Technology stack](03-technology-stack.md) | Specific frontend/backend/data/AI/cloud/testing choices, rationale, tradeoffs, costs and deferred decisions |
| 4. Low-level design | [LLD and contracts](04-low-level-design.md) | Data model, API contracts, policy structure, states, permissions, transactions, idempotency, retries and illustrative SQL |
| 5. High-level design | [System architecture / HLD](02-system-architecture.md) | Combined with item 2 so there is one authoritative HLD |
| 6. Consumer and target-buyer flows | [User and buyer flows](05-user-and-buyer-flows.md) | Buyer journey, staff screens, onboarding, approval roles, indirect supplier/applicant/customer correction flows |
| 7. Competitors and how we could differentiate | [Competition and positioning](07-competition-and-positioning.md) | Dated official-source comparisons, existing alternatives, proposed advantage and the evidence needed to prove it |
| From project to startup | [Startup roadmap](06-startup-roadmap.md) | Discovery, pilot design, pricing experiments, unit economics, first-year stage gates, team and fundraising evidence |
| Detailed implementation | [Implementation plan](08-implementation-plan.md) | Build order, dependencies, issue-ready backlog, tests, release gates and first ten work sessions |
| Research provenance and limitations | [Research notes](09-research-notes.md) | Primary evidence, developer implementation perspectives, unresolved assumptions and verification boundary |

Recommended reading order: product → buyer flows → architecture → stack → LLD → implementation → competition → startup roadmap. A founder deciding whether to invest can read product, competition and startup roadmap first.

## The eight modules

1. Invoice and payment preflight.
2. Reconciliation investigation.
3. Anti-money-laundering investigation evidence.
4. Chargeback evidence preparation.
5. Agent payment control gateway.
6. Loan underwriting evidence validation.
7. Collections/customer communication review.
8. Customer/business verification review (KYC/KYB).

They share identity, permissions, evidence records, policy versions, review cases, approvals, audit history and an action gateway. Each module still has its own rules, source requirements, specialist integrations and validation set. An invoice case does not automatically run a lending or AML evaluation.

## Architectural decisions in plain words

| Decision | Meaning |
|---|---|
| One application, modular backend | The product has one login and consistent workflows; modules remain independently understandable and testable |
| AI assists with reading and explanation | Financial calculations, authorization and execution depend on explicit application controls |
| Records keep their history | Corrections create new versions; reviewers can reconstruct what was known when a decision was made |
| Approval applies to an exact proposal | A changed amount, beneficiary, policy or authority causes re-evaluation and required reapproval |
| Durable background work | A restart does not silently discard document processing or approved follow-up work |
| External actions can be uncertain | A timeout triggers status reconciliation; it does not justify sending a new payment |
| Two synthetic organizations in tests | Isolation is verified even before real customer onboarding |
| Customer systems stay authoritative initially | The first product reviews records and exports recommendations; its payment connector is a simulator |

## Implementation baseline

**Frontend:** Next.js, React, TypeScript, accessible components.

**Backend:** Python, FastAPI, Pydantic, SQLAlchemy and Alembic.

**Data and work:** PostgreSQL, private object storage, database-backed durable jobs/outbox, exact money types.

**AI/document processing:** pypdf and OCR adapters; bounded Bedrock model calls after evaluation; optional Textract; supplementary content controls.

**Pilot hosting proposal:** Docker containers on AWS ECS Fargate, RDS PostgreSQL, S3, Cognito, Secrets Manager/KMS, CloudWatch/OpenTelemetry. Mumbai is a proposed region, subject to actual customer requirements, service availability and data-processing routes.

**Quality:** unit/property tests, real PostgreSQL isolation/concurrency tests, provider contract tests, reviewed evaluation cases and Playwright user journeys.

Exact package/model versions and cloud costs are selected and measured during implementation. There is no requirement to buy cloud services to create the first local deterministic demo.

## Delivery and commercial sequence

For two experienced builders with accessible data, use a rough 12–16-week first-release/pilot planning range. A solo builder learning the stack should allow four to six months or longer. Both ranges are assumptions, and neither estimates the whole eight-module production suite.

1. Observe the current workflow and identify its buyer and baseline cost.
2. Build an end-to-end invoice review using fictional data.
3. Add reconciliation and a payment-control simulator with independent approvals.
4. Verify isolation, financial calculations, stale approvals, retries and recovery.
5. Run a defined paid historical/advisory pilot with agreed data and success criteria.
6. Measure actual user effort, errors, integration cost and willingness to pay.
7. Repeat with a similar customer before widening the product.
8. Add the next module only when the buyer, evidence and domain expertise justify it.

The startup roadmap contains illustrative rupee prices and unit-economics scenarios. They are experiments for discovery, not competitor prices, cloud quotes, market benchmarks or revenue forecasts.

## First implementation milestone

A user can upload a fictional invoice, inspect its extracted or manually entered fields beside the source, run three explicit checks, resolve an exception, obtain an independent simulated approval, and export a traceable review history. A second organization cannot access any of those records.

Build that milestone before extending the interface across all eight workflows. The first review session should reveal whether the product helps the intended user and which assumptions need revision.

## Outstanding decisions

- Confirm geography, customer segment, team capacity, and budget.
- Obtain representative authorized records and a domain reviewer.
- Choose the first supported accounting/bank export formats.
- Agree which fields require human verification and how beneficiary verification works.
- Agree the pilot's acceptance criteria, data handling, deployment and retention arrangements.
- Select model/OCR provider configurations using measured quality and cost.
- Obtain customer-specific requirements before any live financial action or regulated-domain deployment.

No customer interviews, provider procurement, outreach, or deployment were performed as part of preparing these documents.
