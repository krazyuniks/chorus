---
type: project-doc
status: design-freeze
date: 2026-04-29
---

# Chorus - Technical Architecture

## Purpose

This is the reviewer-facing implementation architecture for Chorus. It translates the evidence-first design in `architecture.md` into the technical artefact a senior architect would expect to inspect: system purpose, component boundaries, data flow, contract ownership, runtime topology, testing, operations, and deliberate deferrals.

`architecture.md` remains the decision narrative. This document is the technical map.

## Overview

Chorus is a production-shaped reference implementation for governed multi-agent workflows. It proves that agentic AI can be introduced into a business process without losing durable orchestration, explicit authority boundaries, traceability, safety checks, and regression control.

The Phase 1 business slice is Lighthouse, an inbound-lead concierge for a fictional SMB:

```text
Lead email -> Intake -> Research/qualification -> Draft -> Validation -> Propose/send or escalate
```

The working system is deliberately narrow. The architecture artefacts are deliberately broader: they show how the same controls would scale across enterprise SDLC, multiple teams, provider relationships, prompt/model versioning, and operational support.

## Core Value Proposition

Chorus demonstrates governed agent adoption, not autonomous agent novelty.

The value is the combination of:

- Durable workflow state owned by Temporal.
- Agent identity, prompt references, model routing, lifecycle state, and budgets owned by the Agent Runtime.
- External actions mediated by a Tool Gateway.
- JSON Schema contracts for events, agent outputs, tool calls, and audit records.
- Queryable decision trail and correlation across UI, Temporal, Redpanda, Grafana, and eval fixtures.
- Governance artefacts that explain how the same pattern fits structured enterprise SDLC.

## Technology Stack

| Concern | Technology | Rationale |
|---|---|---|
| Orchestration | Temporal, Python SDK | Durable workflow state, replay, retries, waits, and visible branches. |
| Agent runtime | Python, FastAPI, PydanticAI | Typed agent contracts, runtime policy resolution, inspectable invocation capture. |
| Tool mediation | Python service boundary | Central enforcement for grants, argument schemas, approval, redaction, idempotency, and audit. |
| Messaging | Redpanda Community Edition | Kafka-compatible event stream, console visibility, schema registry. |
| Storage | Postgres | Phase 1 registry, grants, policy materialisation, outbox, projections, decision trail, episodic history, tenant isolation. |
| Frontend | React, Vite, TypeScript, TanStack, Tailwind | Data-first local demo UI and read-only admin surfaces. |
| BFF | FastAPI + SSE | Read-model endpoints and one-way workflow progress updates. |
| Contracts | JSON Schema, generated Pydantic models | Canonical contracts with drift checks. |
| Observability | OpenTelemetry, Grafana stack, Temporal Console, Redpanda Console | Correlated technical and audit evidence. |
| Connector substrate | Mailpit (SMTP capture), Companies House API (UK public company info), Postgres-backed local CRM service | Real-software connectors per no-mocks policy; sandbox-boundary writes only. |
| Tests/eval | pytest, Vitest, Playwright, Temporal replay, trace/eval fixtures | Regression coverage over contracts, infrastructure behaviour, workflow determinism, and governance invariants. |

## Logical Components

| Component | Responsibility | Must not own |
|---|---|---|
| Lighthouse UI | Submit fixture leads, show workflow timeline, decision trail, tool verdicts, runtime registry, grants, routing, and eval status. | Workflow state or policy decisions. |
| BFF | Read projections, expose API/SSE, provide correlation-friendly UI data. | Direct orchestration or connector calls. |
| Temporal workflows | Durable Lighthouse state machine, retries, waits, failure branches, compensation/escalation. | Network IO, model calls, database writes inside deterministic workflow code. |
| Temporal activities | Invoke Agent Runtime, Tool Gateway, persistence, and event publication boundaries. | Long-lived policy ownership. |
| Agent Runtime | Resolve agent version, prompt reference, lifecycle status, tenant policy, model route, budget caps, and invocation identity. | Direct connector authority. |
| Model router | Execute model/provider calls under runtime policy and budget caps. | Business workflow orchestration. |
| Tool Gateway | Enforce grants, argument schemas, modes, redaction, approval, idempotency, and action audit. | Agent reasoning or workflow state. |
| Local connector service | Contract-faithful CRM, company research, email proposal, and email-send modules backed by **real software** (Postgres-backed local CRM, real public APIs for company research, Mailpit for SMTP capture). No mocks or hand-rolled fakes per project policy. | Real production writes to closed third-party platforms. |
| Projection workers | Consume events, update Postgres read models, surface DLQ/escalation evidence. | Critical workflow state. |
| Eval harness | Replay fixture leads and assert path, outcome, governance, contracts, cost, and latency. | Runtime policy mutation. |

