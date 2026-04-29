---
type: project-doc
status: design-freeze
date: 2026-04-29
---

# Chorus - Governance and Guardrails

## Purpose

This document describes the enterprise governance posture Chorus is designed to demonstrate. It is written for senior stakeholders evaluating whether agentic AI and LLM-enabled systems can be adopted safely inside controlled operational processes.

The goal is not to claim Chorus is a complete enterprise policy framework. The goal is to show the architectural guardrails, evidence surfaces, and operating controls that a serious programme would require.

## Governance Principles

1. **No ambient authority.** Agents can reason, but all external action authority is granted and enforced outside prompt text.
2. **Human accountability remains explicit.** Risky actions use proposal, approval, escalation, or compensation states rather than pretending the agent is the accountable actor.
3. **Contracts are governed assets.** Events, agent outputs, tool calls, eval fixtures, and audit records are versioned contracts.
4. **Traceability is mandatory.** Every material decision links workflow, agent, prompt, model, tool, output, cost, duration, and correlation ID.
5. **Evaluation is part of release control.** Behavioural fixtures and governance invariants gate change.
6. **Provider choice is policy, not implementation trivia.** Model/provider selection, budgets, fallback, and validator diversity are inspectable runtime policy.
7. **Deferrals are explicit.** Known production concerns are named and separated from Phase 1 evidence scope.

## Control Matrix

| Risk | Guardrail | Chorus evidence |
|---|---|---|
| Agent performs an unauthorised action | Tool Gateway grants by `(agent_id, tenant_id, tool, mode)` | Blocked/downgraded write fixture and audit verdict. |
| Prompt change alters behaviour silently | Prompt references and hashes captured per invocation | Decision trail shows prompt identity for each run. |
| Model/provider change causes regression | Runtime model policy plus eval fixtures | Eval gate checks path, outcome, cost, latency, and validator diversity. |
| Unsafe or low-quality output reaches customer | Explicit validation workflow state | Validator can approve, reject with reason, or escalate. |
| Data crosses tenant boundary | Tenant IDs, RLS, tenant-scoped policies | Phase 1A Postgres migration, two demo tenants, and real-Postgres fail-closed RLS tests. |
| Tool arguments are malformed or unsafe | JSON Schema validation at gateway | Invalid argument fixtures fail before connector execution. |
| Audit record is incomplete | Decision trail schema and required fields | Contract tests and eval assertions over persisted records. |
| External provider or connector fails | Temporal retries, circuit breakers, DLQ/escalation | Connector-failure fixture and retry/exhaustion evidence. |
| Cost grows without visibility | Runtime budget caps and per-invocation cost capture | Eval budget checks and Grafana cost view. |
| Teams bypass approved patterns | Architecture docs, ADRs, contract gates, quality gates | Repo structure makes approved boundaries explicit. |

## Guardrail Layers

### Architectural Guardrails

- Temporal is the durable orchestration spine.
- Agent Runtime owns agent identity, lifecycle, prompts, model routing, policy, and invocation records.
- Tool Gateway owns action authority.
- JSON Schema owns cross-boundary contracts.
- Postgres owns Phase 1 audit, policy materialisation, outbox, and projections.
- Redpanda owns event distribution and event-schema visibility, not critical workflow state.

### Change-Control Guardrails

- Architecture and ADRs are updated with material design changes.
- Contract changes require schema diffs, generated-code refresh, samples, and drift checks.
- Workflow changes require replay tests.
- Agent, prompt, model, and tool-policy changes require trace/eval fixtures or documented exception.
- Governance fixtures must include happy path, blocked write, validator rejection, connector failure, and low-confidence research.

### Runtime Guardrails

- Agents never call connectors directly.
- Runtime policy resolves model/provider and budget caps.
- Tool Gateway validates arguments and grants before connector execution.
- Risky writes run in propose or approval mode unless explicitly authorised.
- Every invocation and tool action emits audit evidence.

### Operational Guardrails

- Correlation ID links UI, Temporal, Redpanda, Grafana, audit, and eval output.
- DLQ/escalation paths are visible, not hidden in logs.
- `doctor` verifies the local scaffold in Phase 0 and local runtime readiness before Phase 1A demos or review.
- Production deferrals are marked as such in docs and not implied to be implemented.

## Provider and Model Governance

The model boundary should support the conversations expected in enterprise adoption:

- Approved provider list with model identifiers and intended use.
- Role/task/tenant-tier routing policy.
- Budget caps by workflow, tenant, and agent role.
- Validator route diversity where available.
- Prompt and model version capture in the decision trail.
- Fallback and degradation policy for provider failure.
- Safety/eval fixture expectations before route promotion.
- Operational support notes for rate limits, incidents, and provider changes.

### Phase 1 Provider Catalogue

| Provider | Models | Intended use | Notes |
|---|---|---|---|
| Local structured boundary | `lighthouse-happy-path-v1` | Phase 1A deterministic local happy-path evidence. | Active implementation for Workstream C; no external credentials or connector authority. |
| Anthropic | Claude (latest stable Opus/Sonnet) | Primary agent reasoning, drafting, qualification. | Primary route via API key. |
| OpenAI | GPT-4-class | Validator-route diversity; second opinion on draft validation. | Diversity satisfies governance invariant. |
| AWS Bedrock | Deferred | Future enterprise hosting boundary. | Phase 2+; signals enterprise-aware routing. |

Routing policy resolves provider per (agent role, workflow stage, tenant tier). Budgets cap cost per invocation and per workflow run.

Phase 1A implements the policy surface enough for Lighthouse through the local
structured boundary and Postgres routing policy. Commercial provider adapters
remain behind the same model boundary and are not required for the first
local evidence slice. Phase 1 does not need a complete provider-management
platform.

## Prompt Governance

Prompts are treated as versioned procedural assets:

- Stored in Git or generated from Git-tracked templates.
- Referenced by stable prompt IDs.
- Hashed at invocation time.
- Bound to agent version and model route by runtime policy.
- Changed through normal review with eval impact considered.
- Never used as the only place where authority, safety, or compliance logic lives.

## Safety and Evaluation Governance

Evaluation is split into technical and behavioural checks:

| Check | Purpose |
|---|---|
| Contract validation | Prove payloads conform to governed schemas. |
| Workflow replay | Prove Temporal determinism survives code change. |
| Trace/eval fixtures | Prove expected business path and final outcome. |
| Governance invariants | Prove forbidden actions are blocked and approvals are required. |
| Budget checks | Prove latency and cost remain visible and bounded. |
| Fault injection | Prove failure branches are real, not diagram-only. |

## Responsible-AI Alignment

Chorus demonstrates responsible-AI alignment through engineering controls:

- Transparency: decision trail, prompt/model identity, and audit views.
- Security: tenant scoping, redaction, gateway enforcement, and secret isolation at the model boundary.
- Accountability: explicit approval/escalation states and durable workflow records.
- Reliability: retries, replay, DLQ, eval fixtures, and contract checks.
- Human oversight: risky writes use proposal or approval paths.
- Change control: ADRs, contract versioning, and CI gates.

## Out of Scope for Phase 1

- Legal/regulatory policy authoring.
- Full model-risk management programme.
- Enterprise identity, SSO, and RBAC.
- Production incident-management integration.
- Real customer data.
- Real production writes to closed third-party platforms. (Connectors run real software in sandbox/local mode — Mailpit for SMTP, public APIs for research, local CRM service — never mocks or hand-rolled fakes.)
