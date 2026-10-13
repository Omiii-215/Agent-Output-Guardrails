# Technology stack and implementation choices

Planning date: 9 October 2026. These are recommended choices for the proposed product, not installed dependencies or verified cloud-account entitlements. Pin exact compatible versions when implementation begins and record them in lockfiles.

## 1. Recommended baseline

Use one repository and a **modular monolith**: one backend codebase with clear internal modules, deployed as an API process and a worker process. A separate Next.js web frontend calls that API. PostgreSQL is the source of truth for business records and durable work. This keeps transactions and operations manageable for a small team.

| Layer | Default choice | Purpose and reason | When to revisit |
|---|---|---|---|
| Web application | Next.js, React, TypeScript | Review tables, document views, policy forms, case detail, authenticated navigation | Only if team expertise strongly favors another mature framework |
| Styling/components | Tailwind CSS with accessible Radix/shadcn-style components | Consistent forms, dialogs, tables, keyboard behavior; customize deliberately | Audit accessibility rather than assuming a component library guarantees it |
| Forms and client validation | React Hook Form + Zod | Fast feedback for uploads, filters, corrections and policy settings | Server remains authoritative |
| Server data in UI | TanStack Query; generated TypeScript API types | Poll asynchronous job status; cache only within correct user/workspace boundaries | Add server events if polling traffic or UX warrants it |
| API and domain services | Python + FastAPI + Pydantic | Typed request contracts, document processing, explicit validation, OpenAPI | Do not add a second business backend in Next.js |
| Business calculations | Python Decimal + PostgreSQL NUMERIC or integer minor units | Exact arithmetic with explicit currency and rounding rules | Extend currency handling before multicurrency customers |
| Database access | SQLAlchemy + Alembic + PostgreSQL driver | Typed persistence and reviewed schema migrations | Prefer explicit transactions for critical paths |
| Durable jobs | PostgreSQL jobs/outbox + dedicated worker | Persist work alongside case changes; leases, retry limits, backoff, deduplication | Add a broker/workflow engine only after measured queue or workflow needs |
| Primary database | PostgreSQL locally; Amazon RDS for PostgreSQL in the pilot | Relational constraints, transactions, organization-scoped records and RLS | Dedicated customer deployment if justified by isolation requirements |
| Evidence storage | Local filesystem adapter for synthetic development; private Amazon S3 for pilot | Original files, exports, versioned evidence, controlled downloads | Separate archival retention from active evidence storage |
| Identity | OIDC adapter; Amazon Cognito user pool for pilot | Managed sign-in, MFA, federation path; app owns organization membership/roles | Buyer SSO requirements may change the IdP integration |
| PDF extraction | pypdf for digital text; rendered pages + Tesseract for local OCR experiments | Start with inexpensive local extraction and explicit review | Compare with Textract on customer documents; keep the adapter replaceable |
| Managed OCR option | Amazon Textract expense/document analysis | Candidate for invoices and receipts when evaluated accuracy justifies cost | Verify language/layout support, regional availability and per-page economics |
| AI provider | Amazon Bedrock behind a narrow model adapter | Structured extraction assistance and source-grounded drafting under one approved provider configuration | Select/pin a model only after quality, region and cost evaluation |
| Financial policy engine | Versioned, declarative JSON rules validated with Pydantic; explicit Python evaluators | Deterministic checks with readable reason codes and tests | OPA/Cedar for authorization policy if complexity warrants it; no need initially |
| Additional AI content controls | Bedrock Guardrails where useful, plus application data minimization and schema/source checks | Supplement content/PII/prompt-attack checks | Evaluate false positives by workflow; never substitute for payment authorization |
| Search | PostgreSQL full-text search and indexed metadata | Find cases, invoices, vendors and evidence within a tenant | Add vector retrieval only when a validated use case needs semantic search |
| Runtime/deployment | Docker Compose locally; ECS Fargate + ECR for cloud containers | Same application artifacts in development and cloud; scale API and workers separately | No Kubernetes needed for the initial operating model |
| Infrastructure definition | Terraform with reviewed plans and separate environment state | Repeatable networks, identities, storage, databases and services | Check provider versions and resource behavior before applying |
| Monitoring | OpenTelemetry + CloudWatch metrics/logs/alarms | Correlation IDs, queue lag, errors, latency, model/OCR costs, provider health | Export to another compatible observability platform as customer needs change |
| Secrets and encryption | AWS task roles, Secrets Manager and KMS for cloud | Short-lived service credentials and scoped access | Separate duties between application runtime and infrastructure administrators |
| Tests | pytest, Hypothesis, PostgreSQL integration tests, Vitest, Playwright, axe | Financial invariants, races, isolation, contract and full user-flow checks | Expand only around real risk and failures |
| Delivery | GitHub Actions, dependency scanning, container scanning, staged rollout | Review → test → build → staging → approval → production | Enterprise source-control provider can replace GitHub |

