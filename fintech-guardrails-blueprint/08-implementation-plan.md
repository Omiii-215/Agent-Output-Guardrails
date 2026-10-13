# Implementation plan, backlog and acceptance gates

Status: implementation blueprint. No application, integrations or infrastructure have been deployed by creating this plan.

## 1. Delivery strategy

Build the shared platform through an end-to-end invoice workflow, then add reconciliation and simulated payment controls. Give all eight modules clear boundaries now; implement the other modules only when a representative customer and validation data are available.

Planning assumption: two experienced builders plus regular finance-domain input. A pilot-ready first release and initial pilot may take roughly **12–16 weeks** under these assumptions. A solo builder learning the stack should plan **4–6 months or longer**. These are provisional effort ranges, not delivery commitments. An eight-module production suite is a substantially larger program whose schedule should be estimated after discovery.

## 2. Milestones

| Stage | Indicative window | What gets built or learned | Exit gate |
|---|---|---|---|
| Discovery and fixtures | Weeks 1–2 | Observe review work; select one buyer segment; agree data contract; label example cases; sketch review screens | Named pilot champion; baseline process and costs; representative authorized or synthetic fixtures |
| Shared foundations | Weeks 3–4 | Organization/membership, API, database migrations, object interface, case records, audit history, durable jobs, staging identity | Two tenants are isolated in API/database/object access; jobs survive restart; access changes take effect |
| Invoice review | Weeks 5–7 | Upload, extraction, critical-field correction, duplicate and arithmetic checks, vendor comparisons, evidence panel, versioned policies | End-to-end reviewer workflow; extraction errors become review cases; rule results reproducible |
| Reconciliation and action simulator | Weeks 8–10 | CSV imports, one-to-one matching, exception queue, action proposals, maker-checker, idempotency, simulated outcomes | Match evaluation passes agreed gate; stale/self approvals rejected; duplicate and timeout behavior demonstrated |
| Pilot readiness | Weeks 11–12 | Monitored deployment, backups/restore drill, export/deletion procedures, support runbooks, representative evaluation, security review | No unresolved release-blocking controls; data arrangements agreed; rollback and recovery demonstrated |
| Measured customer pilot | Weeks 13–16 | Observe normal work; compare outcomes; fix integration friction; record costs; test willingness to pay | Buyer accepts measured results and decides whether to purchase/continue |

Stages overlap only where dependencies allow. Customer access, integration approvals and validation can dominate the calendar. Do not shorten validation merely to hit an illustrative date.

## 3. Proposed repository structure

This is a future layout, not existing code:

```text
finguard/
  apps/
    web/                         # Next.js application
    api/                         # FastAPI entry point
    worker/                      # Worker entry point, same Python package
  backend/
    identity/                    # Membership, roles, entity scope
    evidence/                    # Documents, imports, source references
    cases/                       # Review lifecycle, assignments
    policies/                    # Versioned rules and evaluators
    approvals/                   # Payload-bound approvals
    actions/                     # Controlled execution and simulator
    modules/
      invoices/
      reconciliation/
      aml/
      chargebacks/
      underwriting/
      communications/
      kyc/
    adapters/
      object_store/
      oidc/
      ocr/
      models/
      payments/
    persistence/
    telemetry/
  contracts/                     # Generated OpenAPI/client artifacts
  migrations/
  tests/
    unit/
    integration/
    isolation/
    workflow/
    evaluations/
  fixtures/synthetic/
  infrastructure/
  docs/
```

M5's gateway lives in shared `actions/` because it must control the other modules' financial actions. Do not create eight independent authentication, approval or audit implementations.

## 4. Build order within each stage

### Foundation backlog

| ID | Task | Depends on | Definition of done |
|---|---|---|---|
| F-01 | Record architecture decisions, data classifications and environments | Product scope | Decisions have owner, reason and revisit trigger |
| F-02 | Scaffold web/API/worker, linting and build checks | F-01 | One documented local start path with synthetic data |
| F-03 | Implement organizations, memberships and current-role checks | F-02 | Cross-tenant reads/writes/exports rejected; unauthorized roles tested |
| F-04 | Establish database migrations, organization-scoped keys and RLS | F-03 | Migration tested on empty and prior schema; runtime is not DB owner |
| F-05 | Add object upload quarantine and scan workflow | F-04 | Type/size limits, restricted parsing, object authorization, failure status |
| F-06 | Add cases, evidence versions and append-only audit interface | F-04 | Original records preserved; edits create new versions; audit includes actor/context |
| F-07 | Add jobs/outbox, leases, bounded retries, dead-letter review | F-06 | Crash/restart and duplicate delivery do not lose or duplicate effects |
| F-08 | Connect staging OIDC; enforce session and CSRF protections | F-03 | Auth failure, revocation, role change and session expiry verified |

