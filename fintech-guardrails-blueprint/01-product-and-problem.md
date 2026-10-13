# Product and problem definition

Planning date: 9 October 2026. Status: proposed product; assumptions and targets require customer validation. Working name: **FinGuard** (a placeholder, not a cleared trademark).

## 1. Unified problem statement

Finance, payments, lending, and compliance teams must turn documents, transaction records, customer information, and organizational policies into accurate decisions and authorized actions. Their evidence often lives in different systems. Reviewing it, resolving contradictions, applying the correct policy, and reconstructing decisions can require repeated manual work.

AI can help extract information, investigate exceptions, and prepare recommendations. It can also produce unsupported claims, misread amounts, reveal information to the wrong person, or propose an action beyond its authority. These risks become consequential when an output influences a payment, accounting correction, customer communication, identity review, or credit decision.

The proposed product is a single web application that connects evidence, domain-specific checks, human review, and controlled execution. Eight financial workflow modules share organization permissions, policy versioning, source references, approvals, and an audit history. Its objective is to reduce avoidable review work and errors while preserving accountability. It must measure missed problems as well as unnecessary interruptions to legitimate work.

**Primary product hypothesis:** a finance team will pay for a reliable invoice-to-reconciliation exception workflow that works with its existing records and makes each finding and approval explainable.

**Expansion hypothesis:** some customers will later buy additional risk and compliance modules using the same control infrastructure. The initial finance buyer is not assumed to need all eight modules.

## 2. Evidence and assumptions

The Bank of England/FCA's 2024 survey of 118 firms reported that 75% used AI; data privacy/protection, quality, and security were the three largest perceived current risks. This establishes relevant industry concerns, not demand for this particular product. [Survey](https://www.bankofengland.co.uk/report/2024/artificial-intelligence-in-uk-financial-services-2024)

NIST describes the risk of generative AI presenting false information and fabricated supporting reasoning. Evidence-backed financial drafting must therefore include verification and correction paths. [NIST Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)

