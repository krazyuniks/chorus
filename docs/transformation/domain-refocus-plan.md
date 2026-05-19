---
type: project-doc
status: active
date: 2026-05-19
---

# Domain Refocus Plan

## Goal

Choose a small, coherent set of UK-regulated use cases that exercise the
ports-and-adapters thesis. The domain work serves the architecture, not
the other way round. Domains are selected because they stress different
governance regimes while reusing the same adapter surface.

The target is not "AI routes messages". The target is regulated business
work where every cross-port payload is contract-validated, every governed
decision is audit-stamped with provenance, and every captured invocation
is replayable across providers.

## Shape Of The Use-Case Set

The R1 outcome is one fleshed-out use case plus two further use cases
chosen to demonstrate adapter reuse, not three independent products.

| Slot | Role |
|---|---|
| Use case 1 (primary) | Fully modelled. Drives the contracts, ubiquitous language, workflow, adapters, eval, replay, and demo. |
| Use case 2 | Different regulator, different intake shape, same adapter surface. Demonstrates that swapping the intake and connector adapters does not deform the core. |
| Use case 3 | Third regulator and third operational shape. Provides cross-provider replay evidence across all three. |

A use case is allowed to skip parts of the workflow surface if it does not
need them, but it must reuse the same named ports.

## Selection Criteria

Candidates must satisfy these criteria. UK-regulated verticals only.

| Criterion | Requirement |
|---|---|
| UK regulatory regime | The work sits under a recognised UK regulator (FCA, SRA, ICO, HMRC, or equivalent). Governance and approval boundaries map to that regime. |
| Operational shape | Inbound work, classification, context gathering, proposed action, approval where risk demands it, audit. |
| Adapter exercise | Stresses intake, LLM provider, connector, audit, projection, and observability ports without requiring exotic adapters. |
| Synthetic local data | The use case can be demonstrated with local synthetic data and sandbox connectors only; no production third-party credentials. |
| Contract-first fit | The important boundaries can be written as contracts before code. |
| Replay surface | Captured invocations carry enough context to be replayed against an alternate provider for cross-provider eval. |

## Selected And Proposed Use Cases

| Slot | Use case | Regulator | Status |
|---|---|---|---|
| 1 | UK insurance broking inbound quote qualification | FCA (general insurance distribution) | **Confirmed.** Replaces the fictional Lighthouse domain. |
| 2 | UK legal services intake plus conflict check | SRA | Proposed. Confirmed in R1. |
| 3 | UK wealth management / IFA inbound enquiry | FCA (retail investment advice) | Proposed. Confirmed in R1. |

Each use case must exercise the same adapter surface. Where the inbound
channel differs (email versus broker portal versus IFA enquiry form), the
intake adapter changes; the workflow core does not.

## Ubiquitous Language Work

Before runtime changes, each confirmed use case needs a domain model
defining:

- actors and roles;
- inbound artefacts;
- commands;
- domain events;
- aggregates or lifecycle records;
- value objects;
- state machine;
- policies and invariants tied to the relevant regulator;
- approval points;
- failure and escalation paths;
- safe refs and field placement;
- banned or ambiguous terms.

The model for use case 1 (UK insurance broking inbound quote qualification)
is the primary R1 deliverable. The models for use cases 2 and 3 are added
once R1 has produced a stable shape.

## Treatment Of Existing Names

| Existing term | Reset action |
|---|---|
| Lighthouse | Retired as the project's named exemplar. Its workflow code remains as historical evidence until R3, but the project no longer describes itself through Lighthouse. |
| Support Desk Triage | Retired or replaced. It does not map to any of the three selected UK-regulated use cases. Its value was as a second workflow proof; that role passes to use case 2. |
| Ticket / case / account refs | Replaced with the ubiquitous language of the selected domains. |
| Tool action | Stays as a platform / Tool Gateway term. Domain workflow descriptions use the domain's own verbs. |

## Desired Local POC Shape

The local POC after R4 must run three coherent flows:

1. UK insurance broking inbound quote qualification end to end.
2. UK legal intake / conflict check, sharing connector, audit, and
   projection adapters with use case 1.
3. UK wealth management / IFA inbound enquiry, sharing the same adapters,
   with cross-provider replay evidence across all three.

Each use case needs:

- a business scenario described in domain language;
- contracts at every port the use case touches;
- local synthetic data;
- workflow implementation that reuses the core spine;
- Tool Gateway actions named in the use case's domain;
- BFF / UI inspection;
- invariant-based eval evidence (see `eval-reshape-directions.md`);
- cross-provider replay evidence;
- a short demo path.

## Research Step

R1 begins with a product brief for use case 1 (UK insurance broking
inbound quote qualification). The brief must capture:

- broker / underwriter / customer roles;
- FCA general-insurance-distribution touch points;
- process pain in current manual workflow;
- proposed Chorus-assisted workflow;
- which decisions are agent-proposed and which require human approval;
- approval boundaries derived from regulatory duty;
- safe refs, identifiers, and data placement;
- local demo scope and synthetic data plan;
- adapter mapping (intake, LLM provider, connector, audit, projection,
  observability) for this use case.

Once that brief stabilises, the same template applies to use cases 2 and 3,
focused on the differences that prove adapter reuse.