### Invoice backlog

| ID | Task | Depends on | Definition of done |
|---|---|---|---|
| I-01 | Define invoice/vendor/payment-history import schemas | F-06 | Currency, decimals, timestamps, source row IDs and duplicate imports validated |
| I-02 | Extract digital PDF text and create source spans | F-05/F-07 | Critical fields link to pages/spans; corrupt/scanned files get explicit status |
| I-03 | Add OCR adapter with quality checks | I-02 | Representative scanned examples evaluated; uncertain fields require review |
| I-04 | Build deterministic total, duplicate and beneficiary checks | I-01 | Each rule has reason code, severity, applicability, source refs and expected tests |
| I-05 | Implement versioned policy activation | I-04 | Policy draft → test → review → activate; affected pending decisions invalidated |
| I-06 | Build evidence/result/correction UI | I-02/I-04 | Keyboard-usable side-by-side evidence and corrections; no color-only statuses |
| I-07 | Add bounded AI extraction/explanation | I-06 | Structured outputs validated; no invented evidence references; model outage safe |

### Reconciliation and action backlog

| ID | Task | Depends on | Definition of done |
|---|---|---|---|
| R-01 | Import bank/accounting rows without changing originals | I-01 | Idempotent imports; checksums and import lineage |
| R-02 | Exact reference/amount/currency matching | R-01 | Ambiguous matches remain suggestions; no transaction matched twice |
| R-03 | Exception cases and correction proposals | R-02 | Reviewer confirms resolution; accepted result references originals |
| A-01 | Define canonical action payload and decision snapshot | I-05/F-06 | Amount, currency, beneficiary version, entity, policy and evidence hashes included |
| A-02 | Maker-checker approvals and expiry | A-01 | No self approval; revoked roles/stale payloads fail; exact version approved |
| A-03 | Fake payment connector with success/failure/unknown states | A-02/F-07 | Simulates provider timeout after acceptance and duplicate webhook delivery |
| A-04 | Dispatch revalidation and idempotency | A-03 | Limits rechecked at send time; concurrency cannot exceed allowance; retries use same identity |
| A-05 | Outcome-to-reconciliation linkage | A-04/R-03 | Simulation clearly labeled; case shows resulting record and resolution |

### Pilot operations backlog

| ID | Task | Definition of done |
|---|---|---|
| O-01 | Region/provider and data-processing review | Approved list of processing locations, subprocessors, permitted data and retention |
| O-02 | Infrastructure, secrets and monitoring | Reviewed deployment plan; scoped runtime roles; production credential separation |
| O-03 | Backup/restore and deployment rollback | Timed rehearsal using staging; record actual RPO/RTO and reconcile pending work |
| O-04 | Evaluation and performance report | Held-out cases; denominators; failure taxonomy; latency/cost under stated load |
| O-05 | Customer onboarding and support | Named policy owner/approver/support contacts; escalation and incident procedures |
| O-06 | Retention, export and account closure | Authorized workflows tested across DB, objects, providers, backups and legal holds |

## 5. Initial policy examples

These describe business intent; executable schemas and enforcement are specified in [LLD](04-low-level-design.md).

| Rule | Required inputs | Expected treatment |
|---|---|---|
| Missing invoice amount/currency/vendor | Verified or reviewable extracted fields | Review; no payment eligibility |
| Total mismatch | Line items, taxes, discount, total, explicit rounding rule | Block payment eligibility and show exact calculation for correction/review; tolerances owned/versioned by customer |
| Exact paid-invoice duplicate | Normalized vendor/invoice reference, currency, historical payment record | Block new payment proposal; reference existing case/payment |
| Similar invoice | Similarity signal and comparison fields | Review; similarity alone does not prove fraud |
| Unverified beneficiary change | Approved vendor record and proposed account version | Hold until independent verification workflow completes |
| Amount exceeds approval threshold | Action amount/currency and effective policy | Require appropriate authorized approvers |
| Requester equals approver | Trusted actor identities | Reject approval |
| Inputs/policy changed since approval | Current versus approved snapshot | Invalidate approval and require re-evaluation |
| Provider returned ambiguous status | Stable external request ID | Mark unknown; reconcile with provider; do not generate a fresh payment request |

