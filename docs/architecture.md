---
type: project-doc
status: design-freeze
version: 1.0.0
date: 2026-04-29
---

# Chorus - Architecture

## Purpose

This is the sole architecture document for Chorus. It defines the principles,
domain language, component boundaries, runtime topology, data contracts,
operational controls, testing surface, and deliberate deferrals for the Phase 1
reference implementation.

The companion high-level document is [`overview.md`](overview.md). The overview
explains what Chorus is and how to review it. This document explains how Chorus
is designed. The durable decision record lives in [`../adrs/`](../adrs/).

## Audience

This document is written for architecture reviewers, platform engineers,
runtime engineers, governance reviewers, and delivery teams evaluating a
governed agent workflow pattern. It is project-facing and implementation-facing:
it should be possible to inspect the repository and map each architectural
claim to a concrete artefact, contract, service boundary, or deferred item.

## Architectural Position

Chorus is an outer-loop, programme-level architecture for governed multi-agent
workflows. It addresses runtime architecture, provider and model governance,
tool authority, auditability, evaluation, observability, and SDLC adoption
controls for agent-enabled business processes.

The inner-loop counterpart is Woof: an SDLC tool for the developer's own
AI-assisted work cycle - discovery, definition, breakdown, execution, and gate
- with schema-governed contracts and a per-epic JSONL audit trail. Woof is not a
runtime dependency of Chorus. The relationship is conceptual: Chorus governs
agentic business workflows; Woof governs agent-assisted software delivery.

## Core Principles

| Principle | Architectural consequence |
|---|---|
| Evidence before breadth | Phase 1 implements one narrow vertical slice with inspectable controls instead of a broad generic platform skeleton. |
| Durable state has one owner | Temporal owns long-running workflow state, retries, timers, waits, branches, and replay. |
| Agents have no ambient authority | Agents reason and propose. External action authority is granted and enforced by the Tool Gateway outside prompt text. |
| Runtime identity is explicit | Agent version, lifecycle state, prompt reference, model route, budget cap, tenant policy, and invocation ID are resolved before each invocation. |
| Contracts are first-class assets | Events, agent inputs/outputs, tool calls, gateway verdicts, audit records, and eval fixtures are governed by JSON Schema. |
| Audit and telemetry answer different questions | Postgres decision trail captures accountability evidence; OpenTelemetry and consoles capture operational behaviour. |
| Evaluation is a release control | Trace/eval fixtures assert path, outcome, authority, budget, latency, and contract invariants. |
| Local evidence uses real software | Mailpit, Postgres, Redpanda, Temporal, and local connector services run for real in sandbox/local mode. |
| Deferrals are explicit | Production auth, closed-system writes, cloud deployment, Scylla, a workflow DSL, and additional workflows are named as out of scope for Phase 1. |

## System Context

Chorus demonstrates a governed agent workflow through the Lighthouse proof
scenario. Lighthouse is an inbound-lead concierge for a fictional small
business.

```text
Customer email
  -> Mailpit SMTP intake
  -> Temporal poll activity
  -> Lighthouse workflow
  -> Agent Runtime
  -> Model/provider boundary
  -> Tool Gateway
  -> Local/sandbox connectors
  -> Postgres decision trail and outbox
  -> Redpanda events
  -> Projection worker
  -> BFF and UI progress
  -> Eval and observability evidence
```

The implementation is intentionally narrow. The architecture is broader: it
shows the boundaries and controls an organisation would need before scaling
agent workflows across teams, providers, and business processes.

## Phase 1 Scope

| Phase | Scope | Exit evidence |
|---|---|---|
| Phase 0 - Foundation | Documentation, ADRs, local runtime scaffold, service layout, command runner, contracts scaffold, and review path. | Repo opens cleanly; docs and ADRs are linked; local prerequisites and scaffold boundaries are explicit. |
| Phase 1A - Happy path | Mailpit SMTP intake, Temporal Lighthouse workflow, Agent Runtime, Tool Gateway, Postgres projections, Redpanda events, UI progress, audit trail, observability, and happy-path eval. | A reviewer can send a fixture email, follow one workflow by correlation ID, and run the happy-path eval. |
| Phase 1B - Governance/failure evidence | Blocked write, low-confidence research, validator rejection, connector failure, retry exhaustion, and escalation fixtures. | Failure fixtures produce expected branches, audit verdicts, DLQ or escalation records, and passing eval checks. |
| Phase 1C - Review packaging | Final README, screenshots or notes, demo script, evidence map, and architecture/governance/SDLC cross-links. | An asynchronous reviewer can inspect the evidence path without hidden context. |