### Local development shape

Run web, API, worker and PostgreSQL locally. Use synthetic fixtures, a filesystem object-store adapter and a fake payment connector. A development-only identity stub must be explicitly enabled and impossible to deploy in production configuration. Add one real OIDC staging integration before handling pilot data.

No real bank keys, paid model calls or cloud resources are necessary for the first deterministic invoice-checking milestone.

## 2. Why this stack fits the product

- TypeScript supports the interactive reviewer interface; Python supports document and model evaluation work.
- One backend owns financial rules, permissions and state transitions. Shared OpenAPI contracts reduce frontend/backend drift.
- PostgreSQL provides one transactional boundary for a decision, approval record, and durable follow-up work.
- Object storage holds document bytes; the database stores metadata, versions, hashes and access relationships.
- API and worker are different processes of the same application, so OCR and model work do not hold an HTTP request open.
- Model, OCR, identity and external-action adapters limit provider-specific assumptions in the business code.

Tradeoff: two languages require familiarity with two toolchains. If the team is strongly TypeScript-only, a TypeScript API is a reasonable substitution; keep the same evidence, policy, transaction and approval contracts. Avoid maintaining both backends.

## 3. AI implementation boundaries

Use bounded operations such as `extract_invoice`, `summarize_findings`, and `draft_case_narrative`. Give each operation an input schema, output schema, maximum size, timeout, retry policy, model/prompt version, and source-reference contract. Critical fields are compared with source records before an action becomes eligible.

Model selection is an engineering gate rather than a hardcoded fashionable model name. Evaluate region-available Claude/Nova candidates against representative examples. Select on critical-field accuracy, unsupported-claim rate, latency, cost per completed case, data terms and allowed processing regions. Record the exact model ID, prompt version and settings in the evaluation report.

Cross-region inference may route requests outside the source region. A Mumbai application endpoint alone does not establish India-only model processing. Confirm the actual destination regions and customer permissions before enabling any inference profile. [AWS cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)

Configure finite input/output budgets. Store request metadata and evaluated outcomes; exclude raw personal data and model prompts from routine logs. An unavailable model may degrade explanations, but must not relax mandatory financial controls.

### Bedrock Guardrails: a supplement to the product's own controls

The service offers content and prompt-attack filters, denied topics, word/sensitive-information filters, contextual grounding checks and automated reasoning capabilities, with feature-specific limitations. These do not replace application authorization or authoritative financial calculations. [AWS Guardrails](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails.html)

Three integration choices to evaluate:

1. `guardrailConfig`: attach a configured guardrail to a model request.
2. `guardContent`: select untrusted content blocks for evaluation, checking filter-specific behavior; include document and tool content, not just typed user messages.
3. `ApplyGuardrail`: evaluate input/output through a separate call, useful around a provider adapter.

The proposed initial integration is a bounded non-streaming request with a pinned guardrail version where tests show benefit. Keep sensitive traces disabled. If model invocation logging is enabled, original unmasked content can be retained even when an output filter masks data; configure logging, access, encryption and retention separately. Any production integration needs current API verification and evaluation; no guardrail is configured by this document.

Coverage is API-field-specific: AWS documents that the prompt-attack filter does not inspect `toolResult` content or tool definitions in the specified fields. Do not assume attaching a guardrail screens every indirect instruction. Keep uploaded/retrieved content untrusted, evaluate supported content paths explicitly, and enforce all action permissions outside the model. [Prompt-attack coverage](https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-prompt-attack.html)

## 4. Authentication and isolation

Use the authorization-code flow with PKCE and a server-side session design. Keep confidential credentials on the server. Prefer a secure, HttpOnly, SameSite session cookie; apply CSRF protection and origin checks to mutations. Browser-only interface restrictions are not authorization.

