---
type: project-doc
status: design-freeze
---

# Chorus - Overview

## What Chorus is

Chorus is a production-shaped reference implementation and architecture artefact set for governed multi-agent workflows.

It demonstrates how specialised AI agents can participate in a durable business process without becoming an opaque, ungoverned automation blob. The core claim is architectural: agentic systems become credible when orchestration, tool authority, traceability, failure handling, schema evolution, evaluation, governance, and SDLC change control are treated as first-class engineering concerns.

The first running example shipped inside the repo is **Lighthouse**: an inbound-lead concierge for a fictional small business. A customer email arrives; agents intake, research, qualify, draft, validate, and either propose/send or escalate. Lighthouse is the proof scenario. Chorus is the architecture artefact.

## Who it is for

- **Architecture reviewers** - people evaluating whether the design has credible boundaries, contracts, operations, and failure handling.
- **Delivery teams** - engineers and architects looking for a concrete pattern for governed agentic workflows.
- **Platform and governance teams** - groups defining guardrails for LLM-enabled systems inside a structured SDLC.

## What the demo proves

The demo is a trace-first vertical slice, not a broad platform showcase. A single-page UI at `localhost:3000` accepts a pre-loaded lead email and starts a durable workflow. From there, a reviewer can inspect:

1. **Workflow durability** - Temporal owns the long-running state machine, retries, replay, timeouts, and visible failure branches.
2. **Governed agent execution** - the agent runtime resolves agent version, prompt, model route, tenant policy, and tool grants before each invocation.
3. **Tool/action mediation** - external actions pass through an explicit gateway with `read`, `propose`, and `write` modes, argument validation, approval hooks, redaction, and audit events.
4. **Decision provenance** - every agent step records input summary, prompt hash, model, tool calls, output, justification, cost, duration, and correlation ID.
5. **Event visibility** - Redpanda carries schema-governed domain events and live progress updates; Redpanda Console shows the stream.
6. **Operational visibility** - Grafana shows traces, latency, errors, and cost per workflow.
7. **Evaluation discipline** - fixture leads exercise expected paths, tool grants, escalation rules, cost budgets, and trace-contract checks.

The demo deliberately shows failure modes alongside the happy path:

- Low-confidence research triggers a deeper-research branch.
- Validator rejection loops back to the drafter with structured reasoning.
- A forced connector failure routes to compensation or human escalation.
- A prohibited write action is blocked or downgraded to proposal mode by the tool gateway.

The 3-minute walkthrough should be possible without opening an editor. The repo must also stand up to asynchronous technical inspection.

The repo also needs to stand up as an architecture package. A reviewer should be able to inspect `technical-architecture.md`, `governance-guardrails.md`, and `sdlc-operating-model.md` and see how the Lighthouse implementation maps to enterprise adoption controls.

## Design-freeze boundaries

- Lighthouse remains the only Phase 1 workflow.
- Phase 1 must include the happy path and the visible failure paths needed to prove governance.
- Mutating admin features stay out of the UI; registry, routing, grants, and audit are read-only there.
- Connector integrations are contract-faithful fakes with local side effects only.
- Governance, guardrail, and SDLC documentation are first-class Phase 1 deliverables.

## What Chorus is not

- Not a SaaS product or hosted service.
- Not a generic agent framework competing with LangGraph, PydanticAI, OpenAI Agents SDK, CrewAI, or vendor platforms.
- Not a checklist implementation of every interesting agentic-AI primitive.
- Not a Scylla, Kubernetes, or cloud-infrastructure demo in Phase 1.
- Not a real CRM/email/payment integration suite. Connectors are contract-faithful fakes.

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