## Domain Language

Chorus's core domain is governed agent workflow execution. The important nouns
are runtime and governance concepts, not a generic agent framework vocabulary.

| Concept | Meaning |
|---|---|
| Tenant | A logical customer or business boundary. Phase 1 seeds pretend tenants to exercise isolation. |
| Lead | Parsed inbound email payload that starts a Lighthouse workflow. |
| Workflow run | One durable Lighthouse execution owned by Temporal. |
| Workflow step | A named state or transition in the Lighthouse workflow. |
| Agent | A governed role capable of producing structured output for a workflow step. |
| Agent version | A specific registered agent configuration with lifecycle state and prompt reference. |
| Prompt reference | Stable ID and Git-tracked template hash captured at invocation time. |
| Provider | Approved model provider in the runtime catalogue. |
| Model route | Policy-selected provider/model/parameters for an agent role and task kind. |
| Budget policy | Cost and latency caps applied per invocation, workflow, tenant, and role. |
| Tool | External action or lookup exposed behind the Tool Gateway. |
| Tool grant | `(agent_id, tenant_id, tool, mode)` authority record. Modes are `read`, `propose`, and `write`. |
| Tool call | Structured request from an agent/runtime boundary to the Tool Gateway. |
| Gateway verdict | Allow, rewrite, propose, block, or approval-required decision emitted by the gateway. |
| Connector | Local or sandbox implementation that performs the tool action after gateway approval. |
| Decision trail entry | Durable audit record for an agent invocation, model route, prompt, output, cost, duration, and correlation ID. |
| Audit event | Durable record for authority-sensitive events, including tool calls and gateway verdicts. |
| Outbox event | Transactional event row written with service-owned state and relayed to Redpanda. |
| Projection | Read model derived from events for UI and inspection surfaces. |
| Eval fixture | Governed test case that asserts expected workflow path, outcome, authority, budget, latency, and contract evidence. |

## Lighthouse Workflow

Lighthouse is the only Phase 1 business workflow.

```text
intake
  -> research/qualification
  -> draft
  -> validation
  -> propose/send
  -> complete

failure/governance branches:
  -> low-confidence research -> deeper research
  -> validator rejection -> draft
  -> connector failure -> retry/compensate/escalate
  -> forbidden write -> block or proposal downgrade
```

The demo trigger is real SMTP intake via Mailpit. A fixture email is sent to
`leads@chorus.local` through Mailpit's SMTP port. A Temporal poll activity reads
Mailpit's HTTP API, deduplicates by Message-ID, parses the email into the lead
intake contract, and starts a workflow run.

UI fixture replay can exist as a development convenience, but the public demo
path leads with SMTP intake because it demonstrates an integration boundary
rather than a hand-fed form.

## Technology Stack

| Concern | Technology | Rationale |
|---|---|---|
| Durable orchestration | Temporal with Python SDK | Long-running workflow state, replay, retries, timers, signals, waits, and branch visibility. |
| Agent runtime | Python, FastAPI, PydanticAI | Typed agent contracts, policy resolution, structured model output, and inspectable invocation capture. |
| Tool mediation | Python/FastAPI service boundary | Central enforcement for grants, argument schemas, modes, approval, redaction, idempotency, and audit. |
| Messaging | Redpanda Community Edition | Kafka-compatible event stream, visible console, and Schema Registry for event subjects. |
| Storage | Postgres | Phase 1 registry, grants, routing policy, outbox, projections, decision trail, episodic history, and tenant isolation. |
| Frontend | React, Vite, TypeScript, TanStack, Tailwind | Dense data-first UI and read-only admin surfaces. |
| BFF | FastAPI plus server-sent events | Read model API and one-way workflow progress stream. |
| Contracts | JSON Schema and generated Pydantic models | Language-neutral contract source with generated runtime types and drift checks. |
| Connectors | Mailpit, Companies House API, Postgres-backed local CRM | Real software in sandbox/local mode with no production writes to closed third-party systems. |
| Observability | OpenTelemetry, Grafana stack, Temporal Console, Redpanda Console | Correlated technical and audit evidence. |
| Assurance | pytest, Vitest, Playwright, Temporal replay, trace/eval fixtures | Regression coverage over contracts, infrastructure behaviour, workflow determinism, and governance invariants. |

