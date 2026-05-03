---
type: project-doc
status: design-freeze
---

# Chorus - Overview

## Purpose

This is the high-level project brief for Chorus. It explains what Chorus is,
why it exists, how to review it, and where the architecture and decision record
live.

The sole architecture reference is [`architecture.md`](architecture.md). The
durable decision record is [`../adrs/`](../adrs/).

## What Chorus is

Chorus is a production-shaped reference implementation and architecture artefact set for governed multi-agent workflows.

It demonstrates how specialised AI agents can participate in a durable business process without becoming an opaque, ungoverned automation blob. The core claim is architectural: agentic systems become credible when orchestration, tool authority, traceability, failure handling, schema evolution, evaluation, governance, and change control are treated as first-class engineering concerns.

The first running example shipped inside the repo is **Lighthouse**: an inbound-lead concierge for a fictional small business. A customer email arrives; agents intake, research, qualify, draft, validate, and either propose/send or escalate. Lighthouse is the proof scenario. Chorus is the architecture artefact.

## Who it is for

- **Architecture reviewers** - people evaluating whether the design has credible boundaries, contracts, operations, and failure handling.
- **Delivery teams** - engineers and architects looking for a concrete pattern for governed agentic workflows.
- **Platform and governance teams** - groups defining guardrails for LLM-enabled systems inside controlled enterprise environments.

## What the demo proves

The demo is a trace-first vertical slice, not a broad platform showcase. A real email sent to `leads@chorus.local` through Mailpit starts a durable Lighthouse workflow. From there, a reviewer can inspect:

1. **Workflow durability** - Temporal owns the long-running state machine, retries, replay, timeouts, and visible failure branches.
2. **Governed agent execution** - the agent runtime resolves agent version, prompt, model route, tenant policy, and tool grants before each invocation.
3. **Tool/action mediation** - external actions pass through an explicit gateway with `read`, `propose`, and `write` modes, argument validation, approval hooks, redaction, and audit events.
4. **Decision provenance** - every agent step records input summary, prompt hash, model, tool calls, output, justification, cost, duration, and correlation ID.
5. **Event visibility** - Redpanda carries schema-governed domain events and live progress updates; Redpanda Console shows the stream.
6. **Operational visibility** - Grafana shows traces, workflow timings, gateway verdicts, projection lag, and agent decisions by correlation ID.
7. **Evaluation discipline** - the happy-path fixture checks the expected path, final outcome, workflow events, decision-trail completeness, tool verdict evidence, budget, latency, and correlation IDs.

Phase 1B added the governance and failure fixtures: low-confidence research, validator rejection, connector failure, retry exhaustion with DLQ evidence, escalation, and forbidden-write downgrade/block checks. Those paths are implemented as evidence fixtures on top of the Phase 1A happy path.

The 3-minute walkthrough should be possible without opening an editor. The repo must also stand up to asynchronous technical inspection: [`evidence-map.md`](evidence-map.md) links each claim to the supporting code, contracts, tests, docs, dashboards, or ADRs.

The repo is also an architecture package. A reviewer should be able to inspect `architecture.md`, `governance-guardrails.md`, the ADRs, and the evidence map and see how the Lighthouse implementation maps to enterprise adoption controls.

## How to review Phase 1

Start with the README first-time reviewer checklist for commands. For the evidence narrative, use this order:

1. `overview.md` for the scope and the Phase 1A/1B boundary.
2. `evidence-map.md` for the claim-to-artefact map.
3. `demo-script.md` for the three-minute Mailpit -> Temporal -> BFF/UI -> Grafana -> audit -> eval walkthrough.
4. `governance-evidence.md` for the Phase 1B failure and authority fixture package.
5. `runbook.md` for exact local operations and cross-surface correlation queries.
6. `architecture.md`, `governance-guardrails.md`, and the ADRs for the design rationale.

## Decision record

Architectural decisions are recorded as ADRs under [`../adrs/`](../adrs/). The ADRs explain why the project selected Lighthouse as the evidence slice, Temporal as the orchestration spine, Redpanda for event visibility, explicit Agent Runtime and Tool Gateway boundaries, Postgres-first storage, JSON Schema contracts, trace/eval assurance, and Mailpit SMTP intake.

The architecture document should reflect accepted decisions, but the ADRs remain the source of record for why material choices were made.

## Design-freeze boundaries

- Lighthouse remains the only Phase 1 workflow.
- Phase 1A includes the happy path; Phase 1B adds the visible failure paths needed to prove governance.
- Mutating admin features stay out of the UI; registry, routing, grants, and audit are read-only there.
- Connector integrations run real software in sandbox/local mode: Mailpit for email, public APIs for research where suitable, and a Postgres-backed local CRM service.
- Governance, guardrail, architecture, and evidence documentation are first-class Phase 1 deliverables.
- Screenshot or screencast packaging remains optional in Phase 1C; the current review path is command-, evidence-map-, and governance-evidence-led.

## What Chorus is not

- Not a SaaS product or hosted service.
- Not a generic agent framework competing with LangGraph, PydanticAI, OpenAI Agents SDK, CrewAI, or vendor platforms.
- Not a checklist implementation of every interesting agentic-AI primitive.
- Not a Scylla, Kubernetes, or cloud-infrastructure demo in Phase 1.
- Not a production CRM/email/payment integration suite. Connectors are sandbox/local implementations behind the same gateway boundary intended for real integrations.

## Design inputs

- A recent architecture scan of 2026 agentic workflow systems: durable execution, governed tool/runtime layers, MCP/A2A-style integration boundaries, trace evaluation, and enterprise observability are the relevant direction.
- A deliberate preference for narrow, inspectable vertical slices over broad framework skeletons.
- A requirement that architecture, governance, contracts, eval, and operations are documented together.

## Out of scope for Phase 1

- Production-grade auth and SSO.
- Real third-party connectors.
- Runtime-editable workflow DSLs.
- Scylla implementation.
- Full admin UI for every registry and policy mutation.
- Production AWS deployment.
- A second business workflow beyond Lighthouse.
