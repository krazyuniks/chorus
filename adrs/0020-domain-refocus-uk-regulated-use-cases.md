---
type: adr
status: accepted
date: 2026-05-20
---

# ADR 0020 - UK-Regulated Use Cases

## Decision

Chorus demonstrates the named-port architecture through three UK-regulated use
cases:

| Slot | Use case | Regulator |
|---|---|---|
| UC1 | UK personal-lines insurance broking inbound quote qualification. | FCA general insurance distribution: ICOBS, PROD 4, Consumer Duty. |
| UC2 | UK legal services intake and conflict check for a corporate / commercial practice area. | SRA Code of Conduct, conflict-of-interest rules, AML obligations. |
| UC3 | UK independent financial advice inbound enquiry. | FCA retail investment advice: COBS 9 suitability, PROD, Consumer Duty. |

The use cases exist to exercise the architecture, not to become three product
lines. The six named ports and workflow spine stay constant. The intake
channels, connector inventory, approval policy, and conduct audit content vary
by use case.

## Consequences

- UC1 is the worked proof and current runnable path.
- UC2 and UC3 require full product briefs and domain models before
  implementation.
- R4 must prove adapter reuse across the three use cases without turning the
  project into a generic workflow framework.
- All data remains local and synthetic.

## Constraints

- Do not use fictional or generic business domains as the evidence story.
- Do not encode regulatory hooks without verifying the current official source
  in the relevant product/domain session.
- Do not broaden into production deployment, production customer data,
  production SSO, or a SaaS product during the local POC.