## Runtime Topology

```text
                           +----------------------+
                           |     Lighthouse UI    |
                           +----------+-----------+
                                      |
                                      v
                           +----------------------+
                           | FastAPI BFF + SSE    |
                           +----------+-----------+
                                      |
                                      v
   +---------+       +---------------+---------------+
   | Mailpit | ----> | Temporal workflow + activities |
   +---------+       +---------------+---------------+
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
        +----------------------+            +----------------------+
        | Agent Runtime        |            | Tool Gateway         |
        | - agent registry     |            | - grants             |
        | - prompt references  |            | - schema validation  |
        | - model routing      |            | - approval/verdicts  |
        | - budgets            |            | - audit events       |
        +----------+-----------+            +----------+-----------+
                   |                                   |
                   v                                   v
        +----------------------+            +----------------------+
        | Model/provider       |            | Local connectors     |
        | boundary             |            | CRM/research/email   |
        +----------+-----------+            +----------+-----------+
                   |                                   |
                   +-----------------+-----------------+
                                     v
                           +----------------------+
                           | Postgres             |
                           | decision trail       |
                           | policy/read models   |
                           | outbox               |
                           +----------+-----------+
                                      |
                                      v
                           +----------------------+
                           | Redpanda             |
                           | events/schema reg.   |
                           +----------+-----------+
                                      |
                                      v
                           +----------------------+
                           | Projection worker    |
                           +----------------------+
```

Each workflow run carries a correlation ID across Temporal workflow ID, agent
invocation records, tool audit events, Redpanda messages, Postgres projections,
OpenTelemetry traces, UI views, and eval output.

## Repository Structure

The repository is organised so a reviewer can inspect boundaries without
reverse-engineering the codebase.

```text
chorus/
├── README.md
├── docs/
│   ├── overview.md
│   ├── architecture.md
│   ├── evidence-map.md
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
│   ├── intake-poller/
│   ├── agent-runtime/
│   ├── tool-gateway/
│   ├── connectors-local/
│   └── projection-worker/
├── workflows/
├── frontend/
├── eval/
├── infrastructure/
├── tests/
├── compose.yml
├── justfile
└── pyproject.toml
```

## Component Boundaries

| Component | Owns | Does not own |
|---|---|---|
| Lighthouse UI | Workflow progress views, decision trail views, tool verdict views, runtime/grants/routing read-only inspection, eval status. | Workflow state, policy mutation, connector calls. |
| BFF | Read endpoints, SSE progress stream, correlation-friendly UI data, development fixture replay endpoint. | Direct orchestration logic, direct connector calls, model calls. |
| Intake poller | Mailpit HTTP polling, Message-ID dedupe, lead parsing, workflow start. | Business decisions after workflow start. |
| Temporal workflow | Durable state machine, timers, retries, waits, failure branches, compensation/escalation flow. | Network IO, model calls, database writes, connector calls inside deterministic workflow code. |
| Temporal activities | Calls into Agent Runtime, Tool Gateway, persistence, and event publication boundaries. | Long-lived policy ownership. |
| Agent Runtime | Agent registry resolution, lifecycle state, prompt references, tenant policy, model routing, budget caps, invocation IDs, decision-trail capture. | External action authority. |
| Model/provider boundary | Provider SDK invocation under runtime policy and budget controls. | Workflow state, tool authority, prompt governance outside registered references. |
| Tool Gateway | Tool grants, argument schema validation, mode enforcement, redaction, idempotency, approval hooks, gateway verdicts, action audit. | Agent reasoning, model routing, workflow state. |
| Local connector service | Contract-faithful CRM, company research, email proposal, and email send modules backed by sandbox/local software. | Production writes to closed third-party platforms. |
| Projection worker | Redpanda consumption, Postgres read-model updates, DLQ/escalation projections. | Critical workflow state. |
| Eval harness | Fixture execution and assertions over path, outcome, contracts, authority, cost, latency, and persisted evidence. | Runtime policy mutation. |