## Runtime Flow

```text
UI
  -> BFF
  -> Temporal workflow
  -> activity: resolve/invoke agent through Agent Runtime
  -> activity: model call via routed provider boundary
  -> activity: tool request through Tool Gateway
  -> local connector (real software, sandbox boundary)
  -> Postgres decision trail + outbox
  -> Redpanda events
  -> projection worker
  -> Postgres read model
  -> BFF SSE/UI updates
```

Every workflow run carries a correlation ID across Temporal workflow ID, agent invocation records, tool audit events, Redpanda messages, Grafana traces, and eval results.

## Contract Ownership

| Contract | Canonical source | Runtime use |
|---|---|---|
| Lead intake | JSON Schema | BFF validation and workflow input. |
| Workflow events | JSON Schema + Redpanda Schema Registry | Event publication, projection, UI progress, eval assertions. |
| Agent input/output | JSON Schema -> generated Pydantic | Agent Runtime validation and decision-trail capture. |
| Tool arguments/verdicts | JSON Schema -> generated Pydantic | Tool Gateway validation and audit. |
| Decision trail | JSON Schema + Postgres schema | Audit, review, eval, and demo inspection. |
| Eval fixtures | JSON Schema | Regression assurance for path, outcome, governance, cost, and latency. |

Breaking changes use explicit versioned subjects/topics and migration notes. Additive changes are allowed within a minor contract version when compatibility checks pass.

## Repository Structure Target

The real repo should be organised for asynchronous inspection:

```text
chorus/
├── README.md
├── docs/
│   ├── evidence-map.md
│   ├── overview.md
│   ├── architecture.md
│   ├── technical-architecture.md
│   ├── governance-guardrails.md
│   ├── sdlc-operating-model.md
│   ├── implementation-plan.md
│   ├── demo-script.md
│   └── runbooks/
├── adrs/
├── contracts/
│   ├── events/
│   ├── agents/
│   ├── tools/
│   └── eval/
├── services/
│   ├── bff/
│   ├── agent-runtime/
│   ├── tool-gateway/
│   ├── connectors-fake/
│   └── projection-worker/
├── workflows/
├── frontend/
├── eval/
├── infrastructure/
├── tests/
└── justfile
```

The exact implementation layout can change during repo creation, but the documentation, contracts, services, workflows, eval, and infrastructure boundaries should remain visible.

## Testing and Assurance

| Test type | Evidence |
|---|---|
| Contract tests | JSON Schema samples validate and generated code is current. |
| Workflow replay tests | Temporal histories replay deterministically. |
| Integration tests | Postgres, Redpanda, Temporal, and service boundaries run for real. |
| E2E tests | Lighthouse happy path and failure paths work through the UI. |
| Trace/eval tests | Fixture leads assert expected path, outcome, authority, cost, latency, events, and decision-trail rows. |
| Tenant tests | RLS and tenant-scoped policy fail closed. |

## Operations Surface

Phase 1 is local-first but must still show the operating model:

- `doctor` command verifies services, migrations, schema registration, seeded tenants, and sample workflow readiness.
- Temporal Console shows workflow state, retries, waits, and branches.
- Redpanda Console shows event flow and schema-governed payloads.
- Grafana shows traces, errors, latency, and cost.
- UI audit views show decision trail and tool verdicts.
- Eval output shows behavioural acceptance, not only technical health.

## Deliberate Deferrals

- Real third-party connectors.
- Production auth/SSO.
- Runtime workflow DSL.
- Scylla implementation.
- Production cloud deployment.
- Multiple business workflows.
- Full mutating admin UI.
