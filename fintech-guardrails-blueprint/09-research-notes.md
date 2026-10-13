# Research provenance and open assumptions

Prepared 9–10 October 2026.

## How to interpret the evidence

The design combines primary technical documentation, official vendor descriptions, and a small number of first-person developer accounts. These have different evidentiary value:

- Official API documentation supports described API behavior and constraints.
- Vendor product pages establish what a vendor publicly describes; they do not independently establish performance or fit for a particular customer.
- Developer accounts provide implementation experience and questions to test, rather than a representative survey or a security guarantee.
- Product positioning, schedules, prices, pilot thresholds, staffing and economic examples in this package are our proposals. They are explicitly unvalidated.

Competitor facts are cited individually in [the comparison](07-competition-and-positioning.md). Technical behaviors are linked in the HLD, LLD and stack documents. No private customer files were used for market research.

## Primary evidence supporting the problem

- [Bank of England/FCA 2024 AI survey](https://www.bankofengland.co.uk/report/2024/artificial-intelligence-in-uk-financial-services-2024): financial-sector adoption and perceived data/security concerns. The sample is UK-regulated respondents; it does not establish India's addressable market.
- [NIST Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf): risks from unsupported generated content and the need for evaluation appropriate to the application.
- [FATF digital transformation work](https://www.fatf-gafi.org/en/publications/Digitaltransformation/Digital-transformation.html): technology opportunities and constraints around financial-crime work. It is not an endorsement of this platform.

## Community Wisdom

The DevRelay research connector was not signed in. Publicly accessible DEV pages were used instead; this did not require account access. This is a small evidence base, and no claim of broad community consensus is made.

### 🌐 Community Wisdom: [Building Reliable Agents with the Transactional Outbox Pattern and Redis Streams](https://dev.to/redis/building-reliable-agents-with-the-transactional-outbox-pattern-and-redis-streams-45e6)

> **Source**: [Ricardo Ferreira](https://dev.to/riferrei), writing for Redis
> **Tags**: `agents`, `redis`, `ai`, `eventdriven`
>
> The author emphasizes committing state and pending work together, while still handling retries, retention and duplicate effects. The visible discussion includes supportive handoff-failure examples; it does not establish comparative benchmarks. Our design uses the same atomicity principle in PostgreSQL, where the business records already live, without adding Redis initially.
>
> 🔗 [Read Full Discussion](https://dev.to/redis/building-reliable-agents-with-the-transactional-outbox-pattern-and-redis-streams-45e6)

### 🌐 Community Wisdom: [I Built a Multi-Tenant CRM with PostgreSQL Row-Level Security — Here's What I Learned](https://dev.to/ashwin31/i-built-a-multi-tenant-crm-with-postgresql-row-level-security-heres-what-i-learned-27c5)

> **Source**: [Aswani Kumar](https://dev.to/ashwin31)
> **Tags**: `django`, `opensource`, `webdev`, `crm`
>
> This first-person account describes the operational tradeoffs behind shared-schema row-level security. The page showed no comments when checked. Its broad isolation claims require qualification: PostgreSQL owners, superusers and bypass roles have special behavior. Our design therefore requires non-owner runtime roles, transaction-local tenant context and tests beyond database queries.
>
> 🔗 [Read Full Discussion](https://dev.to/ashwin31/i-built-a-multi-tenant-crm-with-postgresql-row-level-security-heres-what-i-learned-27c5)

The database design follows the primary [PostgreSQL row-security documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), and reliable-work design is also supported by [AWS transactional outbox guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html). Community anecdotes do not override either source.

## Limits and validation still required

1. No interviews or pilots establish demand for this exact product or price.
2. Competitor feature availability, regional eligibility, service terms and prices require direct evaluation before purchasing or making comparisons.
3. No deployed system has been benchmarked. Performance/recovery objectives are proposed acceptance targets.
4. No jurisdiction-specific compliance determination has been made; the actual entity, financial activity, data flow and customer requirements must be scoped.
5. Model/OCR quality, region routing, retention terms and cost must be verified for the selected configuration and representative data.
6. No test suite can demonstrate universal fraud prevention or zero error. Pilot findings must state their population, sample size, exclusions and uncertainty.

## Documentation review boundary

The package is reviewed for consistent scope, terminology, file links, code fences and embedded JSON examples. The diagrams and pseudocode express a proposed design. Application execution, schema migration execution, production security tests and cloud deployment validation belong to the implementation phase.
