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

Chorus is a programme-level architecture for governed multi-agent workflows. It
addresses runtime architecture, provider and model governance, tool authority,
auditability, evaluation, observability, and operational governance controls for
agent-enabled business processes. The Phase 1A review evidence is intentionally
self-contained in this repository so a reviewer can trace each claim to local
code, contracts, tests, operational surfaces, or ADRs.

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
| Phase 1C - Review packaging | Final README, screenshots or notes, demo script, evidence map, architecture links, and governance evidence. | An asynchronous reviewer can inspect the evidence path without hidden context. |
| Phase 2 - Governed platform expansion | Planned LangGraph agent execution, provider/model governance, governed identity/runtime change control, observability and journey evidence boundaries, connector expansion, second workflow proof, and production-readiness architecture pack. | Provider-governance groundwork has begun with `contracts/governance/`, LangGraph now runs inside Agent Runtime with graph execution evidence in decision-trail metadata, the commercial provider placeholder has an explicit disabled-by-default adapter boundary, provider failure, timeout, rate-limit, and budget-exceeded fixtures prove fallback to the local route without production provider calls, route-selection audit metadata is captured for reviewer inspection, read-only BFF/UI views expose provider catalogue, route-version, and graph-execution evidence, docs/runbook/evidence surfaces are aligned, ADR 0013 defines the Phase 2B identity, authority, observability, journey-evidence, and audit boundary, and ADR 0014 selects a local CalDAV calendar connector as the Phase 2C connector-expansion scope. Phase 2C now has calendar argument schemas, a local Radicale sandbox, Tool Gateway-dispatched availability/hold-proposal paths, approval-required calendar write packages, approved local apply evidence for idempotent create/retry/compensation, and read-only BFF calendar status/audit projection. ADR 0015 selects local Support Desk Triage as the Phase 2D second workflow proof scope; 2D-01 adds the support intake, support agent IO, ticket argument, workflow-event, and eval enum baseline, 2D-02 adds a Postgres-backed local ticket desk sandbox plus Tool Gateway read/propose dispatch for ticket lookup, duplicate lookup, and case-update proposals while ticket status writes remain approval-required, 2D-03 adds the code-defined `support_triage` Temporal workflow runtime plus replay baseline, and 2D-04 adds support eval plus persisted evidence proving safe trace joins across workflow events, Agent Runtime decisions, ticket Tool Gateway verdicts, and proposed case-update refs. Read-only support inspection remains planned. See [`phase-2-plan.md`](phase-2-plan.md), [ADR 0011](../adrs/0011-phase-2-governed-platform-expansion.md), [ADR 0012](../adrs/0012-langgraph-agent-execution-runtime.md), [ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md), [ADR 0014](../adrs/0014-connector-expansion-approval-hardening-scope.md), and [ADR 0015](../adrs/0015-second-workflow-proof-scope.md). |

## Phase 2 Planning Boundary

Phase 2 opens selected Phase 1 deferrals without changing the core posture:
evidence before breadth, Temporal-owned workflow state, runtime policy outside
prompts, Tool Gateway authority, contract-first payloads, and eval as a release
control.

Phase 2A implemented agent execution and provider governance evidence.
Provider catalogue contracts, route-version metadata, a provider-keyed model
adapter registry, LangGraph execution, disabled-provider evidence, fallback
handling, and provider degradation fixtures have landed. ADR 0013 opens Phase
2B by defining identity, authority, observability, journey-evidence, and audit
boundaries before mutating runtime controls are added.
ADR 0014 opens Phase 2C by selecting a local Radicale/CalDAV calendar connector
candidate. The scope is a Lighthouse follow-up calendar hold behind the Tool
Gateway with explicit approval, idempotency, retry, compensation, projection,
audit, eval, runbook, and evidence-map expectations. Calendar argument schemas
now cover availability lookup, hold proposal, hold creation, and hold
cancellation using safe refs and bounded categories only. The 2C-02 runtime
slice adds a local Radicale sandbox and Tool Gateway-dispatched connector paths
for availability lookup and hold proposal. Calendar create/cancel grants remain
`approval_required`; writes stop before connector execution and 2C-03 records a
minimal local `approval_packages` row with safe refs, bounded state/category
fields, idempotency key hash, grant/policy refs, redaction summary, expiry/SLA
refs, and trace joins. This does not add reviewer decisions, approval apply,
production calendar providers, OAuth, credential entry, production connector
writes, a hosted observability dependency, a Lighthouse workflow calendar
branch, an eval fixture, or a mutating admin UI. The 2C-04 runtime slice adds a
local approved calendar apply path inside the Tool Gateway: an already approved
package re-enters the gateway, package state/expiry/grant/idempotency/safe
calendar refs are checked, and the Radicale connector is invoked only from that
gateway path. This proves idempotent local VEVENT creation, transient retry
classification, cancellation compensation, and compensation-failure escalation
without adding a reviewer decision service, workflow branch, UI mutation, or
production integration.
The 2C-05 closeout adds a read-only BFF calendar status projection derived from
`approval_packages` and `tool_action_audit`. It exposes safe approval/audit
refs, calendar refs, bounded status and retry/compensation/failure categories,
grant/policy refs, and trace joins only; it does not expose raw event bodies,
raw tool arguments, connector payloads, reviewer decisions, or PII.