## Workflow Architecture

Temporal workflows are the orchestration spine. Workflow code is deterministic:
no random values, wall-clock time, network IO, database IO, model calls, or
connector calls run inside workflow logic. Fallible and effectful operations are
activities.

Workflow changes require replay coverage. The workflow should remain readable
in Temporal Console: states and branches are part of the review surface, not an
implementation detail hidden in agent loops.

Redpanda events are used for visibility, projections, and async consumers. They
do not own critical workflow state.

## Agent Runtime Architecture

The Agent Runtime exists because "agent X ran" is not enough evidence. Before
each invocation, the runtime resolves:

- tenant and workflow context;
- agent ID, role, version, owner, lifecycle state, and capability tags;
- prompt reference and prompt hash;
- provider/model route, parameters, and fallback policy;
- budget caps and cost attribution dimensions;
- invocation ID and correlation ID;
- expected input/output contract.

The runtime captures a decision-trail entry for every invocation. The record is
created early enough that failed invocations remain inspectable.

Phase 1 runtime mutation is CLI/config driven. The UI shows runtime state
read-only.

## Model Routing

Model choice is policy, not scattered SDK code. The routing key is:

```text
(tenant_id, agent_role, task_kind, tenant_tier) -> provider/model/parameters/budget
```

Default Phase 1 posture:

| Task category | Route posture |
|---|---|
| Classification and simple extraction | Small/fast model where sufficient. |
| Structured qualification | Reliable mid-tier model. |
| Drafting and nuanced reasoning | Stronger reasoning model. |
| Validation | Different provider or model family from producer where available. |

Provider/model changes require eval impact review because they can alter
workflow behaviour without code changes.

## Tool Gateway Architecture

The Tool Gateway is the authority boundary. Agents never call connectors
directly.

For every tool call, the gateway:

1. validates the request against the tool argument schema;
2. resolves the `(agent_id, tenant_id, tool, mode)` grant;
3. enforces `read`, `propose`, or `write` mode;
4. applies tenant scoping and redaction policy;
5. enforces idempotency;
6. triggers approval hooks for risky writes;
7. emits a gateway verdict and audit event;
8. calls the connector only if the verdict permits it.

Verdicts are explicit: `allow`, `rewrite`, `propose`, `approval_required`, or
`block`.

MCP can be an integration protocol at the tool boundary in a later phase. It is
not treated as an authority model by itself.

## Connector Substrate

Phase 1 connectors use real software in sandbox/local mode:

| Connector area | Phase 1 implementation |
|---|---|
| SMTP intake | Mailpit receives fixture lead email and exposes messages via HTTP API. |
| Email proposal/send | Mailpit captures all outbound SMTP. |
| CRM | Postgres-backed local service implementing lookup/create/update contract paths. |
| Company research | Public company-information APIs where suitable, starting with Companies House for UK company examples. |

The local connector service is contract-faithful and sits behind the Tool
Gateway. Phase 1 does not write to real CRMs, production mailboxes, payment
systems, or other closed third-party platforms.

## Contracts and Schema Evolution

JSON Schema is canonical for cross-boundary contracts:

| Contract | Canonical source | Runtime use |
|---|---|---|
| Lead intake | `contracts/events/` | Mailpit parser and workflow input validation. |
| Workflow events | `contracts/events/` plus Redpanda Schema Registry | Event publication, projection, UI progress, eval assertions. |
| Agent inputs/outputs | `contracts/agents/` -> generated Pydantic | Runtime validation and decision-trail capture. |
| Tool calls/verdicts | `contracts/tools/` -> generated Pydantic | Gateway validation and audit. |
| Audit records | `contracts/events/` and Postgres schema | Review, eval, and traceability. |
| Eval fixtures | `contracts/eval/` | Regression checks for path, outcome, governance, cost, and latency. |

Contract rules:

- Additive changes are allowed within a compatible minor version when samples
  and generated models pass.
- Breaking changes use versioned subjects/topics and migration notes.
- CI fails when schemas, samples, generated models, or compatibility
  assumptions drift.
