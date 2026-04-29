---
type: project-doc
status: design-freeze
version: 0.3.0
date: 2026-04-28
---

# Chorus - Architecture

Chorus is a production-shaped reference implementation and architecture artefact set for governed multi-agent workflows. The architecture is evidence-first: each decision must make durable orchestration, explicit tool authority, auditability, failure handling, schema discipline, evaluation, governance, and SDLC adoption controls inspectable.

Companion artefacts complete the enterprise architecture package:

- `technical-architecture.md` maps the implementation architecture, components, contracts, data flow, tests, and operations surface.
- `governance-guardrails.md` defines the AI/LLM guardrail control matrix.
- `sdlc-operating-model.md` defines lifecycle stages, gates, roles, change control, provider collaboration, and team enablement.

## 1. Architectural goal

**Concern.** What is Chorus optimising for?

**Decision.** Optimise for a tight, inspectable evidence artefact rather than a broad generic platform.

**Reason.** Architecture evidence is judged on clear boundaries, operability, and failure handling. A narrow vertical slice with strong traceability is more useful than a wide platform skeleton with thin implementation.

**Consequences.** Phase 1 favours fewer agents, fewer connectors, Postgres-only storage, read-only admin surfaces, and a repeatable demo/eval loop. Production-scale alternatives are documented when relevant but not implemented prematurely.

**Enterprise artefact consequence.** Phase 1 documentation must be good enough for asynchronous architecture review, not only for running the local demo.

---

## 2. Demo workflow

**Concern.** What business workflow proves the architecture?

**Decision.** **Lighthouse**, an inbound-lead concierge for a fictional SMB.

**Flow.** Lead email received -> intake -> research/qualification -> draft -> validation -> propose/send or escalate.

**Failure branches.**

- Low-confidence research triggers deeper research.
- Validator rejection loops back to drafting.
- Connector failure triggers compensation or human escalation.
- Forbidden write action is blocked or downgraded to proposal mode.

**Consequences.** Lighthouse is the only Phase 1 business workflow. A second example is deferred.

---

## 3. Orchestration runtime

**Concern.** Who owns workflow lifecycle, retries, timeouts, durable state, replay, signals, fan-out/fan-in, and human-in-the-loop waits?

**Alternatives.** Temporal, Restate, DBOS, Inngest, Dapr Workflow, AWS Step Functions, hand-rolled.

**Decision.** **Temporal**, self-hosted, with the Python SDK.

**Reason.** Temporal is the most mature open-source durable execution engine for long-running, code-defined workflows. Activities map cleanly to agent invocations and external actions. Replay-from-history is built in. Human waits, timers, retries, and failure branches are first-class.

**Consequences.** Workflow code must remain deterministic: no random, wall-clock time, network IO, or database IO inside workflow logic. Fallible work lives in activities. Replay tests are mandatory.

---

## 4. Coordination model

**Concern.** How do agents coordinate?

**Decision.** Temporal workflows are the primary state machine. Sagas are modelled as explicit failure/compensation branches inside the workflow. Choreographed side effects use Redpanda events.

**Reason.** The critical path needs one durable source of truth. Side effects such as audit projection, UI updates, metrics, and lifecycle notifications should not complicate the workflow.

**Consequences.** Orchestration stays explainable in Temporal Console. Redpanda is used for event visibility, projections, and async consumers, not for in-workflow state.

---

## 5. Workflow definition format

**Concern.** Where do workflow definitions live?

**Alternatives.** Native Temporal code, YAML/DSL interpreted by a generic engine, BPMN.

**Decision.** Native Temporal workflows in Python.

**Reason.** Runtime-editable YAML would add an interpreter and reduce type/refactor safety. For this artefact, code-reviewed workflow changes are a stronger signal than a broad DSL.

**Consequences.** Workflow versioning is Temporal-native. A YAML layer can be revisited only if a future client requirement justifies it.

---

## 6. Messaging fabric

**Concern.** How do components communicate beyond Temporal?

**Alternatives.** Redpanda, Apache Kafka, NATS, Redis Streams, RabbitMQ, SQS/SNS.

**Decision.** **Redpanda** Community Edition.

**Reason.** Redpanda gives Kafka API compatibility, a visible console, built-in Schema Registry, and lower local/demo operational friction than Kafka. It is a good evidence surface because topic flow and schema-governed payloads are inspectable.

**Use cases.**

- Domain events.
- Agent invocation/audit feed.
- UI/read-model projection feed.
- Lifecycle and policy events.
- DLQ topics for exhausted retries.