For AML, FATF describes opportunities for technology while retaining human judgment and monitoring unintended consequences. These are design considerations, not a certification of any product. [FATF technology work](https://www.fatf-gafi.org/en/publications/Digitaltransformation/Digital-transformation.html)

Unvalidated assumptions to test:

- India-first, business-to-business distribution/wholesale businesses with a finance team, repeated invoice review, and exportable accounting/payment records.
- CFO/controller buys; accounts-payable and reconciliation analysts use it; IT/security participates in approval.
- One or two builders; optional fractional finance-domain and security expertise.
- First release uses INR, one legal entity per customer workspace, approved file formats, and customer-supplied vendor/payment records.
- Pilot users can share authorized historical examples and spend time labeling outcomes.
- Export/import compatibility is sufficient for the first pilot; live bank access is not required to prove review value.
- A bank, lender, or remittance firm requires a separate sales and validation track before AML/KYC/credit modules enter production.

The product design should change if these assumptions fail. Customer discovery questions and stop conditions are in [the startup roadmap](06-startup-roadmap.md).

## 3. The three kinds of control

| Layer | What it addresses | Example | Owner of the final check |
|---|---|---|---|
| AI output and input controls | Unsupported claims, malicious instructions in documents, excessive sensitive information, malformed output | Invoice text tells the assistant to ignore approval rules | Bounded model adapter, schema validation, source checks, restricted tools |
| Financial workflow controls | Incorrect amounts, missing evidence, duplicate actions, unverified recipients, policy exceptions | The invoice's total does not equal its line items | Deterministic application rules and trusted records |
| Authorization and execution controls | Whether this actor may perform this exact action now | A requester tries to approve their own payment | Server authorization, approval service, execution gateway |

Identity verification, sanctions screening, fraud scoring, and credit-risk modeling remain specialist capabilities. The platform may integrate them and govern their outputs. A language-model content filter alone does not establish identity authenticity, prevent every fraud, or validate a credit model.

## 4. Eight modules within one application

Every module has its own input contract, policy pack, evidence requirements, evaluation cases, and release gate. Shared navigation does not imply every check runs on every request.

| Module | Problem statement | Proposed workflow and output | Required evidence/integrations | Effectiveness to measure | Delivery stage |
|---|---|---|---|---|---|
| M1 Invoice and payment preflight | Reviewers need to detect duplicate invoices, incorrect totals, and beneficiary changes before approval | Extract fields; compare with vendor, PO, and payment records; produce pass/block/review findings with references | Original invoice, approved vendor version, PO if available, paid-invoice history | Critical-field accuracy; precision/recall by issue; review time; false holds | First release |
| M2 Reconciliation investigation | Bank and accounting records differ, and analysts repeatedly reconstruct causes | Import records; suggest one-to-one matches initially; identify missing/duplicate entries; draft a resolution | Immutable bank/processor exports, accounting entries, import lineage | Match precision; missed matches; time per exception; erroneous corrections | First release |
| M3 AML evidence workspace | Investigators collect scattered evidence and write narratives with incomplete context | Accept an existing alert; assemble a timeline and facts; identify missing evidence; prepare an investigator-reviewed draft | Authorized transaction history, customer profile, screening/monitoring outputs, investigator notes | Citation correctness; omitted facts; reviewer rework; time per case | Later regulated-domain release |
| M4 Chargeback evidence | Staff manually assemble records into responses that may be incomplete or inconsistent | Organize order, delivery, support, and refund evidence into an editable packet | Merchant order system, carrier records, support records, dispute deadline/rules | Packet preparation time; evidence completeness; unsupported assertions; deadline adherence | Adjacent module after buyer validation |
| M5 Agent payment control gateway | Automation can attempt actions with stale approvals, incorrect recipients, excessive amounts, or duplicate requests | Evaluate a proposed action; require scoped authority and approval; execute through a controlled connector | Actor authority, exact action payload, beneficiary version, current limits, provider status | Unauthorized/duplicate execution tests; false rejects; approval freshness; unknown-status resolution | Simulator first; live actions separately gated |
| M6 Underwriting evidence validator | Loan files can contain conflicting figures, unsupported reasons, and undocumented policy exceptions | Check document evidence and calculations; highlight inconsistencies; prepare a reviewer checklist | Lender-provided policies, authorized income/bank documents, model outputs where relevant | Calculation accuracy; contradiction detection; evidence coverage; reviewer correction rate | Later regulated-domain release |
| M7 Collections and communication QA | Customer messages can contain incorrect balances, unapproved offers, policy violations, or missed hardship indicators | Compare drafts/transcripts with account facts and approved policies; flag for a supervisor | Account ledger, approved communication policy, authorized conversation record | Policy-violation recall; false alerts; factual errors; correction and complaint trends | After lender/servicer partner validation |
| M8 KYC/KYB review | Missing, stale, or inconsistent evidence creates repeated reviewer work | Organize customer/business evidence; incorporate verification results; route discrepancies | Approved verification provider results, document metadata, ownership records where available | Review time; missing-document detection; false matches/alerts; rework | Later regulated-domain release |

Interpretation boundaries: an anomaly is not proof of fraud; a suspicious-activity narrative is not a finding of money laundering; a complete credit file is not proof of creditworthiness or fairness; a matched name is not a confirmed identity.

## 5. Shared product capabilities

1. **Organizations and access:** membership, roles, module entitlements, legal-entity scope, revocation, and separation of requester and approver.
2. **Evidence workspace:** original records, extracted fields, page/row references, source freshness, confidence or verification status, and user corrections.
3. **Policy library:** explicit rules with owner, applicability, version, effective date, review status, and test examples.
4. **Case and review queue:** assigned owner, due date, findings, unresolved questions, comments, escalation, and allowed next actions.
5. **Approval service:** approver authority, exact payload, supporting decision version, expiry, and invalidation after changes.
6. **Action gateway:** a single enforced route for enabled financial actions; duplicate protection, limits, provider reconciliation, and an emergency stop.
7. **Audit and export:** actor, action, timestamp, input/policy versions, decision, approvals, outcome, and evidence references.
8. **Evaluation and operations:** replay labeled cases, compare releases, monitor queue age and provider failures, and show module-specific outcome measures.

### Web application navigation

Workspace → Overview → Review queue → Documents and imports → Invoices → Reconciliation → Payment simulations → Policies → Approvals → Audit → Integrations → Team and settings.

The other five modules appear only when enabled for a validated customer. Prototype demonstrations must be labeled as demonstrations. Users should not see a production feature that only contains sample results.

## 6. First-release user stories

| ID | Story | Acceptance condition |
|---|---|---|
| P-01 | As an analyst, I upload an invoice and inspect extracted fields | Each critical field points to a source location; missing/unreadable fields require correction |
| P-02 | As an analyst, I see a possible duplicate | Finding shows matching record and comparison fields; repeated upload does not create repeated payment proposals |
| P-03 | As a reviewer, I inspect a beneficiary change | Prior and proposed versions are visible; independent verification is recorded before it becomes trusted |
| P-04 | As an approver, I approve an exact simulated payment | Requester cannot approve their own request; a changed amount/recipient/input snapshot invalidates approval |
| P-05 | As a controller, I reconcile imported records | Exact matching is reproducible; suggested matches need acceptance; original imported rows stay available |
| P-06 | As an auditor, I reconstruct a decision | Export includes evidence, versions, actors, approvals, and outcome; export respects field-level permissions |
| P-07 | As an administrator, I revoke a user | Protected requests recheck membership; pending actions cannot rely on revoked authority |
| P-08 | As a user, I encounter unavailable AI | Case remains reviewable; critical missing facts hold the action; existing records are not lost |

## 7. Product constraints and quality goals

- **Default first release:** file imports, review decisions, correction proposals, and payment simulation. No custody, autonomous loan decisions, regulator filings, or unsupervised collections messages.
- **Financial correctness:** decimal/integer money representations; explicit currency; reproducible calculations and matching.
- **Evidence first:** store source references and distinguish extracted, user-confirmed, and externally verified facts.
- **No silent bypass:** an unavailable required check yields a review/hold result, not permission to execute.
- **Accessible review:** keyboard navigation, readable tables, status labels beyond color, and clear errors.
- **Data minimization:** only necessary fields go to approved providers; sensitive logs are excluded by default.
- **Tenant isolation:** the UI, API, worker, database, search, object access, and exports all enforce the organization boundary.
- **Customer control:** the organization configures retention and approved processing arrangements within its obligations; deleting an account is a managed workflow, not blind deletion of audit evidence.

Suggested performance and recovery targets are design assumptions in [HLD](02-system-architecture.md), not achieved service promises.

## 8. What would make this useful enough to buy?

The strongest test is whether a finance team completes the same real work with less effort and no unacceptable increase in missed errors or unnecessary holds. A customer should be able to trace an issue from the original invoice through review and approval to its eventual accounting resolution.

Initial evidence required before expanding scope:

- A named buyer owns the problem and has authority to fund a pilot.
- Staff provide representative cases and agree on correct outcomes.
- The product fits an existing review procedure and does not create duplicate manual entry.
- Benefit exceeds software, integration, review, and support costs.
- The same workflow works for another customer without becoming a custom consulting project.

Competitor capabilities and proposed differentiation are separated in [the competition analysis](07-competition-and-positioning.md). We do not currently have evidence that the proposed product outperforms existing products.
