---
type: project-doc
status: active
date: 2026-05-19
---

# Domain Refocus Plan

## Goal

Choose and model a real operational domain before more Chorus feature
development. The chosen domain must give the local POC a clear business
benefit, concrete language, realistic policies, and visible outcomes.

The target is not "AI routes messages". The target is a business process where
AI assistance is useful because the work has ambiguity, context gathering,
policy checks, handoffs, and audit requirements.

## Domain Selection Criteria

The domain must satisfy these criteria:

| Criterion | Requirement |
|---|---|
| Real client pain | A potential client can recognise the process and explain why delay, inconsistency, or manual triage is costly. |
| Rich language | The process has named actors, artefacts, states, rules, and exception paths that can become ubiquitous language. |
| Workflow shape | Work enters through an intake channel, moves through classification/context/action/approval/completion, and has durable state. |
| Governance fit | Some actions can be automated, some can only be proposed, and some need explicit approval. |
| Local evidence fit | The domain can be demonstrated with synthetic local data and sandbox connectors. |
| Contract-first fit | The important boundaries can be described as business contracts before code. |
| Deployment independence | The local POC can be useful without Amazon, Kubernetes, production SSO, or real third-party credentials. |

## Candidate Domains

These are candidates, not final decisions.

| Candidate | Why it could work | Risks |
|---|---|---|
| Managed service operations | Strong fit for Radian IT context; request intake, triage, enrichment, approval, and customer communication are credible. | Must avoid generic "ticket desk" language and choose a specific service workflow. |
| Client onboarding and compliance evidence | Rich documents, policy checks, missing-information loops, approvals, and audit trails. | Could become document-processing heavy if not scoped tightly. |
| Field service request fulfilment | Clear states, scheduling, parts/resource checks, customer comms, and escalation. | Calendar/resource planning can expand quickly. |
| Procurement or vendor qualification | Strong approval and evidence trail; useful for governance story. | May feel less connected to the existing Lighthouse lead workflow. |
| Incident response and change control | Strong audit, severity, approval, and post-incident linkage. | Too close to platform operations unless tied to a business domain. |

The reset should select one primary domain and one optional follow-up use case.
Do not keep adding unrelated examples.

## Ubiquitous Language Work

Before runtime changes, create a domain model that defines:

- actors and roles;
- inbound artefacts;
- commands;
- domain events;
- aggregates or lifecycle records;
- value objects;
- state machine;
- policies and invariants;
- approval points;
- failure and escalation paths;
- safe refs and field placement;
- banned or ambiguous terms.

The model should be understandable without knowing Chorus internals.

## Terms To Review

These existing terms need explicit treatment:

| Term | Current issue | Reset action |
|---|---|---|
| Lighthouse | Sounds like a product name but is actually a use case. | Keep only if it remains a named workflow under Chorus; otherwise rename to a domain term. |
| Support Desk Triage | Sounds like a different product and has weak client context. | Reframe, rename, or replace after domain selection. |
| Ticket | Generic helpdesk term without a defined business setting. | Replace with the selected domain artefact if possible. |
| Case | Ambiguous unless the chosen domain uses case management language. | Keep only with a glossary and lifecycle. |
| Account | Could imply real customer records or personal data. | Use a more precise domain term or keep only as synthetic safe ref. |
| Tool action | Platform term, not domain language. | Use in architecture; hide from business workflow descriptions where possible. |

## Desired Use-Case Shape

The local POC should end with two or three coherent flows:

1. A primary business workflow that a client can understand in one paragraph.
2. A second flow or branch that proves reuse without feeling like a different
   product.
3. Optional connector approval/idempotency evidence if it supports the same
   domain.

Each use case needs:

- a business scenario;
- domain contracts;
- local synthetic data;
- workflow implementation;
- Tool Gateway actions with domain names;
- BFF/UI inspection;
- eval and replay evidence;
- demo script and review path.

## Research Step

The next reset step should spend time on domain research before choosing. The
output should be a short product/domain brief, not a broad market report:

- audience and buyer/user;
- process pain;
- current manual workflow;
- proposed Chorus-assisted workflow;
- why agents help;
- risks and approval boundaries;
- local demo scope;
- vocabulary and event model;
- benefits that can be shown in the POC.