**Important nuance.** Schema Registry governs schema versions and compatibility. Producers and consumers still need schema-aware validation/serialisation, and CI must reject drift.

---

## 7. Storage posture

**Concern.** Which persistent stores are needed in Phase 1?

**Decision.** Phase 1 is **Postgres-only**, plus Redpanda for in-flight events and Temporal's own persistence.

**Postgres stores.**

- Agent runtime registry.
- Tool grants and model-routing policy materialisation.
- Outbox rows.
- Workflow read model/projections.
- Decision trail.
- Episodic workflow history.
- Semantic memory via pgvector if required by the Lighthouse research path.

**Production note.** Scylla remains a documented Phase 2/production option for append-heavy, partition-then-range workloads such as long-retention decision trails and episodic histories. The Phase 1 design keeps storage adapters so this is not an architectural rewrite.

**Reason.** Postgres is enough for the evidence workload. Premature Scylla implementation would distract from the core proof.

---

## 8. Agent Runtime service

**Concern.** How is "agent X" represented at runtime?

**Decision.** A Python/FastAPI Agent Runtime sits between Temporal activities and the model/tool layers.

It owns:

- **Registry** - agent id, role, version, prompt reference, default model, capability tags, owner, lifecycle status.
- **Capability resolution** - bind role request plus tenant to a concrete agent config.
- **Model routing policy** - role/task/tenant tier to model id, parameters, budget caps.
- **Lifecycle state** - proposed, shadow, canary, live, retired.
- **Invocation capture** - create the decision-trail record and correlation identifiers.

**Reason.** Temporal dispatches work. The runtime decides which agent configuration is valid for a tenant at that time. These are separate concerns.

**Phase 1 scope.** Runtime mutations are CLI/config driven. The UI can show read-only runtime state.

---

## 9. Tool Gateway and action authority

**Concern.** How do agents gain permission to act?

**Decision.** Add an explicit Tool Gateway boundary. Agents never call external connectors directly.

The gateway enforces:

- `(agent_id, tenant_id, tool, mode)` grants, where mode is `read`, `propose`, or `write`.
- Argument schema validation.
- Tenant scoping and redaction.
- Dry-run/proposal handling.
- Human approval hook for risky writes.
- Idempotency key and action audit event.
- Allow/rewrite/block verdicts.

**MCP stance.** MCP is an integration protocol at the tool boundary, not an authority model by itself. Phase 1 can expose fake connector tools through Chorus-native contracts; MCP compatibility can be documented or added later behind the gateway.

**Reason.** The language-to-action boundary is the highest-risk part of an agentic system. Making it visible is core architecture evidence.

---

## 10. Agent implementation pattern

**Concern.** How is an individual agent's reasoning loop coded?

**Decision.** Use PydanticAI as the Phase 1 default for typed agent contracts and structured outputs. Use direct provider SDK calls only inside the model/router boundary where PydanticAI adds no value. Do not add LangGraph in Phase 1.

**Temporal nuance.** Long-running or IO-heavy agent operations expose model requests, tool calls, and connector communication as Temporal activities where practical. Avoid hiding too much irreversible work inside one opaque activity.

**Rejected for Phase 1.** Full CrewAI/AutoGen-style top-level orchestration and LangGraph subgraphs, because they duplicate or obscure the Temporal evidence path for this slice.

---

## 11. Memory architecture

**Concern.** What memory is needed to prove the architecture?

**Decision.** Keep the three-tier model, but implement only the pieces Lighthouse needs.

- **Episodic** - workflow-local history and agent observations, stored in Postgres append tables in Phase 1.
- **Semantic** - tenant/domain knowledge for retrieval, using Postgres + pgvector only if the research agent needs it.
- **Procedural** - workflow code, prompt templates, tool catalogue, agent declarations, and routing policy in Git.

**Reason.** Three tiers are a useful conceptual boundary, but Phase 1 should not build unused memory infrastructure.

---

## 12. Multi-model routing

**Concern.** Which model does each agent use?

**Decision.** Route via policy in the Agent Runtime: `(role, task_kind, tenant_tier) -> model_id + parameters + budget caps`.

**Default posture.**

- Cheap classification: small/fast model.
- Structured extraction and qualification: reliable mid-tier model.
- Complex reflection/research: stronger reasoning model.
- Validation: different model family from the producer where available.

**Reason.** Model selection, cost limits, and validation diversity should be inspectable policy decisions, not scattered SDK calls.