FastAPI validates the trusted identity and then checks current application membership, role, legal-entity scope and action authority. Do not treat a client-supplied organization ID as proof of membership. Set the database's organization context inside each transaction; ordinary runtime roles must not bypass RLS. Workers and downloads require the same organization checks.

Cognito is an identity provider. The application remains responsible for tenant membership, maker-checker separation, policy ownership and action authorization. A user-pool-only arrangement is sufficient when the browser talks to our API and receives narrowly scoped document upload/download URLs. [Cognito developer guide](https://docs.aws.amazon.com/cognito/latest/developerguide/what-is-amazon-cognito.html), [Next.js authorization guidance](https://nextjs.org/docs/app/guides/authentication), [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

## 5. Cloud deployment and costs

Default proposed pilot region: `ap-south-1` (Mumbai), subject to customer requirements and current service/model availability. Use separate development, staging and production environments; no live customer data in synthetic demos.

Suggested topology: public HTTPS load balancer → web/API services; private worker and database; private evidence bucket; controlled outbound calls to approved model/OCR and connector endpoints. Only the execution component can use a enabled financial-action credential. Disable live-action connectors entirely in the first release.

Development can be inexpensive locally. A secure always-on cloud pilot has fixed costs even with few customers. Estimate before launch:

`monthly cost = container runtime + database/backup + networking/load balancing + storage/requests + OCR + model tokens/guardrail calls + identity + logging/security + support labor`

Include S3 request and retrieval costs, stored versions, logs and audit retention; database standby/backups; outbound transfer or private-endpoint/NAT costs; and the operational cost of recovery testing. Retention policies and batching can reduce cost, but must preserve required evidence.

No dollar or rupee cloud quote is asserted here. Build a region-specific estimate using measured case sizes and current rates: [Fargate](https://aws.amazon.com/fargate/pricing/), [RDS PostgreSQL](https://aws.amazon.com/rds/postgresql/pricing/), [S3](https://aws.amazon.com/s3/pricing/), [Bedrock](https://aws.amazon.com/bedrock/pricing/), [Textract](https://aws.amazon.com/textract/pricing/), [Cognito](https://aws.amazon.com/cognito/pricing/).

For S3, enable TLS, encryption at rest, public-access blocking, least-privilege object access, and monitored access history. Budget for server access logs/CloudTrail data events and CloudWatch metrics where enabled. Scope service resource policies to the relevant source account/resource where supported; encrypt log destinations. Consider customer-managed keys when the buyer's requirements justify their management cost. [S3 security guidance](https://docs.aws.amazon.com/AmazonS3/latest/userguide/security-best-practices.html)

## 6. Decisions deliberately deferred

| Deferred choice | Why | Decision trigger |
|---|---|---|
| Exact model ID and guardrail thresholds | Need representative evaluations and region approval | Before any real-data pilot |
| Live banking/payment provider | Requires customer demand, provider eligibility, contract and operational validation | After review/simulation value is proven |
| KYC/sanctions/credit specialist providers | Depends on geography and regulated customer workflows | Before activating the relevant module |
| Redis, Kafka, vector database | Current design does not require them | Measured latency/throughput/retrieval requirement |
| Temporal or another workflow service | Additional operations and learning cost | Long-running workflows become hard to maintain with the durable job/state model |
| Dedicated tenant infrastructure | Expensive before a buyer requires it | Contracted isolation requirement |
| Multi-region operation | Adds data-governance and recovery complexity | Agreed recovery/availability requirements justify it |

## 7. Primary technical references

- [FastAPI documentation](https://fastapi.tiangolo.com/) and [deployment with containers](https://fastapi.tiangolo.com/deployment/docker/).
- [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/): validate types, then separately validate business meaning.
- [pypdf text extraction](https://pypdf.readthedocs.io/en/stable/user/extract-text.html): scanned images require OCR.
- [Textract invoice/receipt analysis](https://docs.aws.amazon.com/textract/latest/dg/analyzing-document-expense.html).
- [AWS transactional outbox guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html): atomic persistence and idempotent processing are distinct concerns.
- [Playwright documentation](https://playwright.dev/docs/intro) for user-flow verification.

These references support individual technology behaviors. They do not prove this product's performance, security, suitability for a particular jurisdiction, or commercial value.