- PydanticAI dynamic schema support is allowed only when static generation is
  awkward and the exception is documented.

## Storage Architecture

Phase 1 is Postgres-first.

Postgres stores:

- tenants and seed tenant metadata;
- agent registry and lifecycle state;
- provider/model routing policy materialisation;
- tool grants;
- decision trail;
- action audit records;
- episodic workflow history where needed;
- workflow read models and projections;
- transactional outbox rows;
- local connector state, including the CRM service;
- optional pgvector-backed semantic memory only if the Lighthouse research path
  needs it.

Temporal uses its own persistence. Redpanda carries event streams and schema
visibility. Redpanda does not replace workflow state or audit storage.

Tenant isolation is represented through `tenant_id` on all tenant-owned tables,
row-level security, tenant-scoped policy, and tests that fail closed.

Scylla remains a deferred production option for append-heavy long-retention
decision trail or episodic history workloads. Phase 1 keeps storage boundaries
clear enough that this remains an adapter change, not an architectural rewrite.

## Events, Outbox, and Projections

Service-owned writes that emit events use transactional outbox:

```text
write service state + outbox row in one Postgres transaction
  -> relay publishes to Redpanda
  -> relay marks outbox row sent
  -> projection worker consumes event
  -> projection worker updates read model idempotently
```

Outbox does not remove every crash window around model/provider calls. It
ensures that once a result or audit record is persisted, the event announcing it
is not lost. Activities and gateway calls still use idempotency keys.

Consumers dedupe by event ID, workflow ID, invocation ID, or idempotency key as
appropriate.

## Frontend and BFF

The UI is a dense, data-first inspection surface. It is not a marketing landing
page and it does not own business state.

Expected views:

- workflow run list and timeline;
- Mailpit-triggered lead run details;
- decision trail;
- tool verdicts and audit;
- runtime registry;
- grants;
- model routing policy;
- eval status;
- links to Temporal, Redpanda, Grafana, and Mailpit surfaces by correlation ID.

The BFF reads Postgres projections and exposes server-sent events for one-way
progress updates. Refresh and reconnect must be reliable because the source of
truth is the projection, not an ephemeral browser stream.

## Observability and Audit

Chorus separates auditability from operational telemetry.

| Surface | Purpose |
|---|---|
| Postgres decision trail | Accountability record for agent invocations, prompt/model identity, output, cost, duration, and correlation. |
| Postgres tool audit | Authority record for tool requests, gateway verdicts, approval hooks, and connector outcomes. |
| Temporal Console | Workflow state, retries, waits, branches, and replay evidence. |
| Redpanda Console | Event flow, schemas, DLQ topics, and projection feed visibility. |
| Grafana/OpenTelemetry | Traces, logs, metrics, latency, errors, and cost signals. |
| UI audit views | Reviewer-friendly projection of workflow, agent, and tool evidence. |
| Eval output | Behavioural acceptance and governance invariant results. |

Every material operation must carry a correlation ID.

## Evaluation and Assurance

The trace/eval harness is a Phase 1 architectural pillar. It asserts whether
observed behaviour is acceptable, not merely whether the system produced text.

Fixture expectations include:

- expected workflow path;
- expected final outcome: send, propose, escalate, or reject;
- allowed tool actions;
- blocked or downgraded write attempts;
- validator route diversity where available;
- emitted event contract validity;
- decision-trail and audit-record completeness;
- latency and cost budget limits;
- retry, DLQ, compensation, or escalation behaviour for failure cases.

Phase 1A includes the happy-path eval. Phase 1B extends coverage to governance
and failure fixtures.

## Governance Runtime Controls

Chorus turns governance into runtime-enforced boundaries:

| Governance concern | Runtime control |
|---|---|
| Prompt changes | Prompt ID and hash captured per invocation; eval impact reviewed. |
| Provider/model changes | Routing policy records provider/model parameters, budget, and validator diversity. |
| Tool authority | Gateway grants and mode enforcement outside prompts. |
| Unsafe customer output | Explicit validation workflow state before propose/send. |
| Tenant isolation | `tenant_id`, RLS, tenant-scoped policy, and isolation tests. |
| Auditability | Required decision-trail and tool-audit fields with contract checks. |
| Regression | Trace/eval fixtures gate behavioural changes. |

