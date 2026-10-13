# FinGuard diagram gallery

These diagrams describe the proposed FinGuard blueprint. They do not represent a deployed product. First release: invoice checks, one-to-one reconciliation and simulated payment controls. Five expansion modules require separate validation. FinGuard is a working name.

16 PNG images, plus editable DOT sources and scalable SVG versions of the 15 technical diagrams.

[Open the offline gallery](index.html) · [Download the complete ZIP](../finguard-diagrams.zip) · [Back to the blueprint](../README.md)

## Diagram index

| # | Diagram | Image | Scalable image | Source |
|---|---|---|---|---|
| 00 | Problem, solution and value to prove | [PNG](00-problem-to-solution.png) | — | [Generation prompt](sources/00-overview-prompt.txt) |
| 01 | System context | [PNG](01-system-context.png) | [SVG](01-system-context.svg) | [DOT](sources/01-system-context.dot) |
| 02 | System architecture / high-level design | [PNG](02-system-architecture.png) | [SVG](02-system-architecture.svg) | [DOT](sources/02-system-architecture.dot) |
| 03 | Technology stack | [PNG](03-technology-stack.png) | [SVG](03-technology-stack.svg) | [DOT](sources/03-technology-stack.dot) |
| 04 | Low-level component design | [PNG](04-low-level-components.png) | [SVG](04-low-level-components.svg) | [DOT](sources/04-low-level-components.dot) |
| 05 | Core data model | [PNG](05-core-data-model.png) | [SVG](05-core-data-model.svg) | [DOT](sources/05-core-data-model.dot) |
| 06 | Approval lifecycle | [PNG](06-approval-lifecycle.png) | [SVG](06-approval-lifecycle.svg) | [DOT](sources/06-approval-lifecycle.dot) |
| 07 | Payment execution and recovery | [PNG](07-payment-execution.png) | [SVG](07-payment-execution.svg) | [DOT](sources/07-payment-execution.dot) |
| 08 | Finance user flow | [PNG](08-finance-user-flow.png) | [SVG](08-finance-user-flow.svg) | [DOT](sources/08-finance-user-flow.dot) |
| 09 | Reconciliation flow | [PNG](09-reconciliation-flow.png) | [SVG](09-reconciliation-flow.svg) | [DOT](sources/09-reconciliation-flow.dot) |
| 10 | Target buyer journey | [PNG](10-target-buyer-flow.png) | [SVG](10-target-buyer-flow.svg) | [DOT](sources/10-target-buyer-flow.dot) |
| 11 | Supplier and consumer correction flow | [PNG](11-consumer-correction-flow.png) | [SVG](11-consumer-correction-flow.svg) | [DOT](sources/11-consumer-correction-flow.dot) |
| 12 | Competitive landscape and positioning | [PNG](12-competitive-positioning.png) | [SVG](12-competitive-positioning.svg) | [DOT](sources/12-competitive-positioning.dot) |
| 13 | Implementation roadmap | [PNG](13-implementation-roadmap.png) | [SVG](13-implementation-roadmap.svg) | [DOT](sources/13-implementation-roadmap.dot) |
| 14 | From project to startup | [PNG](14-startup-roadmap.png) | [SVG](14-startup-roadmap.svg) | [DOT](sources/14-startup-roadmap.dot) |
| 15 | Eight modules, one shared platform | [PNG](15-eight-module-platform.png) | [SVG](15-eight-module-platform.svg) | [DOT](sources/15-eight-module-platform.dot) |

## How to use these images

- Use PNG for slides, reports and sharing. Open at full size to inspect small labels.
- Use SVG when you need to zoom or print the technical diagrams without losing sharpness.
- Edit a DOT file and run `python3 render_diagrams.py` with Graphviz installed to regenerate the technical images.
- The overview was created with the built-in image-generation tool; its exact prompt is saved with the sources.
- The technical diagrams faithfully simplify the existing blueprint. The linked documents define the complete contracts.
- Competitor groups summarize the dated research in document 07; they are not rankings or evidence of superiority.

## 00. Problem, solution and value to prove

Why this proposed product exists and where its first release starts

![Problem, solution and value to prove](00-problem-to-solution.png)

## 01. System context

People, source systems and provider boundaries

![System context](01-system-context.png)

## 02. System architecture / high-level design

One modular application, an API and durable background workers

![System architecture / high-level design](02-system-architecture.png)

## 03. Technology stack

Proposed development and pilot-hosting choices

![Technology stack](03-technology-stack.png)

## 04. Low-level component design

Application services and their control boundaries

![Low-level component design](04-low-level-components.png)

## 05. Core data model

Simplified relationships; see the LLD for complete contracts

![Core data model](05-core-data-model.png)

## 06. Approval lifecycle

Approval binds an independent reviewer to an exact proposal

![Approval lifecycle](06-approval-lifecycle.png)

## 07. Payment execution and recovery

Simulation first; live connectors require a separate release gate

![Payment execution and recovery](07-payment-execution.png)

## 08. Finance user flow

From an invoice to a reviewed, traceable simulation

![Finance user flow](08-finance-user-flow.png)

## 09. Reconciliation flow

First release supports exact one-to-one matching only

![Reconciliation flow](09-reconciliation-flow.png)

## 10. Target buyer journey

CFO or controller buys; finance staff validate daily usefulness

![Target buyer journey](10-target-buyer-flow.png)

## 11. Supplier and consumer correction flow

Requests pass through the customer organization's authorized channel

![Supplier and consumer correction flow](11-consumer-correction-flow.png)

## 12. Competitive landscape and positioning

Known product overlap; proposed differentiation still needs evidence

![Competitive landscape and positioning](12-competitive-positioning.png)

## 13. Implementation roadmap

12-16 weeks assumes two experienced builders and accessible data

![Implementation roadmap](13-implementation-roadmap.png)

## 14. From project to startup

Advance when customer evidence supports the next investment

![From project to startup](14-startup-roadmap.png)

## 15. Eight modules, one shared platform

Three first-release workflows; five separately validated expansions

![Eight modules, one shared platform](15-eight-module-platform.png)