ADR 0015 scopes Phase 2D to a local Support Desk Triage workflow using future
workflow type `support_triage`. The selected workflow is adjacent to
Lighthouse but distinct: support request intake, classification/severity
triage, account or case context lookup, resolution planning, response and
case-update proposal, validation, completion, and escalation. Future
implementation must use only safe refs and bounded categories in examples,
keep support-ticket actions behind the Tool Gateway, start any local ticket
write as approval-required, add support-specific replay and eval evidence when
workflow behaviour changes, and expose read-only projection/audit/observability
surfaces. 2D-01 adds only contracts, generated models, safe samples, and enum
baselines: support request intake, support agent IO, ticket case lookup,
duplicate lookup, case-update proposal, future approval-required status
update, optional `support_triage` workflow-event values, and Phase 2D eval
contract values. 2D-02 adds only the local ticket desk sandbox and gateway
dispatch baseline: Postgres safe-ref ticket cases and case-update proposal
rows, support agent/grant seeds, Tool Gateway validation/dispatch for ticket
lookup, duplicate lookup, and proposed case update, and an approval-required
`ticket.update_status` grant that stops before connector execution. 2D-03 adds
`chorus.workflows.support.SupportTriageWorkflow`, registers it on the existing
Temporal worker, records safe support workflow events, and reuses the existing
Agent Runtime and Tool Gateway activities for classification, context lookup,
resolution planning, validation, ticket case lookup, duplicate lookup, and
proposed case-update dispatch. Agent Runtime now validates the support agent
IO contract through the local structured boundary. 2D-04 adds the support
happy-path eval fixture and persisted evidence baseline: support decisions can
persist in `decision_trail_entries`, and tests/eval prove workflow events,
support decisions, ticket verdicts, and proposed case-update refs join by safe
tenant/correlation/workflow refs. The runtime path does not call
`ticket.update_status` and does not add Support BFF/UI routes, production
connectors, credential entry, hosted observability dependencies, production
connector writes, ticket status execution, or a workflow DSL. Lighthouse
remains the Phase 1 demo and regression baseline.

Phase 2 does not make Chorus a top-level agent framework or SaaS product by
default. LangGraph is scoped to per-invocation agent execution; Temporal still
owns durable workflow state and the Tool Gateway still owns action authority.
Each reopened deferral needs an explicit milestone in
[`phase-2-plan.md`](phase-2-plan.md), matching docs, and evidence gates before
it is treated as delivered.

## Domain Language

Chorus's core domain is governed agent workflow execution. The important nouns
are runtime and governance concepts, not a top-level agent framework vocabulary.

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
  -> retry exhaustion -> DLQ evidence -> escalate
  -> forbidden write -> block or proposal downgrade
```

The demo trigger is real SMTP intake via Mailpit. A fixture email is sent to
`leads@chorus.local` through Mailpit's SMTP port. The implemented Mailpit poll
activity reads Mailpit's HTTP API, deduplicates by Message-ID using a stable
Message-ID-derived Temporal workflow ID, parses the email into the lead-intake
contract, and starts a Lighthouse workflow run.

Phase 1 deliberately keeps ingress narrow: the poller validates the
`lead_intake` contract and mints the `correlation_id` before calling Temporal,
but it does not persist a Chorus-owned ingress outbox event before workflow
start. Retry before Temporal starts relies on Mailpit retaining the message and
the idempotent Message-ID-derived workflow ID. A production or multi-source
ingress layer would record the intake event durably, publish it through
Redpanda, and start Temporal from an idempotent workflow-starter consumer.

UI fixture replay can exist as a development convenience, but the public demo
path leads with SMTP intake because it demonstrates an integration boundary
rather than a hand-fed form.

## Technology Stack

| Concern | Technology | Rationale |
|---|---|---|
| Durable orchestration | Temporal with Python SDK | Long-running workflow state, replay, retries, timers, signals, waits, and branch visibility. |
| Agent runtime | Python, FastAPI boundary, LangGraph inside Agent Runtime | Governed invocation identity, typed agent contracts, policy resolution, graph-backed agent execution, structured model output, and inspectable invocation capture. |
| Tool mediation | Python/FastAPI service boundary | Central enforcement for grants, argument schemas, modes, approval, redaction, idempotency, and audit. |
| Messaging | Redpanda Community Edition | Kafka-compatible event stream, visible console, and Schema Registry for event subjects. |
| Storage | Postgres | Phase 1 registry, grants, routing policy, outbox, projections, decision trail, episodic history, and tenant isolation. |
| Frontend | React, Vite, TypeScript, TanStack, Tailwind | Dense data-first UI and read-only admin surfaces. |
| BFF | FastAPI plus server-sent events | Read model API and one-way workflow progress stream. |
| Contracts | JSON Schema and generated Pydantic models | Language-neutral contract source with generated runtime types and drift checks. |
| Connectors | Mailpit, Companies House API, Postgres-backed local CRM, Radicale-backed local CalDAV sandbox, Postgres-backed local ticket desk sandbox | Real software in sandbox/local mode with no production writes to closed third-party systems. |
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
│   ├── implementation-plan.md
│   ├── phase-2-plan.md
│   ├── demo-script.md
│   ├── components/
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
├── frontend/
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

Workflow changes require replay coverage. Workstream B commits a replay fixture
for the Phase 1A happy path and tests it with Temporal's replayer. The workflow
should remain readable in Temporal Console: states and branches are part of the
review surface, not an implementation detail hidden in agent loops.

The Workstream B Lighthouse state machine is:

```text
intake
  -> research_qualification
  -> draft
  -> validation
  -> propose_send
  -> complete

