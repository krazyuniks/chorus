---
type: project-doc
status: active
date: 2026-05-25
---

# Chorus - Evidence Map

## Purpose

This document maps Chorus's engineering claims to the artefacts that support
them, organised by named port. It is the navigation aid for a reviewer who
wants to move from a claim to the code, contract, test, or decision record
behind it.

The map keeps design evidence and implementation evidence distinct. UC1 has
the concrete runnable path today. UC2 and UC3 have product/domain scope,
contracts, shared-spine workflows, sandbox connector adapters, grants,
approval-package inspection, conduct invariants, read-only projection/BFF/UI
inspection, and schema-only eval fixtures. UC2 also has an R5 code-level
synthetic email-intake adapter for the documented contract sample. UC2 and
UC3 are not claimed as locally runnable use cases because documented operator
intake commands, use-case provider route activation, and full fixture playback
remain closure exceptions.

## How to use this map

Read top to bottom for the port-by-port narrative. Each port section carries a
claim-to-artefact table and the current decision records that govern it.

## Intake port

The intake port receives inbound business work; channel adapters
contract-validate and normalise it.

| Claim | Artefacts | Status |
|---|---|---|
| Inbound work enters through a contract-validated channel adapter | `chorus/workflows/mailpit.py`, `chorus/workflows/intake.py`, `contracts/intake/uc1/` (email-channel, web-form-channel, partner-portal-channel), `tests/workflows/test_mailpit_intake.py` | UC1 Mailpit/email intake is runnable. UC1 web-form and partner-portal contracts are present, but additional runnable adapter paths are deferred beyond R4. |
| Channel-specific idempotency maps to one work identifier | `chorus/workflows/mailpit.py` (Message-ID dedupe, stable workflow ID) | Implementation in code. |
| UC1 intake shape is fully specified | [`product-brief.md`](product-brief.md), [`domain-model.md`](domain-model.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md) | Design complete. |
| UC2 intake and conduct shape is fully specified | [`product-brief-uc2.md`](product-brief-uc2.md), [`domain-model-uc2.md`](domain-model-uc2.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md), `contracts/intake/uc2/`, `chorus/workflows/uc2_synthetic_intake.py`, `tests/workflows/test_uc2_synthetic_intake.py` | Design and intake contracts complete. The R5 synthetic email-intake adapter validates the `email_legal_intake` sample, normalises it to `Uc2LegalIntake`, derives stable workflow fields, and starts the UC2 workflow. The operator-facing command, provider route activation, and full eval playback remain open. |
| UC3 intake and conduct shape is fully specified | [`product-brief-uc3.md`](product-brief-uc3.md), [`domain-model-uc3.md`](domain-model-uc3.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md), `contracts/intake/uc3/` | Design and intake contracts complete. No UC3 local intake adapter starts a workflow yet; that is a recorded R4 closure exception. |

Decision record: [ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md).

## LLM provider port

The LLM provider port carries model invocations and must be provider-agnostic
by construction.

