---
type: project-doc
status: active
date: 2026-05-30
---

# Chorus - Evidence Map

## Purpose

This document maps Chorus's engineering claims to the artefacts that support
them, organised by named port. It is the navigation aid for a reviewer who
wants to move from a claim to the code, contract, test, or decision record
behind it.

The map keeps design evidence and implementation evidence distinct. UC1 has
the Mailpit/email runnable path. UC2 has a documented local synthetic
email-intake command for the contract sample, recorded-replay model routes for
the workflow agent tasks, workflow-path eval playback for one happy fixture
and one conflict-exception branch, and projected BFF/UI evidence for workflow
progress, decision-trail rows, Tool Gateway audit rows, and the
`engagement_letter.send` approval-package state. UC3 has product/domain scope,
contracts, shared-spine workflow, sandbox connector adapters, grants,
approval-package inspection, conduct invariants, read-only projection/BFF/UI
inspection, schema-only eval fixtures, and a code-level synthetic email advice
intake adapter with recorded-replay route policies for the workflow agent
tasks. UC3 workflow-path eval playback now covers the happy suitability-report
issue approval fixture and a Consumer Duty vulnerability-support handoff
branch; projection evidence for a triggered local run, the documented
operator command, and live-provider activation remain closure exceptions.

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
| UC2 intake and conduct shape is fully specified | [`product-brief-uc2.md`](product-brief-uc2.md), [`domain-model-uc2.md`](domain-model-uc2.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md), `contracts/intake/uc2/`, `chorus/workflows/uc2_synthetic_intake.py`, `tests/workflows/test_uc2_synthetic_intake.py`, `tests/bff/test_app.py`, [`runbook.md`](runbook.md) | Design and intake contracts complete. The R5 synthetic email-intake adapter validates the `email_legal_intake` sample, normalises it to `Uc2LegalIntake`, derives stable workflow fields, starts the UC2 workflow through the documented `uv run python -m chorus.workflows.uc2_synthetic_intake` operator command, and has happy-path projection/BFF evidence. |
| UC3 intake and conduct shape is fully specified | [`product-brief-uc3.md`](product-brief-uc3.md), [`domain-model-uc3.md`](domain-model-uc3.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md), `contracts/intake/uc3/`, `chorus/workflows/uc3_synthetic_intake.py`, `chorus/eval/uc3_workflow_playback.py`, `tests/workflows/test_uc3_synthetic_intake.py`, `tests/eval/test_uc3_workflow_playback.py` | Design and intake contracts complete. The R5 code-level synthetic email advice intake adapter validates the `email_advice_enquiry` sample, normalises it to `Uc3AdviceEnquiry`, derives stable workflow fields, and delegates to the UC3 workflow starter with duplicate detection. UC3 recorded-replay model-route seeding resolves through the provider port by default, and workflow-path playback now drives the happy issue fixture and vulnerability-support handoff branch through the runtime. The documented operator command and projection evidence remain later P2 work. |

Decision record: [ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md).

## LLM provider port

The LLM provider port carries model invocations and must be provider-agnostic
by construction.

