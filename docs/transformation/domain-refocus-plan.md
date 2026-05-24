---
type: project-doc
status: active
date: 2026-05-24
---

# Domain Use-Case Set

Chorus demonstrates the ports-and-adapters thesis through UK-regulated
business workflows. The domain work serves the architecture: each use case
stresses a different regulatory and operational shape while reusing the same
ports.

## Selected Use Cases

| Slot | Use case | Regulator | R4 state |
|---|---|---|---|
| UC1 | UK personal-lines insurance broking inbound quote qualification. | FCA general insurance distribution: ICOBS, PROD 4, Consumer Duty. | Product brief and domain model exist; runnable path exists; connector persistence and full verdict routing are R4 work. |
| UC2 | UK legal services intake and conflict check for a corporate / commercial practice area. | SRA Code of Conduct, conflict-of-interest rules, AML obligations. | Product brief and domain model exist; runtime implementation is later R4 work. |
| UC3 | UK independent financial advice inbound enquiry. | FCA retail investment advice: COBS 9 suitability, PROD, Consumer Duty. | Product brief and domain model exist; runtime implementation is later R4 work. |

The use cases are not independent products. They prove whether the same
workflow spine and named ports can carry different regulated business
contexts.

## Selection Criteria

| Criterion | Requirement |
|---|---|
| UK regulatory regime | The work sits under a recognised UK regulator and has conduct or approval boundaries that can be audited. |
| Operational shape | Inbound work, classification, context gathering, proposed action, approval where risk demands it, audit, and closure. |
| Adapter exercise | The use case stresses intake, LLM provider, connector, audit, projection, and observability ports without exotic adapters. |
| Synthetic local data | The use case can be demonstrated locally without production third-party credentials or customer data. |
| Contract-first fit | The important boundaries can be written as contracts before code. |
| Replay surface | Captured invocations carry enough context to replay against an alternate provider for cross-provider eval. |

## Domain Model Requirements

Each use case has a product brief and domain model before runtime work. Those
artefacts define:

- actors and roles;
- inbound artefacts;
- lifecycle records and state machine;
- commands and domain events;
- value objects and safe references;
- approval points;
- policies and conduct invariants tied to current official regulatory sources;
- connector inventory;
- failure and escalation paths;
- field placement across contracts, audit, projection, telemetry, and
  transcripts;
- banned or ambiguous terms.

## R4 Local POC Shape

R4 must produce three coherent local flows:

1. UC1 insurance enquiry qualification.
2. UC2 legal intake and conflict check.
3. UC3 IFA suitability intake.

Each flow needs:

- a business scenario in domain language;
- contracts at every port the use case touches;
- local synthetic data;
- workflow implementation on the shared spine;
- Tool Gateway actions named in the use case's domain;
- BFF/UI inspection;
- invariant-based eval;
- replay evidence through the LLM provider port.