---

## 13. Validation gates

**Concern.** How does Chorus catch poor or unsafe output before action?

**Decision.** Validation is an explicit workflow state. The validator is an agent with a different route from the producer. Outcomes are `approve`, `reject_with_reason`, or `escalate_to_human`.

**Reason.** Boundary validation is more observable and replayable than hidden self-reflection inside a single prompt.

---

## 14. Evaluation and assurance

**Concern.** How do we prove behaviour has not regressed?

**Decision.** Add a trace/evaluation harness as a Phase 1 architectural pillar.

The harness should include:

- Lead fixture set with expected workflow path.
- Expected final outcome: send/propose/escalate/reject.
- Expected tool grant mode and blocked-action checks.
- Validator-family diversity checks.
- Cost and latency budget checks.
- Contract checks over emitted events and decision-trail rows.
- Fault-injection cases for connector failure and low-confidence research.

**Reason.** Observability shows what happened. Evaluation says whether that behaviour was acceptable. Hiring managers will recognise this as the line between demo and engineering discipline.

---

## 15. Outbox and dual-write safety

**Concern.** How do results and events stay consistent?

**Decision.** Use transactional outbox for service-owned database writes plus event publication.

Each service writes result/projection state and an outbox row in one Postgres transaction. A relay publishes to Redpanda and marks rows sent. Consumers are idempotent and dedupe by event id or `(agent_id, invocation_id)`.

**Nuance.** Outbox does not eliminate every crash window around LLM calls. It ensures that once a response is persisted, the event announcing it is not lost. Activities must use idempotency keys and persist decision records as early as practical.

**Implementation default.** Start with a simple Python relay. Revisit Redpanda Connect/Postgres CDC if the custom relay becomes more distracting than useful.

---

## 16. Multi-tenancy

**Concern.** How is tenant isolation represented?

**Decision.** Design for multi-tenancy from day one, exercise it lightly in Phase 1.

- Temporal namespace or tenant-scoped task/workflow naming.
- Redpanda topic prefix and tenant header.
- Postgres `tenant_id` on every table with row-level security.
- Tool grants and model policy keyed by tenant.

**Phase 1 default.** Seed two pretend SMB tenants, demo one tenant, and include RLS/tenant-isolation tests. Do not overbuild tenant-switching UI unless it helps the walkthrough.

---

## 17. Observability and audit

**Concern.** What did the system do, and is it healthy?

**Decision.** Separate audit evidence from operational telemetry.

- **Decision trail** - durable per-invocation evidence in Postgres for Phase 1.
- **Operational telemetry** - OpenTelemetry traces/logs/metrics to Grafana stack.
- **Consoles** - Temporal Console and Redpanda Console are part of the demo evidence.

**Reason.** Audit and telemetry answer different questions. The demo should deep-link by correlation ID across all views.

---

## 18. Frontend and BFF

**Concern.** What runs at `localhost:3000`?

**Decision.** Use the latest stable React, Vite, TypeScript, TanStack Router/Query/Table, Tailwind, Vitest, Playwright, and `openapi-typescript` available when the repo is created. Use Refine only if it materially accelerates read-only data/admin views without pulling the UI into a framework-shaped demo.

**BFF default.** A thin FastAPI BFF exposes read endpoints plus server-sent events (SSE) for progress updates. The BFF reads from a Postgres projection/read model so reconnect and refresh are reliable. The projection is fed from Redpanda/outbox events.

**Reason.** SSE is enough for one-way progress updates and simpler than WebSockets. The projection avoids coupling UI state to ephemeral stream position.

**UI style.** Dense, plain, data-first screens. No marketing landing page and no decorative card-heavy layout.

---

## 19. Containerisation and local run

**Concern.** How does the system run locally?

**Decision.** Docker Compose with mode-aware profiles and Traefik hostnames:

- `app.chorus.localhost`
- `api.chorus.localhost`
- `temporal.chorus.localhost`
- `redpanda.chorus.localhost`
- `grafana.chorus.localhost`

Containers use UID/GID mapping. Entrypoints run idempotent migrations. A `chorus doctor` command verifies environment, services, schema registration, and sample workflow readiness.

**Reason.** Reliable local run is part of the evidence. Hiring managers should not need fragile setup steps to inspect the system.

---

## 20. Data contracts and schema evolution

**Concern.** How are component contracts defined and evolved?

**Decision.**