| Claim | Artefacts | Status |
|---|---|---|
| Reasoning runs behind a provider boundary, not a direct SDK call | `chorus/llm_provider/port.py` (surface), `chorus/llm_provider/adapter_openai.py` (OpenAI-SDK transport), `chorus/llm_provider/adapter_replay.py` (recorded-replay substrate), `chorus/agent_runtime/runtime.py` (sequential five-step pipeline), `chorus/agent_runtime/prompt_loader.py` (local prompt loading and hash verification), `chorus/agent_runtime/response_schemas.py` (UC1, UC2, and UC3 task response shapes), `prompts/uc1/`, `prompts/uc2/`, `prompts/uc3/`, `contracts/llm_provider/uc1_agent_io.schema.json`, `contracts/llm_provider/uc2_agent_io.schema.json`, `contracts/llm_provider/uc3_agent_io.schema.json`, `tests/agent_runtime/test_runtime.py` | The port is the only path to a provider SDK. The runtime loads approved local prompt refs, verifies their `sha256` hashes, sends the prompt and schema instruction as system messages, and supplies task-specific `response_shape` metadata before live or recorded-replay-safe invocations. The OpenAI-compatible adapter extracts and locally validates structured JSON, rejecting malformed JSON or empty `structured_data` as non-retryable provider-port failures. UC2 and UC3 route resolution now cover their workflow agent tasks through the same recorded-replay provider boundary. |
| Every invocation records provider and model metadata | `chorus/llm_provider/route_catalogue.py`, `contracts/llm_provider/provider_catalogue.schema.json`, `contracts/llm_provider/model_route_version.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`provider_catalogues`, `provider_catalogue_models`, `model_route_versions`) | Implementation in code. Active local routing policy, route-version rows, provider catalogue rows, BFF inspection views, and eval replay fixtures now align on runtime route `recorded-replay` with `local` / `uc1-happy-path-v1` for UC1. UC2 route-policy and route-version rows now align on the same local recorded-replay route for `uc2_matter_classification`, `uc2_party_extraction`, `uc2_conflict_determination`, and `uc2_engagement_decision`. UC3 route-policy and route-version rows now align on the same local recorded-replay route for `uc3_advice_scope_classification`, `uc3_fact_find_summary`, `uc3_risk_profile_assessment`, `uc3_consumer_duty_support_assessment`, and `uc3_suitability_conclusion`; OpenAI `gpt-5.4-mini-2026-03-17` / `OPENAI_API_KEY` and DeepSeek `deepseek-v4-flash` / `DEEPSEEK_API_KEY` were verified from official provider docs on 2026-05-24 and remain disabled until R5 P3. |
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
| UC2 connector inventory is contract-declared, adapter-registered, grant-expressible, and inspectable through read-only projections | [`product-brief-uc2.md`](product-brief-uc2.md), [`domain-model-uc2.md`](domain-model-uc2.md), `contracts/connector/uc2/`, `contracts/connector/tool_call.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql`, `infrastructure/postgres/seeds/001_demo_tenants.sql`, `chorus/workflows/uc2.py`, `chorus/connectors/uc2.py`, `chorus/persistence/projection.py`, `chorus/bff/app.py`, `frontend/src/routes/workflows.$workflowId.tsx`, `frontend/src/api/fixtures.ts`, `chorus/eval/use_cases/uc2_conduct.py`, `chorus/eval/uc2_workflow_playback.py`, `tests/connectors/test_uc2_connectors.py`, `tests/tool_gateway/test_gateway.py`, `tests/bff/test_app.py`, `tests/bff/test_app_unit.py`, `tests/persistence/test_postgres_foundation.py`, `tests/eval/test_run.py`, `tests/eval/test_uc2_workflow_playback.py`, `tests/workflows/test_uc2_workflow.py`, [`runbook.md`](runbook.md) | Contract surface complete for conflict check, KYC / beneficial ownership, AML record store, and engagement-letter store arguments. The UC2 workflow definition routes the declared tool names through `WorkflowSpine.connector_call`; the default connector registry registers deterministic sandbox adapters for those tool names; tenant-demo grant seeds express the UC2 authority surface with `engagement_letter.send` as the approval-required write; focused tests prove Tool Gateway validation, safe approval-package refs, DB grant alignment, workflow-path playback, and read-only BFF/UI inspection of projected UC2 workflow progress, decision-trail rows, Tool Gateway audit rows, and approval-package action refs. Conflict-exception and AML EDD approvals are workflow/manual-review conduct evidence because no exact connector request binds those packages. UC2 local intake has a documented fixture adapter, recorded-replay model routes now resolve, and workflow-path playback exercises happy-path send approval plus the conflict-exception manual-review branch. |
| UC3 connector inventory is contract-declared, workflow-wired, adapter-registered, grant-expressible, and inspectable through read-only projections | [`product-brief-uc3.md`](product-brief-uc3.md), [`domain-model-uc3.md`](domain-model-uc3.md), `contracts/connector/uc3/`, `contracts/connector/tool_call.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql`, `infrastructure/postgres/seeds/001_demo_tenants.sql`, `chorus/workflows/uc3.py`, `chorus/connectors/uc3.py`, `chorus/persistence/projection.py`, `chorus/bff/app.py`, `frontend/src/routes/workflows.$workflowId.tsx`, `frontend/src/api/fixtures.ts`, `chorus/eval/use_cases/uc3_conduct.py`, `chorus/eval/uc3_workflow_playback.py`, `tests/connectors/test_uc3_connectors.py`, `tests/tool_gateway/test_gateway.py`, `tests/bff/test_app_unit.py`, `tests/persistence/test_postgres_foundation.py`, `tests/eval/test_run.py`, `tests/eval/test_uc3_workflow_playback.py`, `tests/workflows/test_uc3_workflow.py`, `tests/test_contracts.py` | Contract surface complete for attitude-to-risk profiling, capacity-for-loss assessment, platform research, suitability-report draft / issue, decline, and manual-review argument payloads. The UC3 workflow definition routes those declared tool names through `WorkflowSpine.connector_call` using safe refs, bounded categories, policy refs, and conduct-hook refs only; the default connector registry registers deterministic sandbox adapters for those tool names; tenant-demo grant seeds express the UC3 authority surface with `suitability_report.issue` as the approval-required write; focused tests prove generated argument-model validation, safe approval-package refs, DB grant alignment, bounded synthetic outputs, read-only BFF/UI inspection of fixture UC3 workflow progress and `suitability_report.issue.write` approval-package action refs, and workflow-path playback through the happy issue path and vulnerability-support handoff branch. Risk-profile override and vulnerability handoff are workflow/manual-review conduct evidence because no exact connector request binds those approvals. Raw client financial details, vulnerability narratives, platform credentials, report prose, production adviser data, and production customer data stay behind intake or connector-owned stores. UC3 has a code-level synthetic intake starter, recorded-replay route policies for its model-backed workflow tasks, and full workflow-path eval playback; projection evidence for a triggered local run, the documented operator command, and live-provider activation remain recorded closure exceptions. |

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
| Domain events project into read models | `chorus/persistence/projection.py` (workflow + approval/calendar projection), `chorus/persistence/redpanda.py`, `contracts/projection/workflow_event.schema.json`, `tests/persistence/test_redpanda_projection.py`, `tests/bff/test_app.py`, `tests/bff/test_app_unit.py`, `frontend/src/api/fixtures.ts`, `frontend/src/api/queries.test.ts`, `frontend/src/routes/-workflows.$workflowId.test.tsx`, [`runbook.md`](runbook.md) | The projection port keeps the workflow surface plus generic approval-package inspection and the existing calendar-specific compatibility view. Its shared event contract and Postgres checks admit the declared UC1, UC2, and UC3 workflow families; UC2 happy-path playback now projects into BFF/UI inspection with workflow progress, decision-trail rows, Tool Gateway audit rows, and `engagement_letter.send` approval-package state, and the runbook documents the relay/project commands for the local UC2 operator loop. UC3 workflow-path playback captures outbox progress for its happy issue and vulnerability handoff fixtures, but triggered-run projection evidence remains a later P2 slice. |
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
| Eval runs over the audit ports, not in-test bookkeeping | `chorus/eval/common_invariants.py`, `chorus/eval/use_cases/uc1_conduct.py`, `chorus/eval/use_cases/uc2_conduct.py`, `chorus/eval/uc2_workflow_playback.py`, `chorus/eval/use_cases/uc3_conduct.py`, `chorus/eval/uc3_workflow_playback.py`, `chorus/eval/invariants.py`, `chorus/eval/scenario_player.py`, `chorus/eval/fixtures/uc1_happy_path.json`, `chorus/eval/fixtures/uc1_validator_redraft.json`, `chorus/eval/fixtures/uc2/uc2_synthetic_acceptance_conduct.json`, `chorus/eval/fixtures/uc2/uc2_conflict_exception_approval_conduct.json`, `chorus/eval/fixtures/uc3/uc3_synthetic_suitability_conduct.json`, `chorus/eval/fixtures/uc3/uc3_vulnerability_support_handoff_conduct.json`, `tests/eval/test_run.py`, `tests/eval/test_uc2_workflow_playback.py`, `tests/eval/test_uc3_workflow_playback.py` | Invariants assert over captured-run artefacts. UC2 has workflow-path fixture playback through Temporal, Agent Runtime, Tool Gateway, decision/transcript persistence, tool-action audit, approval-package rows, and outbox progress for the happy acceptance/send-approval-gated fixture and a conflict-exception manual-review branch. UC3 now mirrors that shape for a happy suitability-report issue approval fixture and a Consumer Duty vulnerability-support handoff branch. The UC2 and UC3 conduct checks fail loudly when required workflow progress, agent decision, transcript, tool-action audit, or approval-package evidence is missing. |
| Cross-provider replay is a first-class eval mode | `chorus/eval/replay.py`, `chorus/eval/replay_comparator.py`, `contracts/eval/replay_run_record.schema.json`, `chorus/persistence/replay_runs.py`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`replay_run_records`), `chorus/bff/app.py` (`/api/eval/replay-runs`), `chorus/eval/fixtures/transcripts/uc1_classifier_happy.json`, `tests/eval/test_run.py`, `tests/persistence/test_postgres_foundation.py`, `tests/bff/test_app_unit.py` | Recorded-replay exists today and now builds/persists replay-run evidence records linking the original invocation/transcript, alternate route, comparator status/result, lineage refs, and token/cost/latency metrics. The hard-fail tier classifies schema, policy snapshot, conduct hook, unsafe action, audit/transcript, route-governance, and provider-port replay defects. The decision-fail tier classifies bounded UC1 qualification verdict, routing, regulated-outcome, approval-decision, and connector-action category divergence under the same policy snapshot. The review-finding tier records non-terminal recommended-next-step, confidence, rationale, optional field, and evidence-selection divergence without storing raw rationale or customer content. The metrics-only tier records token, latency, retry-count, provider-cost, and safe provider-metadata deltas with bounded reason codes and field names only; live-provider execution remains credential-gated and inactive by default. |

Decision record: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

### Workflow durability

| Claim | Artefacts | Status |
|---|---|---|
| The workflow spine is durable and replay-stable | `chorus/workflows/spine.py` (`WorkflowSpine`, `WorkflowDefinition`, `WorkflowStepDefinition`), `chorus/workflows/uc1.py` (UC1 enquiry-qualification workflow), `chorus/workflows/uc2.py` (UC2 legal-services intake and conflict-check workflow), `chorus/workflows/uc2_synthetic_intake.py`, `chorus/eval/uc2_workflow_playback.py`, `chorus/workflows/uc3.py` (UC3 IFA suitability workflow), `chorus/workflows/uc3_synthetic_intake.py`, `chorus/eval/uc3_workflow_playback.py`, `tests/workflows/`, `tests/eval/test_uc2_workflow_playback.py`, `tests/eval/test_uc3_workflow_playback.py`, `tests/bff/test_app.py`, [`runbook.md`](runbook.md) | UC1 runs on the spine as the Mailpit/email local runnable path. UC2 and UC3 now have definition-first workflows over the same primitives with focused Temporal tests, inline replay history, connector authority, conduct invariants, schema-only eval fixtures, and read-only projection inspection evidence. UC2 has a documented synthetic start path for the email intake sample, recorded-replay model routes for its workflow agent tasks, workflow-path playback for the happy acceptance path plus one conflict-exception branch, and projected BFF/UI evidence for the happy path. UC3 has a code-level synthetic start path, shared-worker registration, recorded-replay model routes for its workflow agent tasks, and workflow-path playback for the happy issue path plus vulnerability-support handoff branch; the operator command and triggered-run projection evidence remain open. |

Decision records: [ADR 0017](../adrs/0017-langgraph-removed-from-agent-execution.md)
and [ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md).

## R4 Closure

The closed R4 backlog, exit criteria, evidence notes, and recorded closure
exceptions are in
[`transformation/r4-implementation-backlog.md`](transformation/r4-implementation-backlog.md).