escalation branch:
  -> escalate
```

Every state transition emits a generated-contract `WorkflowEvent` through the
`lighthouse.record_workflow_event` activity, which calls
`ProjectionStore.record_workflow_event()` and writes only to the transactional
outbox. Read models remain Redpanda/projection-worker derived.

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

ADR 0012 promotes LangGraph to the first-class agent execution engine inside
this boundary. LangGraph is not the durable business workflow owner. The
implemented graph runs inside the existing `lighthouse.invoke_agent_runtime`
Temporal activity, uses `graph.invoke()` without LangGraph checkpoint
persistence, and returns the same `AgentInvocationResponse` contract.

The intended ownership split is:

- Agent Runtime resolves tenant, agent, prompt, route, budget, invocation ID,
  output contract, and decision-trail capture.
- LangGraph owns the per-invocation execution graph: context preparation,
  model-adapter invocation, result normalisation, contract validation, and
  final response shaping.
- Model adapters remain the provider/model call boundary selected by runtime
  policy.
- Tool Gateway remains the only path to external action.

Phase 1 runtime mutation is CLI/config driven. The UI shows runtime state
read-only.

Workstream B defines the Temporal activity boundary as
`lighthouse.invoke_agent_runtime`. It accepts a contract-shaped
`AgentInvocationRequest` and returns an `AgentInvocationResponse` aligned with
`contracts/agents/lighthouse_agent_io.schema.json`. Workstream C implemented
the first internals behind that activity name: it resolves tenant, agent,
prompt, and model-route policy from Postgres, selects a provider-specific model
adapter from the Agent Runtime registry, validates the agent output contract,
and persists a generated-contract `AgentInvocationRecord` into
`decision_trail_entries`. Phase 2A item `2A-04` now executes that adapter call
through the LangGraph path `prepare_context -> invoke_model_adapter ->
normalise_result -> validate_contract -> final_response`. The workflow
interface did not change.

Phase 2A item `2A-05` adds graph execution evidence to the Postgres
`decision_trail_entries.metadata` column: execution engine, graph version,
graph path, and a graph path summary. This metadata is stored next to the OTel
trace/span join IDs. The generated `AgentInvocationRecord` remains the
canonical decision-trail contract; LangGraph does not become an audit store or
durable state owner.

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

The Phase 1A happy path routes to the local `lighthouse-happy-path-v1`
structured model boundary so the architecture evidence can run without
production provider credentials. The commercial provider placeholder now has a
disabled-by-default adapter boundary behind the same registry, but production
provider calls remain out of scope until provider credentials and eval
promotion policy are introduced.

Phase 2A adds Postgres-backed provider catalogue and immutable route-version
tables as governance evidence. They mirror the existing Phase 1 local routes
and disabled commercial-provider placeholder. The Agent Runtime still selects
the runnable route from `model_routing_policies`, but it joins the matching
approved `model_route_versions` row when available so decision-trail metadata
can show route ID, route version, provider catalogue, and selection source
without making immutable route versions the mutating policy interface.

The Phase 2A runtime adapter registry registers the local Lighthouse adapter
and a `commercial.example` placeholder adapter. The commercial adapter is a
disabled-by-default boundary: it performs no production provider calls, requires
no credentials for local runs, and records provider-disabled evidence in
`decision_trail_entries.metadata` when routing policy selects it. If routing
policy selects any other unregistered provider, the runtime records a failed
decision-trail entry and raises an Agent Runtime error. ADR 0012 places
LangGraph inside that same policy boundary: the compiled graph invokes the
selected adapter from the `invoke_model_adapter` node, while the local
Lighthouse adapter remains the only runnable model path.

Provider fallback is policy-gated. When a selected adapter raises a provider
invocation failure and `fallback_policy.on_provider_error` is `fallback_route`,
the runtime records the failed primary provider decision, then invokes the
configured fallback route through the same LangGraph graph with a new
invocation ID. The shipped fixture uses a failing `commercial.example` boundary
and a local `lighthouse-happy-path-v1` fallback so provider failure is visible
in the decision trail instead of being swallowed.

Provider degradation evidence now covers timeout, rate-limit, and
budget-exceeded paths using local fixture adapters and the disabled-provider
boundary shape. Timeout and rate-limit fixtures record provider-failure
metadata with reason values `timeout` and `rate_limited`. Budget degradation is
enforced inside Agent Runtime after adapter execution by comparing observed
cost against the resolved route `budget_cap_usd`; an exceeded cap records
provider-budget metadata and can use the same policy-gated fallback path. These
fixtures do not add credential entry, production commercial provider calls,
mutating provider admin, LangGraph checkpoint persistence, or LangGraph durable
execution.

Route-selection evidence is captured in `decision_trail_entries.metadata` next
to the graph execution metadata and OTel IDs. Each invocation records the
selected provider/model, task kind, budget, route ID/version where available,
provider catalogue, selection source, fallback reason, observed cost, and
observed latency. The generated `AgentInvocationRecord` still carries the
canonical provider/model, cost, and duration fields; metadata adds reviewer
lineage for Phase 2A route selection without changing the Temporal activity
request/response contracts.

Phase 2A read-only BFF/UI views expose that evidence without adding a mutating
admin surface: provider catalogue rows, provider model declarations, immutable
route versions, graph execution paths, route versions, fallback state, and
per-workflow graph execution records are projected from Postgres.

This is an inspection surface, not a provider-management product. The shipped
commercial provider is `commercial.example`, a disabled placeholder used for
failure and fallback evidence. There is no credential-entry UI, production
commercial provider call path, route-promotion workflow, LangGraph checkpoint
persistence, or LangGraph durable execution in Phase 2A.

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

Workstream B defines the Temporal activity boundary as
`lighthouse.invoke_tool_gateway`. It accepts a contract-shaped
`ToolGatewayRequest`, validates generated `ToolCall`/`GatewayVerdict` payloads,
and returns a `ToolGatewayResponse`. Workstream D implements the internals
behind that stable activity name: generated tool-contract validation,
per-tool argument validation, grant lookup, mode enforcement, redaction,
idempotency, approval-required decisions, audit persistence, connector
invocation, and real Mailpit outbound capture. The workflow interface did not
change, and agents still have no connector authority.

## Connector Substrate

Phase 1 connectors use real software in sandbox/local mode:

| Connector area | Phase 1 implementation |
|---|---|
| SMTP intake | Mailpit receives fixture lead email and exposes messages via HTTP API. |
| Email proposal/send | Mailpit captures all outbound SMTP. |
| CRM | Postgres-backed local service implementing lookup/create/update contract paths. |
| Company research | Public company-information APIs where suitable, starting with Companies House for UK company examples. |
| Calendar holds | Radicale-backed local CalDAV sandbox for safe availability lookup and hold proposal dispatch. |
| Ticket desk | Postgres-backed local ticket desk sandbox for safe support case lookup, duplicate lookup, and proposed case-update dispatch. |

The local connector service is contract-faithful and sits behind the Tool
Gateway. Phase 1 does not write to real CRMs, production mailboxes, payment
systems, or other closed third-party platforms.

The Phase 1A implementation currently routes `email.propose_response` and
`email.send_response` through the Mailpit SMTP connector, stores local CRM lead
state in Postgres through `crm.lookup_company` and `crm.create_lead`, and keeps
Companies House research behind an environment-gated connector. The gateway
records every decided call in `tool_action_audit` with generated
`AuditEvent`/`GatewayVerdict` payloads and active OTel metadata where present.

Phase 2C connector expansion is scoped by
[ADR 0014](../adrs/0014-connector-expansion-approval-hardening-scope.md) to a
local CalDAV calendar connector backed by Radicale or an equivalent local
sandbox. The scoped action family is calendar availability lookup, follow-up
hold proposal, local hold creation, and local hold cancellation. Runtime work
must prove gateway-only access, approval-required write handling, idempotent
VEVENT creation, retry classification, compensation through the gateway, safe
projections, redacted audit, eval fixtures, and runbook evidence before it is
treated as delivered.

The 2C-01 baseline adds generated Pydantic argument models for those four
calendar actions and extends the `ToolCall` tool-name enum. The 2C-02 runtime
slice adds `chorus.connectors.calendar.RadicaleCalendarConnector`, a local
Radicale sandbox in `compose.yml`, seeded calendar grants, and Tool Gateway
dispatch for the calendar tool family. Availability lookup and hold proposal
can execute against the local sandbox. Hold creation and cancellation grants
are seeded as `approval_required`; 2C-03 creates a requested approval package
with safe refs for those verdicts, and the connector is not invoked for writes
until an already approved local apply call re-enters the Tool Gateway. The
2C-04 apply path checks package state, expiry, grant, original idempotency key
hash, tenant/correlation/workflow/invocation refs, and safe calendar refs
before connector execution. The connector treats duplicate VEVENT UIDs as
idempotent only when the stored safe context matches, and cancellation
compensation uses `calendar.cancel_hold` through the gateway. The 2C-05 BFF
projection derives safe calendar status from local approval packages and
Tool Gateway apply audit rows for reviewer inspection without exposing raw
CalDAV bodies or tool arguments. Reviewer decisions, the Lighthouse workflow,
eval fixtures, UI mutation, production calendar providers, OAuth, credential
entry, and production connector writes remain unchanged and out of scope.

Phase 2D adds `chorus.connectors.ticket.LocalTicketDeskConnector` behind the
same Tool Gateway boundary. The connector reads safe local ticket case refs,
finds duplicate case refs, and persists proposed case-update refs in Postgres
without mutating case status. `ticket.lookup_case` and
`ticket.lookup_duplicates` use `read` grants, `ticket.propose_case_update` uses
a `propose` grant, and `ticket.update_status` is seeded as
`approval_required` so the gateway stops before connector execution. The ticket
sandbox is now consumed by the 2D-03 `support_triage` workflow only through
the existing Tool Gateway activity boundary. The 2D-04 eval and persistence
baseline proves proposal refs without status mutation. Support BFF/UI
inspection, production ticketing providers, credential entry, reviewer
decision UI, ticket status execution, and production connector writes remain
out of scope.

## Contracts and Schema Evolution

JSON Schema is canonical for cross-boundary contracts:

| Contract | Canonical source | Runtime use |
|---|---|---|
| Lead intake | `contracts/events/` | Mailpit parser and workflow input validation. |
| Workflow events | `contracts/events/` plus Redpanda Schema Registry | Event publication, projection, UI progress, eval assertions. |
| Agent inputs/outputs | `contracts/agents/` -> generated Pydantic | Runtime validation and decision-trail capture. |
| Tool calls/verdicts | `contracts/tools/` -> generated Pydantic | Gateway validation and audit. |
| Calendar connector arguments | `contracts/tools/calendar_*_args.schema.json` -> generated Pydantic | Phase 2C local CalDAV connector arguments validated by Tool Gateway dispatch for the local Radicale sandbox. |
| Ticket connector arguments | `contracts/tools/ticket_*_args.schema.json` -> generated Pydantic | Phase 2D local ticket desk arguments validated by Tool Gateway dispatch for the local Postgres sandbox. |
| Audit records | `contracts/events/` and Postgres schema | Review, eval, and traceability. |
| Eval fixtures | `contracts/eval/` | Regression checks for path, outcome, governance, cost, and latency. |
| Provider catalogue and route versions | `contracts/governance/` -> generated Pydantic; `provider_catalogues`, `provider_catalogue_providers`, `provider_catalogue_models`, `model_route_versions` | Phase 2 provider/model governance, route-version evidence, fallback policy, and promotion metadata. |

Generated Pydantic models are committed under `chorus/contracts/generated/`.
`just contracts-gen` regenerates them and `just contracts-check` validates
schemas, samples, and generated-model drift.

Contract rules:

- Additive changes are allowed within a compatible minor version when samples
  and generated models pass.
- Breaking changes use versioned subjects/topics and migration notes.
- CI fails when schemas, samples, generated models, or compatibility
  assumptions drift.
- Runtime/framework dynamic schema support is allowed only when static
  generation is awkward and the exception is documented.

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

The Phase 1A Workstream A storage and projection foundation is implemented as
SQL migrations under `infrastructure/postgres/migrations`, with idempotent
demo seeds under `infrastructure/postgres/seeds`. The first migration creates
tenant-scoped tables for tenants, agent registry, model routing policy, tool
grants, workflow read models, decision trail, tool/action audit, episodic
workflow history, and transactional outbox. The `chorus.persistence` Python
package exposes the migration runner, read-model adapter, outbox lifecycle
store, and Redpanda relay/projection adapters for later activity and BFF
workstreams.

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

For `workflow_event` rows, Phase 1A implements the local evidence path:

- activities append canonical event payloads with
  `ProjectionStore.record_workflow_event()`;
- `OutboxStore.claim_pending()` safely leases due rows with
  `FOR UPDATE SKIP LOCKED`, changes status to `publishing`, and increments
  `attempts`;
- the Redpanda relay publishes the generated-contract payload to
  `chorus.workflow.events.v1` and marks rows `sent`;
- publish failures mark rows `failed`, retain `last_error`, and schedule
  retry through `next_attempt_at`;
- activity retry exhaustion can mark retained evidence rows terminal `dlq`,
  outside the relay retry claim path;
- abandoned `publishing` leases are returned to the retry path;
- the projection worker consumes Redpanda events and applies
  `ProjectionStore.apply_workflow_event()` idempotently into
  `workflow_history_events` and `workflow_read_models`.

Read-model idempotency is explicit: `workflow_history_events` is unique by
source event ID and by workflow sequence, and `workflow_read_models` advances
only when the incoming event sequence is newer than the stored sequence.

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
- provider catalogue, provider models, and route versions;
- graph execution evidence, both globally and per workflow;
- eval status;
- links to Temporal, Redpanda, Grafana, and Mailpit surfaces by correlation ID.

The BFF reads Postgres projections and exposes server-sent events for one-way
progress updates. Refresh and reconnect must be reliable because the source of
truth is the projection, not an ephemeral browser stream.

## Observability, Journey Evidence, and Audit

Chorus separates auditability, operational telemetry, and application journey
evidence. They share correlation identifiers, but they answer different
questions and have different retention, sensitivity, and authority semantics.

| Surface | Purpose |
|---|---|
| Postgres decision trail | Accountability record for agent invocations, prompt/model identity, output, cost, duration, and correlation. |
| Postgres tool audit | Authority record for tool requests, gateway verdicts, approval hooks, and connector outcomes. |
| Temporal Console | Workflow state, retries, waits, branches, and replay evidence. |
| Redpanda Console | Event flow, schemas, DLQ topics, and projection feed visibility. |
| Grafana/OpenTelemetry | Traces, logs, metrics, latency, errors, and cost signals. |
| UI audit views | Reviewer-friendly projection of workflow, agent, tool, provider, route-version, and graph-execution evidence. |
| Eval output | Behavioural acceptance and governance invariant results. |

The boundary model is:

| Plane | Owns | Does not own |
|---|---|---|
| Infrastructure telemetry | OpenTelemetry traces, metrics, logs, resource/service health, dependency latency, retries, saturation, and error rates. | Business authority, approval decisions, or canonical audit state. |
| Application and user journey evidence | Workflow progress, BFF/UI route context, reviewer/session context, fixture replay path, and business correlation across `correlation_id`, `workflow_id`, `invocation_id`, and future `actor_session_id`. | Secrets, credentials, raw sensitive payloads, or enforcement decisions. |
| Audit/accountability | Decision trail, tool action audit, approval audit, policy mutation audit, and immutable evidence for who or what was authorised under which policy. | Operational metrics dashboards or hosted tracing as the source of truth. |
| Optional LLM observability sidecars | Derived trace/eval exports for prompt debugging, graph inspection, annotation, and experiment comparison. | Local release gates, policy enforcement, or accountability records. |

Every material operation must carry a Chorus `correlation_id`; telemetry also
carries OpenTelemetry `trace_id` and `span_id`. Workflow, agent, tool, approval,
and policy mutation records use stable domain IDs in addition to trace IDs so
that audit remains queryable even if traces are sampled, expired, or exported
to a different backend.

Context propagation must be conservative. Internal trace context may cross
trusted service boundaries. Baggage or equivalent propagated context must not
contain credentials, API keys, access tokens, raw customer content, or PII.
When data leaves the trusted local boundary, trace headers and baggage should
be filtered according to the connector's trust policy.

The Phase 2B field-placement model is defined in
[`observability-user-journey-model.md`](observability-user-journey-model.md).
In short: OpenTelemetry attributes carry operational and correlation fields;
propagated baggage is limited to a small allow-list of join keys; Postgres
projections and BFF/UI read models carry refresh-safe journey evidence; and
decision trail, tool audit, future approval audit, and future policy mutation
audit remain the accountability records. Future actor/session identifiers such
as `actor_session_id`, `workload_principal_id`, `approval_id`,
`policy_change_id`, and `authority_context_id` are planned identifiers, not
Phase 1 runtime dependencies.

LangSmith, Langfuse, or similar LLM observability tools remain optional
sidecars. The Phase 2B-06 evaluation in
[`llm-observability-sidecar-evaluation.md`](llm-observability-sidecar-evaluation.md)
decides that no exporter belongs in the default local stack. A future sidecar
may consume filtered OpenTelemetry traces, graph execution metadata, or eval
summaries through an opt-in collector or deterministic export, but it must not
receive raw prompts, outputs, tool arguments, approval or policy rationale,
credentials, identity-provider claims, or PII. It also does not replace the
local Grafana/OpenTelemetry evidence stack, Postgres decision trail, Tool
Gateway audit, Temporal replay tests, or `just eval` release gate.

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
and failure fixtures: low-confidence research, validator redraft, forbidden
write, connector failure compensation, and retry-exhaustion DLQ escalation.
Phase 2A adds provider fallback/degradation fixtures. Phase 2D adds the
support happy-path eval fixture for `support_triage`.

The harness is implemented by `just eval`. It runs the contract-shaped
Lighthouse happy-path fixture, the Phase 1B governance/failure fixtures, the
Phase 2A provider fallback/degradation fixtures, and the Phase 2D support
happy-path fixture under `chorus/eval/fixtures/`, then asserts the expected
workflow path, proposal/completion/escalation outcome, required workflow
events, Agent Runtime decision-trail completeness, Tool Gateway verdict/audit
evidence, budget, latency, DLQ/compensation/support proposal evidence where
applicable, and correlation ID propagation. When a reviewer passes
`CHORUS_EVAL_CORRELATION_ID` or
`CHORUS_EVAL_WORKFLOW_ID` on the default `just eval` path, the harness also
inspects persisted Postgres evidence for the live happy-path workflow from
`workflow_read_models`, `workflow_history_events`, `outbox_events`,
`decision_trail_entries`, and `tool_action_audit`. Live governance/failure
checks can be targeted with `uv run python -m chorus.eval.run --fixture ...`.
The support fixture can also target a persisted support workflow by workflow
ID or correlation ID; it joins support outbox events, decision-trail rows,
ticket Tool Gateway audit rows, and local proposed case-update refs without
requiring a Support BFF/UI path.
Redpanda, Temporal, Mailpit, and Grafana remain live review surfaces for the
3-minute path; the deterministic eval portion keeps CI and offline review from
depending on an already-running local stack.

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

The UI can inspect runtime governance state, provider-governance state, and
graph-execution evidence. Mutation remains CLI/config driven.

## Identity, Authority, and Future AWS Mapping

Phase 1 implements logical identity and tenant scoping, not production IAM.
Phase 2B will make the identity model explicit before adding mutating runtime
change control. The model should distinguish:

| Principal | Meaning | Current evidence | Future production mapping |
|---|---|---|---|
| Human principal | A person using the BFF/UI, approving risky actions, or proposing policy changes. | Deferred; the local BFF is tenant-fixed and read-only. | OIDC/SAML identity provider, AWS IAM Identity Center, RBAC groups, approval roles. |
| Workload principal | A running service or worker such as BFF, Temporal worker, Agent Runtime, Tool Gateway, projection worker, or connector. | Compose service name plus local environment; OTel service attributes. | ECS task role, EKS pod identity, Lambda execution role, EC2 instance profile, IAM Roles Anywhere, or SPIFFE/SPIRE workload identity. |
| Agent principal | Governed logical agent version selected for a tenant and task. | `agent_registry` rows: `tenant_id`, `agent_id`, role, version, lifecycle, owner, prompt reference/hash, capability tags. | Still a Chorus logical principal; it may be represented as IAM session tags or policy attributes, not as a long-lived IAM user. |
| Invocation principal | One authorised agent invocation within a workflow context. | `invocation_id`, `workflow_id`, `correlation_id`, route, budget, prompt hash, decision-trail entry. | Short-lived authority token or STS session context with tenant, workflow, agent, task, and budget tags. |
| Approval actor | Human or system actor deciding an approval-required action. | `approval_required` gateway verdict only. | Signed approval package with reviewer subject, tenant, role, expiry, decision, and audit record. |
| Policy actor | Human or automation proposing/applying runtime policy changes. | Direct seeded/config mutation in local evidence. | Change-control workflow with proposer, approver, rollback, reason, eval evidence, and audit. |

The Phase 2B-02 workload-principal model is a docs-first schema sketch in
[`workload-principal-model.md`](workload-principal-model.md). It represents
stable workload principals, short-lived workload sessions, tenant scope, local
trust domains, and nullable future AWS mapping metadata without adding AWS,
production SSO, cloud deployment, credentials, migrations, or contracts.

| Workload field family | Local representation | Future AWS or hybrid mapping | Telemetry boundary |
|---|---|---|---|
| Service identity | `workload_principal_id`, `service.name`, `service.namespace`, workload kind, and status. | ECS task role, EKS pod identity, Lambda execution role, EC2 instance profile, IAM Roles Anywhere, or SPIFFE/SPIRE identity. | `service.name`, `service.namespace`, and `chorus.workload.principal_id` may be OTel resource attributes. |
| Trust domain | `local.chorus` for Compose, `fixture.chorus` for local eval/replay automation. | AWS account or cluster trust domain, external OIDC/SAML provider, SPIFFE/SPIRE trust domain, or IAM Roles Anywhere trust anchor reference. | `chorus.workload.trust_domain` may be an OTel resource attribute. |
| Workload session | Opaque `workload_session_id`, runtime kind, started/ended timestamps, and service version. | STS role session, pod/task execution instance, Lambda invocation environment, or signed local authority token context. | Keep out of baggage; span attributes only when bounded local diagnosis requires it. |
| Tenant scope | `none`, `all_tenants`, or `tenant_allow_list` with stable tenant IDs. | STS session tags or application policy attributes. | Use tenant IDs only where already allowed by the observability model. |
| IAM role and STS metadata | Nullable future role ARN, session-name template, tag-key allow-list, and safe defaults. | IAM role ARN, STS session name, session tags, and external ID reference. | Do not emit role ARN, external ID refs, or tag payloads as telemetry attributes. |
| IAM Roles Anywhere and external IdP refs | Nullable profile ARN, trust-anchor ARN, certificate-subject ref, external IdP ref, or SPIFFE ID. | Hybrid workload identity, external OIDC/SAML, SPIFFE/SPIRE, or IAM Roles Anywhere. | Keep in identity/audit records only; never store certificate material or tokens. |

The Phase 2B-03 invocation-authority context is a docs-first schema sketch in
[`invocation-authority-context.md`](invocation-authority-context.md). It groups
the authority fields already carried across Agent Runtime requests, Tool
Gateway requests, decision trail, and tool audit into one future local context:
tenant, correlation, workflow, invocation, agent ID/version, task kind,
provider/model route ID/version, budget cap, requested tool and mode where
applicable, parent invocation, expiry, workload principal/session refs,
approval or policy-change refs when present, and safe trace-join metadata.

The authority context is not telemetry baggage, prompt text, a credential
container, or a replacement for gateway grants. Agent Runtime remains the
authority boundary for agent version, prompt, route, provider, graph, and
budget selection. Tool Gateway remains the authority boundary for grants,
argument schema validation, mode enforcement, approval hooks, idempotency,
redaction, connector invocation, and action audit. If this sketch becomes
executable later, it should start as a local deterministic object and become a
JSON Schema contract only when it crosses a service boundary or release gate.

The Phase 2B-04 human-approval model is a docs-first lifecycle sketch in
[`human-approval-audit-lifecycle.md`](human-approval-audit-lifecycle.md). It
turns the existing Tool Gateway `approval_required` verdict into the trigger
for a future approval package: approval ID, tenant, correlation, workflow,
invocation/tool authority refs, requested action, requested and enforced tool
mode, opaque reviewer subject ref, reviewer role, decision, expiry/SLA, bounded
reason category, policy version refs, workload/session refs, and safe trace
join metadata. Phase 2C-03 promotes the narrow calendar subset into local
Postgres persistence: approval-required calendar writes now create requested
approval packages with safe refs only. The current Lighthouse runtime still
stops at `approval_required`; no reviewer decision path, approval apply,
production SSO, identity-provider integration, credential entry, mutating admin
UI, production connector write, contract, seed, or Temporal wait state is added.

The Phase 2B-05 policy-change model is a docs-first governance workflow in
[`policy-change-governance-workflow.md`](policy-change-governance-workflow.md).
It defines the future propose, approve, apply, and rollback lifecycle for
prompt references, model routes, budget caps, and tool grants. The package
shape binds policy change ID, tenant, optional correlation/workflow refs,
target policy type, target object refs, before/after version refs, proposer
and reviewer actor subject refs, approval ID when required, bounded reason
category, eval evidence refs, apply/rollback refs, expiry/SLA, workload/session
refs, and safe trace joins. It remains docs-first: no policy-change table,
contract, seed, runtime apply service, production SSO, credential path,
production provider call, production connector write, or mutating admin UI is
added by this model.

The future AWS shape is a mapping target, not a Phase 2 local dependency. In an
AWS deployment, human identities would normally federate into roles or
permission sets, while workloads would receive temporary role credentials from
their compute environment. Non-AWS or hybrid workloads could use IAM Roles
Anywhere with X.509 certificates. Chorus should preserve enough metadata to map
local workload and invocation principals to role ARN, role session name,
session tags, trust domain, and external identity provider without embedding AWS
specifics into workflow logic or prompts.

Tool Gateway authorisation remains application-level policy even when workload
authentication is delegated to AWS IAM. IAM proves which workload called the
gateway and constrains cloud-resource access; Chorus grants decide whether a
specific tenant, agent version, invocation, tool, mode, and approval state allow
the business action.

## Security and Data Boundaries

Phase 1 is a single-user local reference implementation, not a production SaaS.
Security architecture is still explicit:

- no production customer data;
- no production auth/SSO in Phase 1;
- no AWS IAM integration in the local evidence path;
- no production calendar, CRM, email, or other closed-system connector writes
  in the local evidence path;
- secrets loaded from local environment files or injected environment
  variables, never committed;
- model/provider credentials held only at the model/router boundary;
- all tenant-owned data carries `tenant_id`;
- tool arguments are schema-validated and tenant-scoped before connector
  execution;
- audit redaction policy applies before sensitive data is persisted or emitted;
- closed third-party systems are not written to in Phase 1.

Production identity, RBAC, SSO, AWS IAM mapping, secrets management, incident
integration, and cloud network controls are deferred, with the identity and
observability shape now planned for Phase 2B.

## Error Handling and Resilience

| Failure | Phase 1 handling |
|---|---|
| Activity failure | Temporal retry policy plus Phase 1B compensation/escalation fixtures. |
| Connector failure | Gateway/connector error classification plus Phase 1B G-04 compensation/escalation fixture. |
| Retry exhaustion | Phase 1B G-05 records a terminal `dlq` outbox marker plus `workflow.retry_exhausted.dlq_recorded` audit evidence before escalation. |
| Provider failure | Runtime records the failed primary provider attempt and, when `fallback_policy` selects a fallback route, records a separate successful local fallback decision. The Phase 2A provider-fallback eval fixture covers this without enabling production provider calls. |
| Low-confidence research | Phase 1B deeper-research branch fixture. |
| Validator rejection | Phase 1B return-to-draft fixture with structured reason. |
| Forbidden write | Gateway block, approval-required, write-to-propose behaviour, and the Phase 1B forbidden-write workflow fixture. |
| Projection failure | Redpanda consumer retry path; projection-specific DLQ/escalation evidence is deferred until projection-worker failure drills are in scope. |
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
| Trace/eval tests | Assert business path, governance invariants, cost, latency, and audit completeness. | `just eval` runs the happy-path fixture plus Phase 1B governance/failure fixtures. |

The no-mocks rule applies to infrastructure and connector behaviour that the
architecture is trying to prove. Lightweight pure-function tests remain useful
where no external boundary is being modelled.

## Local Operations

Local operation is part of the evidence surface.

| Command/surface | Purpose |
|---|---|
| `just up` | Start the local runtime substrate. |
| `just db-migrate` | Apply Postgres migrations and idempotent demo tenant seed data. |
| `just worker` | Run the Lighthouse Temporal worker with workflow and activity registrations. |
| `just intake-once` | Poll Mailpit once and start one Lighthouse workflow per new lead Message-ID. |
| `just relay-once` / `just project-once` | Move workflow events through Redpanda and into refresh-safe Postgres projections. |
| `just doctor` | Phase 0 scaffold checks. Phase 1A extends this to service health, migrations, schema registration, seeded tenants, and sample workflow readiness. |
| `just test-persistence` | Run Postgres persistence, outbox, Redpanda relay/projection, RLS, and fail-closed tenant-isolation tests. |
| `just demo` | Send the fixture lead through Mailpit SMTP and observe workflow execution. |
| `just eval` | Run the happy-path and Phase 1B governance/failure fixtures; optionally inspect a live run when `CHORUS_EVAL_CORRELATION_ID` or `CHORUS_EVAL_WORKFLOW_ID` is set. |
| Temporal Console | Inspect workflow execution. |
| Redpanda Console | Inspect events and schemas. |
| Mailpit UI/API | Inspect inbound and outbound email. |
| Radicale / CalDAV sandbox | Inspect local calendar collection metadata and safe event UID refs. |
| Grafana | Inspect traces, metrics, logs, errors, latency, and cost signals. |
| UI | Inspect workflow progress, audit, runtime policy, grants, routing, and eval status. |

The local stack is Compose-based. Production deployment is out of Phase 1 scope.

## Deliberate Deferrals

Out of scope for Phase 1:

- second business workflow;
- top-level agent framework replacing Temporal;
- runtime-editable workflow DSL;
- production auth, SSO, RBAC, AWS IAM integration, and identity integration;
- production cloud deployment;
- backup/disaster-recovery automation;
- Scylla implementation;
- full mutating admin UI;
- production writes to closed third-party platforms;
- complete provider-management platform;
- production-grade screencast package.

These deferrals are design constraints, not omissions. Phase 1 is meant to prove
the core governance and runtime boundaries clearly enough that later production
hardening has an architectural base.