- JSON Schema is canonical for events and agent contracts.
- Pydantic models are generated via `datamodel-code-generator` for static contracts.
- PydanticAI dynamic schema support can be used only where static generation is awkward.
- Redpanda Schema Registry holds event schema versions and compatibility settings.
- CI checks generated-code drift and sample payload validation.

**Evolution.** Additive changes within a minor version. Breaking changes use versioned subjects/topics and migration windows.

---

## 21. Secrets and config

**Concern.** Where do API keys and configuration live?

**Decision.**

- Local: gitignored `.env.local.sh` or `.env.local` loaded by Compose.
- Production surface: AWS Secrets Manager or equivalent, injected as environment variables.
- LLM provider credentials are held only by the model/router boundary.

**Reason.** Credential exposure should be centralised and easy to explain.

---

## 22. Resilience

**Concern.** How are external failures handled?

**Decision.**

- Temporal retries for activity failures.
- Connector/tool gateway circuit breakers.
- Per-provider and per-tenant rate limits.
- DLQ topics for exhausted async processing.
- Workflow-level branches for escalation and compensation.

**Phase 1.** Implement enough to demonstrate connector failure, blocked write, retry/exhaustion, and manual resolution.

---

## 23. CI/CD and testing

**Concern.** How does confidence scale?

**Decision.**

- Unit tests: pytest and Vitest.
- Integration tests: real Postgres, Redpanda, and Temporal in Compose.
- E2E: Playwright against Lighthouse happy path and failure paths.
- Workflow replay tests: recorded Temporal histories.
- Contract tests: JSON Schema samples and drift check.
- Trace/eval tests: fixture leads and governance invariants.

**Reason.** The no-mocks principle is strongest where contracts and infrastructure behaviour matter. Keep test scope focused enough that CI remains usable.

---

## Phase 1 defaults

These are fixed for Phase 1 unless implementation proves one impossible or actively harmful to the evidence goal.

1. **JSON Schema -> Pydantic.** Use `datamodel-code-generator` for committed static models. Use PydanticAI dynamic schema helpers only as an exception.
2. **Live updates.** Use Postgres projection plus SSE from the BFF. Source projection changes from Redpanda/outbox events.
3. **Tool-grant promotion.** CLI/config for Phase 1 mutation. Add Temporal human-approval workflow only for the demoed risky action path.
4. **Admin surface.** Read-only UI for registry, grants, routing, and audit. Mutating admin remains CLI/config in Phase 1.
5. **Tenancy.** Seed two tenants, demo one, test isolation.
6. **Connector fakes.** One fake connector service with contract-faithful modules for CRM lookup, company research, email proposal, and email send. Writes affect only local fake state.
7. **Agent implementation.** PydanticAI is the default agent contract layer. No LangGraph in Phase 1.
8. **Model routing.** Agent Runtime owns model/provider selection and budget caps. Agent code never selects providers directly.
9. **Evaluation gate.** Trace/eval fixtures are a Phase 1 exit criterion, not a post-demo polish task.

## Phase 1 ADRs

- ADR 0001 - Evidence-first scope and Lighthouse vertical slice.
- ADR 0002 - Temporal as durable orchestration spine.
- ADR 0003 - Redpanda for event visibility and async projections.
- ADR 0004 - Agent Runtime and Tool Gateway boundaries.
- ADR 0005 - Postgres-first storage with deferred Scylla option.
- ADR 0006 - JSON Schema canonical contracts and generated Pydantic models.
- ADR 0007 - Trace/evaluation harness as Phase 1 requirement.

## Out of scope for Phase 1

- Real third-party integrations.
- Production auth/SSO.
- Runtime workflow DSL.
- Scylla implementation.
- Full admin UI.
- Production AWS deployment.
- A second business example.
- Backup/disaster recovery automation.

## SDLC topic coverage matrix

| Topic | Section |
|---|---|
| Evidence goal | §1 |
| Demo workflow | §2 |
| Orchestration | §3 |
| Coordination | §4 |
| Workflow definition | §5 |
| Messaging | §6 |
| Storage | §7 |
| Agent runtime | §8 |
| Tool authority | §9 |
| Agent implementation | §10 |
| Memory | §11 |
| Model routing | §12 |
| Validation | §13 |
| Evaluation | §14 |
| Outbox | §15 |
| Multi-tenancy | §16 |
| Observability/audit | §17 |
| Frontend/BFF | §18 |
| Local run | §19 |
| Contracts | §20 |
| Secrets | §21 |
| Resilience | §22 |
| CI/testing | §23 |
