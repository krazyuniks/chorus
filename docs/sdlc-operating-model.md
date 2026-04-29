---
type: project-doc
status: design-freeze
date: 2026-04-29
---

# Chorus - SDLC Operating Model

## Purpose

This document describes how Chorus demonstrates agentic AI adoption inside a structured SDLC. It is aimed at enterprise architecture reviewers who care about programme-wide adoption, governance, quality gates, versioning, provider collaboration, and team enablement.

This document covers **outer-loop / programme-level** SDLC concerns. The complementary **inner-loop** concerns — an individual developer's AI-assisted work cycle, structured per epic with schema-governed contracts and a JSONL audit trail — are addressed by [Woof](https://github.com/krazyuniks/woof), Chorus's sister artefact.

The implementation remains a reference slice. The operating model shows how the same patterns scale across teams.

## Lifecycle Stages

| Stage | Output | Gate |
|---|---|---|
| 1. Discovery | Problem framing, target workflow, risk classification, evidence goals. | Stakeholders agree the workflow is appropriate for agentic automation. |
| 2. Architecture definition | Technical architecture, governance guardrails, ADRs, contracts, eval strategy. | Discovery questions are closed or explicitly deferred. |
| 3. Contract definition | JSON Schemas, OpenAPI where needed, seed fixtures, acceptance traces. | Contract validation passes and owners are named. |
| 4. Implementation | Workflow, agents, gateway, connectors, projections, UI, observability. | Quality gates pass against real services. |
| 5. Evaluation and assurance | Trace/eval fixtures, replay tests, failure fixtures, cost/latency checks. | Behavioural and governance checks pass. |
| 6. Release/readiness | Demo script, runbook, known limitations, rollback/degradation notes. | Reviewer can run or inspect the slice without hidden context. |
| 7. Operate and improve | Audit review, provider changes, prompt/model route promotion, incident learnings. | Changes preserve traceability, contracts, and eval coverage. |

## Artefact Set

| Artefact | Purpose |
|---|---|
| `README.md` | Entry point and review path. |
| `evidence-map.md` | Engineering claims and supporting artefacts. |
| `overview.md` | Narrative and scope boundaries. |
| `architecture.md` | Decision narrative and Phase 1 defaults. |
| `technical-architecture.md` | Implementation architecture map. |
| `governance-guardrails.md` | Enterprise AI guardrails and control matrix. |
| `sdlc-operating-model.md` | Delivery lifecycle, gates, roles, and change control. |
| `adrs/` | Accepted Phase 1 architectural decisions. |
| `implementation-plan.md` | Phases, milestones, work breakdown, and parallel workstreams. |
| `demo-script.md` | Guided walkthrough. |
| Contracts | JSON Schema/OpenAPI/Pydantic generated artefacts after implementation starts. |
| Eval fixtures | Behavioural and governance regression evidence. |

## Roles and Responsibilities

| Role | Responsibility in an enterprise programme |
|---|---|
| Enterprise/lead architect | Owns guardrails, target architecture, adoption roadmap, and stakeholder alignment. |
| Solution architect | Applies the pattern to a concrete workflow and documents exceptions. |
| Product owner | Owns business outcome, acceptable automation boundary, and escalation policy. |
| Agent/runtime engineer | Implements workflows, runtime integration, gateway mediation, and tests. |
| Data/security representative | Reviews data movement, tenant boundaries, retention, redaction, and secrets. |
| Operations owner | Owns observability, runbooks, incident paths, and provider operational support. |
| Reviewer/approver | Signs off contract changes, risky tool grants, and model/prompt promotions. |

The role split is intended to make ownership explicit: guardrails are defined centrally, workflow-specific exceptions are documented, and runtime authority is enforced by code rather than informal convention.

## Quality Gates

| Gate | Required checks |
|---|---|
| Architecture gate | ADRs updated; technical architecture reflects implementation; deferrals listed. |
| Contract gate | Schemas valid; generated models current; sample payloads pass; compatibility considered. |
| Workflow gate | Temporal replay tests pass; deterministic boundary respected. |
| Runtime governance gate | Agent versions, prompts, model route, budgets, and tool grants are inspectable. |
| Safety/eval gate | Trace fixtures pass for happy path and failure/governance cases. |
| Observability gate | Correlation ID works across UI, Temporal, Redpanda, Grafana, audit, and eval output. |
| Documentation gate | README, runbook, demo script, and architecture docs match the current implementation. |

## Change Control

| Change type | Required treatment |
|---|---|
| Workflow state or branch | ADR if architectural; replay test; trace/eval update if behaviour changes. |
| Agent prompt | Prompt ID/hash update; eval impact checked; decision trail remains queryable. |
| Model route | Runtime policy change; cost/latency budget reviewed; validator diversity checked where relevant. |
| Tool grant | Config/CLI change; audit event; risky writes require approval path. |
| Event/agent/tool contract | Schema versioning, generated-code update, samples, compatibility notes. |
| Connector behaviour | Gateway contract unchanged unless ADR/contract update justifies it. |
| Governance exception | Document owner, reason, expiry/review point, and compensating control. |

## Provider Collaboration Model

An enterprise LLM programme needs a durable provider model. Chorus should demonstrate the shape even if Phase 1 uses a small local policy file:

- Provider/model catalogue and approved-use notes.
- Hosting and data-handling assumptions.
- Safety/eval expectations before model promotion.
- Versioning and deprecation handling for model routes.
- Operational support expectations for incidents, rate limits, and latency.
- Cost attribution by tenant/workflow/agent role.
- Fallback and degradation rules.

## Team Enablement

Chorus should be usable as a teaching artefact:

- New architects can read the artefact set in order and understand the pattern.
- Engineers can see where contracts, workflows, runtime policy, gateway rules, and eval fixtures belong.
- Reviewers can inspect whether a proposed agent change affects authority, safety, cost, or audit.
- Stakeholders can see which production concerns are implemented, deferred, or intentionally excluded.

## Phase 1 SDLC Evidence

The Phase 1 repo should demonstrate:

- A complete artefact set before code expands.
- Contract-first implementation.
- Durable workflow replay tests.
- Real-service integration tests.
- Behavioural trace/eval fixtures.
- Explicit guardrails for agent authority and provider routing.
- Documentation that stays aligned with implementation.