## 6. Evaluation plan

### Dataset

Begin with synthetic scenarios, then authorized and minimized historical cases from a design partner. Define expected results with a finance reviewer. Separate development examples from a held-out evaluation set; version data and labels; record uncertainty and disagreements. Never copy one customer's raw documents into another customer's demo or shared training set.

Coverage must include clean invoices, genuine duplicates, credit notes, identical amounts for different invoices, vendor alias changes, legitimate bank-account changes, tampered-looking records, unreadable pages, ambiguous dates, tax/rounding differences, repeated imports and conflicting source versions. Feature support such as credit notes must be explicit; unsupported cases are routed for review.

### Meaningful tests

1. Financial calculations with decimal boundary and rounding cases.
2. Organization/role isolation in API, database, workers, signed URLs, search and exports.
3. Two simultaneous approvals or payment requests; duplicate prevention enforced transactionally.
4. Document or policy changes after approval; dispatch rejects stale authorization.
5. Worker crash before/after commit and after external acceptance; no lost case and safe unknown-state recovery.
6. Forged/duplicate/out-of-order callbacks; signature and event-identity checks.
7. Malicious instructions in uploaded text; model has no payment credentials or permission to alter policy.
8. Missing/unreadable data and model/OCR downtime; no silent pass.
9. Revoked approver or expired session; action revalidates authority.
10. Backup restoration and reprocessing; no duplicate business actions.

### Metrics and provisional gates

Do not claim a blanket accuracy percentage. Report each rule/module separately, with sample sizes and case composition.

- Required invariant tests: **all pass** for isolation, permission, stale approvals and duplicate prevention. This is a release condition, not proof of universal safety.
- Critical invoice fields: track vendor, number, amount, currency and beneficiary separately; automatic acceptance threshold agreed from measured errors and reviewer tolerance.
- Detection: precision = confirmed issues / flagged issues; recall = detected labeled issues / all labeled issues. Labeling uncertainty stays visible.
- Efficiency: median and high-percentile active handling time per comparable case, including corrections and false alerts.
- Traceability: findings and decisions that have valid, accessible evidence references and policy versions.
- Operations: queue age, completion/failure rates, unknown external states, latency, and cost per completed case.
- Business: reviewer adoption, paid conversion, repeat usage, support hours, and customer-accepted savings.

Initial pilot targets are negotiated in [the startup plan](06-startup-roadmap.md). A target missed honestly is more useful than a misleading all-purpose accuracy claim.

## 7. How the other five modules are implemented later

Each module uses the same `case → evidence → checks → review → decision → audit` services. Add its own schemas, adapter contracts, rule pack, role requirements and evaluation set.

| Module | First bounded implementation | Activation gate |
|---|---|---|
| Chargebacks | Draft an evidence packet from exported order/delivery/refund records | Merchant partner verifies completeness and claims; submission remains reviewed |
| Communications QA | Review draft messages against verified balances and approved policy | Servicer policy owner validates findings, escalation and language coverage |
| KYC/KYB | Organize documents and integrate one authorized verification provider | Identity/compliance partner validates provider semantics and exception workflow |
| AML | Investigator case preparation from existing alerts | Authorized data, qualified reviewers, reproducible evidence and approved procedures |
| Underwriting evidence | Check a lender-provided file against one policy | Lender validates calculations/reasons and boundaries; separate credit/fairness review as needed |

These are separate commercial and domain validation projects. A finance-operations pilot does not validate regulated lending or AML use.

## 8. First ten working sessions

1. Confirm one buyer and workflow; write what success and failure look like.
2. Create two fictional organizations, vendors, invoices, bank rows and expected findings.
3. Scaffold the repository and local start path; add a health page and API contract.
4. Implement membership and organization isolation before real data.
5. Add schema migrations, evidence storage interface and upload lifecycle.
6. Display an original document and manually entered structured invoice fields.
7. Implement three deterministic checks and readable source-backed results.
8. Add case review, correction versions and audit history.
9. Add durable extraction jobs and a fake action/approval flow.
10. Demonstrate one complete workflow; record failures before adding AI extraction.

Each session is a work unit, not a promise of one calendar day. The very first useful demo can use manually entered fields: it tests whether the review workflow helps before extraction quality becomes a distraction.