| Claim | Artefacts | Status |
|---|---|---|
| Reasoning runs behind a provider boundary, not a direct SDK call | `chorus/llm_provider/port.py` (surface), `chorus/llm_provider/adapter_openai.py` (OpenAI-SDK transport), `chorus/llm_provider/adapter_replay.py` (recorded-replay substrate), `chorus/agent_runtime/runtime.py` (sequential five-step pipeline), `chorus/agent_runtime/prompt_loader.py` (local prompt loading and hash verification), `chorus/agent_runtime/response_schemas.py` (UC1 task response shapes), `prompts/uc1/`, `contracts/llm_provider/uc1_agent_io.schema.json`, `tests/agent_runtime/test_runtime.py` | The port is the only path to a provider SDK. The runtime loads approved local prompt refs, verifies their `sha256` hashes, sends the prompt and schema instruction as system messages, and supplies task-specific `response_shape` metadata before live or recorded-replay-safe invocations. The OpenAI-compatible adapter extracts and locally validates structured JSON, rejecting malformed JSON or empty `structured_data` as non-retryable provider-port failures. |
| Every invocation records provider and model metadata | `chorus/llm_provider/route_catalogue.py`, `contracts/llm_provider/provider_catalogue.schema.json`, `contracts/llm_provider/model_route_version.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`provider_catalogues`, `provider_catalogue_models`, `model_route_versions`) | Implementation in code. Active local routing policy, route-version rows, provider catalogue rows, BFF inspection views, and eval replay fixtures now align on runtime route `recorded-replay` with `local` / `uc1-happy-path-v1`; OpenAI `gpt-5.4-mini-2026-03-17` / `OPENAI_API_KEY` and DeepSeek `deepseek-v4-flash` / `DEEPSEEK_API_KEY` were verified from official provider docs on 2026-05-24; source links are recorded in `docs/transformation/r4-design-decisions.md`. |
| Provider neutrality and the route catalogue are specified | [`transformation/engineering-thesis.md`](transformation/engineering-thesis.md) (LLM provider port section) | Design complete. |

Decision records: [ADR 0018](../adrs/0018-llm-provider-port.md) and
[ADR 0017](../adrs/0017-langgraph-removed-from-agent-execution.md).

## Connector port

The connector port is the external-action authority; the Tool Gateway is its
authority layer.

| Claim | Artefacts | Status |
|---|---|---|
| Every connector call passes grant, mode, argument validation, verdict, and audit | `chorus/tool_gateway/gateway.py`, `chorus/connectors/types.py` (`ConnectorAdapter`, `ConnectorRegistry`, `ToolSpec`), `contracts/connector/`, `tests/tool_gateway/test_gateway.py` | Implementation in code. |
| Connectors are real software in sandbox or local mode, not mocks | `chorus/connectors/uc1.py` (six UC1 sandbox adapters), `chorus/persistence/uc1_connectors.py` (UC1 broker-firm-side routing records plus seeded read-connector reference data), `chorus/connectors/uc2.py` (deterministic UC2 sandbox adapters), `chorus/connectors/uc3.py` (deterministic UC3 sandbox adapters), `chorus/connectors/calendar.py` (Radicale-backed CalDAV adapter) | Implementation in code. |
| Dispatch is an adapter registry, not a hardcoded match block | `chorus/connectors/types.py` + `chorus/connectors/__init__.py` (`default_registry`), `chorus/tool_gateway/gateway.py` | New adapters register without editing the gateway. |
| UC1 connector inventory is specified and live | [`r1-adapter-mapping.md`](r1-adapter-mapping.md), `chorus/workflows/uc1.py`, `chorus/connectors/uc1.py`, `chorus/persistence/uc1_connectors.py`, `chorus/eval/fixtures/uc1_accepted_routing.json`, `chorus/eval/fixtures/uc1_referred_routing.json`, `chorus/eval/fixtures/uc1_declined_routing.json` | UC1 adapters exist. The workflow routes `accept`, `refer`, and `decline` qualification verdicts through the Tool Gateway to the persisted quoting queue, referral inbox, and decline ledger connectors; missing-data verdicts stay on the proposal-mode outbound-comms path. Customer profile and product catalogue lookups read tenant-scoped synthetic Postgres seed rows. The default UC1 policy snapshot ref is materialised in `policy_snapshots`. The UC1 eval suite now includes terminal routing fixtures and invariants for accepted, referred, and declined connector paths. |
| UC2 connector inventory is contract-declared, adapter-registered, grant-expressible, and inspectable through read-only projections | [`product-brief-uc2.md`](product-brief-uc2.md), [`domain-model-uc2.md`](domain-model-uc2.md), `contracts/connector/uc2/`, `contracts/connector/tool_call.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql`, `infrastructure/postgres/seeds/001_demo_tenants.sql`, `chorus/workflows/uc2.py`, `chorus/connectors/uc2.py`, `chorus/persistence/projection.py`, `chorus/bff/app.py`, `frontend/src/routes/workflows.$workflowId.tsx`, `frontend/src/api/fixtures.ts`, `chorus/eval/use_cases/uc2_conduct.py`, `tests/connectors/test_uc2_connectors.py`, `tests/tool_gateway/test_gateway.py`, `tests/bff/test_app_unit.py`, `tests/persistence/test_postgres_foundation.py`, `tests/eval/test_run.py`, `tests/workflows/test_uc2_workflow.py` | Contract surface complete for conflict check, KYC / beneficial ownership, AML record store, and engagement-letter store arguments. The UC2 workflow definition routes the declared tool names through `WorkflowSpine.connector_call`; the default connector registry registers deterministic sandbox adapters for those tool names; tenant-demo grant seeds express the UC2 authority surface with `engagement_letter.send` as the approval-required write; focused tests prove Tool Gateway validation, safe approval-package refs, DB grant alignment, and read-only BFF/UI inspection of UC2 workflow progress and approval-package action refs. Conflict-exception and AML EDD approvals are workflow/manual-review conduct evidence because no exact connector request binds those packages. UC2 local intake, use-case provider route activation, and full eval fixture playback remain recorded closure exceptions. |
| UC3 connector inventory is contract-declared, workflow-wired, adapter-registered, grant-expressible, and inspectable through read-only projections | [`product-brief-uc3.md`](product-brief-uc3.md), [`domain-model-uc3.md`](domain-model-uc3.md), `contracts/connector/uc3/`, `contracts/connector/tool_call.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql`, `infrastructure/postgres/seeds/001_demo_tenants.sql`, `chorus/workflows/uc3.py`, `chorus/connectors/uc3.py`, `chorus/persistence/projection.py`, `chorus/bff/app.py`, `frontend/src/routes/workflows.$workflowId.tsx`, `frontend/src/api/fixtures.ts`, `chorus/eval/use_cases/uc3_conduct.py`, `tests/connectors/test_uc3_connectors.py`, `tests/tool_gateway/test_gateway.py`, `tests/bff/test_app_unit.py`, `tests/persistence/test_postgres_foundation.py`, `tests/eval/test_run.py`, `tests/workflows/test_uc3_workflow.py`, `tests/test_contracts.py` | Contract surface complete for attitude-to-risk profiling, capacity-for-loss assessment, platform research, suitability-report draft / issue, decline, and manual-review argument payloads. The UC3 workflow definition routes those declared tool names through `WorkflowSpine.connector_call` using safe refs, bounded categories, policy refs, and conduct-hook refs only; the default connector registry registers deterministic sandbox adapters for those tool names; tenant-demo grant seeds express the UC3 authority surface with `suitability_report.issue` as the approval-required write; focused tests prove generated argument-model validation, safe approval-package refs, DB grant alignment, bounded synthetic outputs, and read-only BFF/UI inspection of UC3 workflow progress and `suitability_report.issue.write` approval-package action refs. Risk-profile override and vulnerability handoff are workflow/manual-review conduct evidence because no exact connector request binds those approvals. Raw client financial details, vulnerability narratives, platform credentials, report prose, production adviser data, and production customer data stay behind intake or connector-owned stores. UC3 local intake, use-case provider route activation, and full eval fixture playback remain recorded closure exceptions. |

Decision records: [ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md)
and [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

## Audit / transcript ports

The audit surface is two ports: a structured decision-trail port and a
full-fidelity transcript port.

| Claim | Artefacts | Status |
|---|---|---|
| Every governed decision has a structured decision-trail record | `chorus/persistence/audit_port.py` (`AuditPortStore.list_decision_trail`), `contracts/audit/agent_invocation_record.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`decision_trail_entries`, `policy_snapshots`), `chorus/agent_runtime/runtime.py` (`record_decision`) | Implementation in code. Qualifier decision metadata includes the emitted `policy_snapshot_ref`, and the local UC1 ref resolves to an immutable seeded policy snapshot row. |
| The transcript carries enough to replay an invocation | `chorus/persistence/audit_port.py`, `contracts/audit/agent_invocation_transcript.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`agent_invocation_transcripts`), `chorus/agent_runtime/runtime.py` (`record_transcript`), `chorus/eval/scenario_player.py` | The transcript port records replay inputs, including the loaded system prompt message, generated response-schema instruction, route metadata, and provider metadata. Decision-trail metadata stores the safe prompt ref/hash and response-schema ref/hash evidence. |
| Audit completeness: no LLM invocation or connector call is unattributed | `chorus/eval/common_invariants.py` (`assert_audit_completeness`), [`transformation/eval-reshape-directions.md`](transformation/eval-reshape-directions.md) | The invariant suite asserts it. |

Decision record: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

## Projection sink

The projection sink derives read models for inspection.

| Claim | Artefacts | Status |
|---|---|---|
| Domain events project into read models | `chorus/persistence/projection.py` (workflow + approval/calendar projection), `chorus/persistence/redpanda.py`, `contracts/projection/workflow_event.schema.json`, `tests/persistence/test_redpanda_projection.py`, `tests/bff/test_app_unit.py`, `frontend/src/api/fixtures.ts`, `frontend/src/api/queries.test.ts` | The projection port keeps the workflow surface plus generic approval-package inspection and the existing calendar-specific compatibility view. Its shared event contract and Postgres checks admit the declared UC1, UC2, and UC3 workflow families; UC2 and UC3 workflow/projection inspection can show safe workflow progress and approval-package state when rows exist, but neither use case is yet locally runnable from an intake path. |
| The read surface is read-only | `chorus/bff/app.py` (per-port `PortReaders` dependency), `frontend/src/routes/` | Implementation in code. |
| Replaying the same events twice converges | `tests/persistence/test_redpanda_projection.py`, `chorus/eval/common_invariants.py` (`assert_projection_convergence`) | Implementation in code. |

Decision record: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

## Observability sink

The observability sink carries traces, metrics, logs, and optional LLM
observability.

| Claim | Artefacts | Status |
|---|---|---|
| Traces, metrics, and logs flow through one pipeline | `chorus/observability/`, `compose.yml` (OTel collector, Tempo, Loki, Prometheus, Grafana), `infrastructure/grafana/` | Implementation in code. |
| Operational surfaces correlate by one identifier | `chorus/observability/` (`set_current_span_attributes`, `current_otel_ids`), `runbook.md` | Implementation in code. |
| Audit and telemetry stay separate | [`architecture.md`](architecture.md) (cross-cutting concerns) | Design complete. |

Decision record: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

## Cross-cutting

### Contracts

| Claim | Artefacts | Status |
|---|---|---|
| Cross-port payloads are JSON Schema with a drift gate | `contracts/` (grouped around the six ports plus `eval/`), `chorus/contracts/generated/`, `chorus/contracts/check.py` | Current contract surface. |

Decision records: [ADR 0018](../adrs/0018-llm-provider-port.md) and
[ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

### Replay as eval substrate

| Claim | Artefacts | Status |
|---|---|---|
| Eval runs over the audit ports, not in-test bookkeeping | `chorus/eval/common_invariants.py`, `chorus/eval/use_cases/uc1_conduct.py`, `chorus/eval/use_cases/uc2_conduct.py`, `chorus/eval/use_cases/uc3_conduct.py`, `chorus/eval/invariants.py`, `chorus/eval/scenario_player.py`, `chorus/eval/fixtures/uc1_happy_path.json`, `chorus/eval/fixtures/uc1_validator_redraft.json`, `chorus/eval/fixtures/uc2/uc2_synthetic_acceptance_conduct.json`, `chorus/eval/fixtures/uc3/uc3_synthetic_suitability_conduct.json`, `tests/eval/test_run.py` | Invariants assert over captured-run artefacts. UC2 has focused conduct checks over safe synthetic captured-run artefacts for SRA / AML engagement-decision evidence, no-conflict / standard-risk acceptance boundaries, approval-gated `engagement_letter.send`, and a schema-only synthetic UC2 fixture. UC3 has focused conduct checks over safe synthetic captured-run artefacts for FCA suitability / PROD / Consumer Duty evidence, risk / support manual-handoff boundaries, approval-gated `suitability_report.issue`, safe connector refs, and a schema-only synthetic UC3 fixture. UC2 and UC3 full fixture playback remain recorded R4 closure exceptions. |
| Cross-provider replay is a first-class eval mode | `chorus/eval/replay.py`, `chorus/eval/replay_comparator.py`, `contracts/eval/replay_run_record.schema.json`, `chorus/persistence/replay_runs.py`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`replay_run_records`), `chorus/bff/app.py` (`/api/eval/replay-runs`), `chorus/eval/fixtures/transcripts/uc1_classifier_happy.json`, `tests/eval/test_run.py`, `tests/persistence/test_postgres_foundation.py`, `tests/bff/test_app_unit.py` | Recorded-replay exists today and now builds/persists replay-run evidence records linking the original invocation/transcript, alternate route, comparator status/result, lineage refs, and token/cost/latency metrics. The hard-fail tier classifies schema, policy snapshot, conduct hook, unsafe action, audit/transcript, route-governance, and provider-port replay defects. The decision-fail tier classifies bounded UC1 qualification verdict, routing, regulated-outcome, approval-decision, and connector-action category divergence under the same policy snapshot. The review-finding tier records non-terminal recommended-next-step, confidence, rationale, optional field, and evidence-selection divergence without storing raw rationale or customer content. The metrics-only tier records token, latency, retry-count, provider-cost, and safe provider-metadata deltas with bounded reason codes and field names only; live-provider execution remains credential-gated and inactive by default. |

Decision record: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

### Workflow durability

| Claim | Artefacts | Status |
|---|---|---|
| The workflow spine is durable and replay-stable | `chorus/workflows/spine.py` (`WorkflowSpine`, `WorkflowDefinition`, `WorkflowStepDefinition`), `chorus/workflows/uc1.py` (UC1 enquiry-qualification workflow), `chorus/workflows/uc2.py` (UC2 legal-services intake and conflict-check workflow), `chorus/workflows/uc2_synthetic_intake.py`, `chorus/workflows/uc3.py` (UC3 IFA suitability workflow), `tests/workflows/` | UC1 runs on the spine as the local runnable path. UC2 and UC3 now have definition-first workflows over the same primitives with focused Temporal tests, inline replay history, connector authority, conduct invariants, schema-only eval fixtures, and read-only projection inspection evidence. UC2 has a code-level synthetic start path for the email intake sample; it is not yet a documented runnable operator path because use-case provider route activation and full eval fixture playback remain open. UC3 local intake remains absent. |

Decision records: [ADR 0017](../adrs/0017-langgraph-removed-from-agent-execution.md)
and [ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md).

## R4 Closure

The closed R4 backlog, exit criteria, evidence notes, and recorded closure
exceptions are in
[`transformation/r4-implementation-backlog.md`](transformation/r4-implementation-backlog.md).
