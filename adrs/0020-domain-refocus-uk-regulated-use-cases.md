---
type: adr
status: accepted
date: 2026-05-20
---

# ADR 0020 - Domain refocus to UK-regulated use cases

## Context

ADR 0001 chose Lighthouse, an inbound-lead concierge for a fictional small
business, as the Phase 1 evidence slice and the only Phase 1 workflow. ADR
0015 added Support Desk Triage as a second workflow proof.

The 2026-05-19 transformation reset found the project's engineering identity
too soft to defend, and its domains ungrounded.
`transformation/context-and-intent.md` records that terms such as `support`,
`ticket`, `case`, and `account` were technically implemented but not grounded
in a chosen domain. A fictional SMB concierge and a generic helpdesk triage do
not exercise a real governance regime, so the audit, approval, and
contract-first work could not be measured against anything external.

`transformation/domain-refocus-plan.md` set the selection criteria:
UK-regulated verticals only, demonstrable on local synthetic data, exercising
the named ports without exotic adapters. R1 confirmed the use-case set.

## Decision

Retire Lighthouse and Support Desk Triage as the project's named exemplars.
Adopt three UK-regulated use cases.

| Slot | Use case | Regulator |
|---|---|---|
| UC1 | UK personal-lines insurance broking inbound quote qualification. Fully modelled in R1. | FCA general insurance distribution (ICOBS, PROD 4, Consumer Duty). |
| UC2 | UK legal services intake and conflict check, corporate / commercial practice area. Confirmed in R1. | SRA Code of Conduct, conflict-of-interest rules, AML obligations. |
| UC3 | UK independent financial advice inbound enquiry. Confirmed in R1. | FCA retail investment advice (COBS 9 suitability, PROD, Consumer Duty). |

The use cases exist to exercise the named ports and to demonstrate adapter
reuse across regulatory regimes. The six named ports and the workflow spine
stay constant across all three. The intake channel adapters, the connector
inventory, the approval policy, and the regulator-specific audit content vary
per use case. That adapter-reuse hypothesis is the centre of the thesis; UC1
is the worked proof and UC2 and UC3 extend it across two regulators and three
conduct disciplines.

Each domain replaces the generic, ambiguous vocabulary with its own ubiquitous
language. The banned terms - lead, case, ticket, account, score,
recommendation, advice, tool - are recorded in the UC1 domain model.

## Consequences

- This ADR supersedes the choice of Lighthouse as the evidence exemplar in ADR
  0001 and the choice of Support Desk Triage as the second workflow in ADR
  0015. The evidence-first principle of ADR 0001 - one complete vertical
  slice, depth over breadth - is retained and now applies to UC1.
- Lighthouse and Support Triage code is preserved as historical evidence until
  R3 retires or rewrites it under the refactored workflow spine.
- R1 produced the UC1 product brief and domain model, the UC2 and UC3
  confirmation, and the adapter mapping. R3 lands the contracts and code; R4
  wires all three use cases for local POC readiness with cross-provider
  replay-eval.
- The domains are governed by recognised UK regulators, so the audit and
  approval work can be measured against an external conduct regime rather than
  against invented abstractions.
- The use cases run on local sandboxes and synthetic data only. Deployment
  leaves the Chorus repository and is reframed as a future vault-level Radian
  IT project.

## Alternatives considered

### Keep Lighthouse and reframe it as UK-regulated

Rejected. Lighthouse is a fictional small-business concierge with no
regulator. Retrofitting a regulatory regime onto a fictional domain would be
exactly the invented abstraction the reset set out to remove.

### One use case only

Rejected. A single use case cannot demonstrate adapter reuse, which is the
centre of the thesis. The second and third use cases prove that the named
ports and the workflow spine carry across regulators without deforming the
domain core.

### More than three use cases

Rejected. Three use cases already span two regulators and three conduct
disciplines, including two contrasting FCA conduct shapes. More would dilute
the depth that the evidence-first principle of ADR 0001 protects.