The UI can inspect runtime governance state in Phase 1. Mutation remains
CLI/config driven.

## Security and Data Boundaries

Phase 1 is a single-user local reference implementation, not a production SaaS.
Security architecture is still explicit:

- no production customer data;
- no production auth/SSO in Phase 1;
- secrets loaded from local environment files or injected environment
  variables, never committed;
- model/provider credentials held only at the model/router boundary;
- all tenant-owned data carries `tenant_id`;
- tool arguments are schema-validated and tenant-scoped before connector
  execution;
- audit redaction policy applies before sensitive data is persisted or emitted;
- closed third-party systems are not written to in Phase 1.

Production identity, RBAC, SSO, secrets management, incident integration, and
cloud network controls are deferred.

## Error Handling and Resilience

| Failure | Phase 1 handling |
|---|---|
| Activity failure | Temporal retry policy, then workflow branch for compensation or escalation. |
| Connector failure | Gateway/connector error classification, retry where transient, escalation or DLQ where exhausted. |
| Provider failure | Runtime fallback/degradation policy where configured; otherwise explicit workflow failure or escalation. |
| Low-confidence research | Deeper-research branch. |
| Validator rejection | Return to draft with structured reason. |
| Forbidden write | Gateway block or proposal downgrade with audit verdict. |
| Projection failure | Redpanda consumer retry and DLQ; workflow state remains in Temporal. |
| Duplicate intake email | Message-ID dedupe before workflow start. |

Failure branches are part of the evidence. They must appear in workflow history,
audit records, eval assertions, and reviewer-facing surfaces.

## Testing Strategy

| Test type | Purpose | Phase 1 evidence |
|---|---|---|
| Contract tests | Validate schemas, samples, generated models, and compatibility assumptions. | `contracts/` checks and CI drift gate. |
| Workflow replay tests | Prove Temporal determinism across code changes. | Recorded histories replay. |
| Unit tests | Validate pure domain/runtime logic where isolated tests are meaningful. | Agent/runtime policy, contract parsing, gateway decision logic. |
| Integration tests | Exercise real Postgres, Redpanda, Temporal, Mailpit, and service boundaries. | No mocks for infrastructure behaviour. |
| E2E tests | Exercise Lighthouse flow through UI/BFF/runtime surfaces. | Playwright happy path and failure views. |
| Tenant tests | Prove tenant isolation fails closed. | RLS and policy tests with two seeded tenants. |
| Trace/eval tests | Assert business path, governance invariants, cost, latency, and audit completeness. | Happy-path and Phase 1B failure fixtures. |

The no-mocks rule applies to infrastructure and connector behaviour that the
architecture is trying to prove. Lightweight pure-function tests remain useful
where no external boundary is being modelled.

## Local Operations

Local operation is part of the evidence surface.

| Command/surface | Purpose |
|---|---|
| `just up` | Start the local runtime substrate. |
| `just doctor` | Phase 0 scaffold checks. Phase 1A extends this to service health, migrations, schema registration, seeded tenants, and sample workflow readiness. |
| `just demo` | Send the fixture lead through Mailpit SMTP and observe workflow execution. |
| Temporal Console | Inspect workflow execution. |
| Redpanda Console | Inspect events and schemas. |
| Mailpit UI/API | Inspect inbound and outbound email. |
| Grafana | Inspect traces, metrics, logs, errors, latency, and cost signals. |
| UI | Inspect workflow progress, audit, runtime policy, grants, routing, and eval status. |

The local stack is Compose-based. Production deployment is out of Phase 1 scope.

## Deliberate Deferrals

Out of scope for Phase 1:

- second business workflow;
- generic agent framework;
- runtime-editable workflow DSL;
- production auth, SSO, RBAC, and identity integration;
- production cloud deployment;
- backup/disaster-recovery automation;
- Scylla implementation;
- full mutating admin UI;
- production writes to closed third-party platforms;
- complete provider-management platform;
- polished screencast before the working slice is stable.

These deferrals are design constraints, not omissions. Phase 1 is meant to prove
the core governance and runtime boundaries clearly enough that later production
hardening has an architectural base.
