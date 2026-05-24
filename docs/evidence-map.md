---
type: project-doc
status: active
date: 2026-05-24
---

# Chorus - Evidence Map

## Purpose

This document maps Chorus's engineering claims to the artefacts that support
them, organised by named port. It is the navigation aid for a reviewer who
wants to move from a claim to the code, contract, test, or decision record
behind it.

The map describes two kinds of evidence and keeps them distinct:

- **Design evidence** - the reset bundle, the R1 product and domain artefacts,
  and the R2 documentation set. This is complete for UC1 and confirmed for
  UC2 and UC3.
- **Implementation evidence** - the runtime code. R3 (contract and code
  terminology refactor) closed 2026-05-24: the code now carries the named-
  port surface, the connector adapter registry, the audit-port split, the
  workflow spine with UC1 on it, the per-port projection / doctor
  decomposition, and the invariant-plus-replay eval. UC2 and UC3 land in
  R4.

UC1 evidence is the most concrete. UC2 and UC3 evidence is sketch-only - the
confirmation note and the adapter-mapping deltas - until R4.

## How to use this map

Read top to bottom for the port-by-port narrative. Each port section carries a
claim-to-artefact table and the decision records that govern it. The pre-reset
chronological ledger is not reproduced here; it is linked at the end.

## Intake port

The intake port receives inbound business work; channel adapters
contract-validate and normalise it.

| Claim | Artefacts | Status |
|---|---|---|
| Inbound work enters through a contract-validated channel adapter | `chorus/workflows/mailpit.py`, `chorus/workflows/intake.py`, `contracts/intake/uc1/` (email-channel, web-form-channel, partner-portal-channel), `tests/workflows/test_mailpit_intake.py` | Implementation in code: UC1 channel adapters and contracts in place after R3 E. |
| Channel-specific idempotency maps to one work identifier | `chorus/workflows/mailpit.py` (Message-ID dedupe, stable workflow ID) | Implementation in code. |
| UC1 intake shape is fully specified | [`product-brief.md`](product-brief.md), [`domain-model.md`](domain-model.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md) | Design complete. |

Decision records: [ADR 0008](../adrs/0008-email-intake-via-mailpit.md).

## LLM provider port

The LLM provider port carries model invocations and must be provider-agnostic
by construction.

| Claim | Artefacts | Status |
|---|---|---|
| Reasoning runs behind a provider boundary, not a direct SDK call | `chorus/llm_provider/port.py` (surface), `chorus/llm_provider/adapter_openai.py` (OpenAI-SDK transport), `chorus/llm_provider/adapter_replay.py` (recorded-replay substrate), `chorus/agent_runtime/runtime.py` (sequential five-step pipeline), `contracts/llm_provider/uc1_agent_io.schema.json`, `tests/agent_runtime/test_runtime.py` | Implementation in code: LangGraph retired in R3 B; the port is the only path to a provider SDK. |
| Every invocation records provider and model metadata | `chorus/llm_provider/route_catalogue.py`, `contracts/llm_provider/provider_catalogue.schema.json`, `contracts/llm_provider/model_route_version.schema.json`, `infrastructure/postgres/migrations/005_provider_governance_catalogue.sql` | Implementation in code. |
| Provider neutrality and the route catalogue are specified | [`transformation/engineering-thesis.md`](transformation/engineering-thesis.md) (LLM provider port section) | Design complete. |

Decision records: [ADR 0018](../adrs/0018-llm-provider-port.md) (LLM provider
port), [ADR 0017](../adrs/0017-langgraph-removed-from-agent-execution.md)
(LangGraph removed from the agent execution path, reverses
[ADR 0012](../adrs/0012-langgraph-agent-execution-runtime.md)),
[ADR 0011](../adrs/0011-phase-2-governed-platform-expansion.md).

## Connector port

The connector port is the external-action authority; the Tool Gateway is its
authority layer.

| Claim | Artefacts | Status |
|---|---|---|
| Every connector call passes grant, mode, argument validation, verdict, and audit | `chorus/tool_gateway/gateway.py`, `chorus/connectors/types.py` (`ConnectorAdapter`, `ConnectorRegistry`, `ToolSpec`), `contracts/connector/`, `tests/tool_gateway/test_gateway.py` | Implementation in code. |
| Connectors are real software in sandbox or local mode, not mocks | `chorus/connectors/uc1.py` (six UC1 sandbox adapters), `chorus/connectors/calendar.py` (Radicale-backed CalDAV adapter) | Implementation in code. |
| Dispatch is an adapter registry, not a hardcoded match block | `chorus/connectors/types.py` + `chorus/connectors/__init__.py` (`default_registry`), `chorus/tool_gateway/gateway.py` | Implementation in code: the hardcoded match block retired in R3 D; new adapters register without editing the gateway. |
| UC1 connector inventory is specified and live | [`r1-adapter-mapping.md`](r1-adapter-mapping.md), `chorus/connectors/uc1.py` | Design complete; R3 D landed the UC1 adapters. |

Decision records: [ADR 0004](../adrs/0004-agent-runtime-and-tool-gateway.md),
[ADR 0014](../adrs/0014-connector-expansion-approval-hardening-scope.md).

## Audit / transcript ports

The audit surface is two ports: a structured decision-trail port and a
full-fidelity transcript port.

| Claim | Artefacts | Status |
|---|---|---|
| Every governed decision has a structured decision-trail record | `chorus/persistence/audit_port.py` (`AuditPortStore.list_decision_trail`), `contracts/audit/agent_invocation_record.schema.json`, `infrastructure/postgres/migrations/001_phase_1a_persistence_foundation.sql` (`decision_trail_entries`), `chorus/agent_runtime/runtime.py` (`record_decision`) | Implementation in code. |
| The transcript carries enough to replay an invocation | `chorus/persistence/audit_port.py`, `contracts/audit/agent_invocation_transcript.schema.json`, `infrastructure/postgres/migrations/010_audit_transcript_port.sql`, `chorus/agent_runtime/runtime.py` (`record_transcript`) | Implementation in code: R3 C split the single audit store into the decision-trail port and the transcript port. |
| Audit completeness: no LLM invocation or connector call is unattributed | `chorus/eval/invariants.py` (`assert_audit_completeness`), [`transformation/eval-reshape-directions.md`](transformation/eval-reshape-directions.md) | Implementation in code: R3 G's invariant suite asserts it. |

Decision records: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md)
(audit ports and replay-eval),
[ADR 0005](../adrs/0005-postgres-first-storage.md).

## Projection sink

The projection sink derives read models for inspection.

| Claim | Artefacts | Status |
|---|---|---|
| Domain events project into read models | `chorus/persistence/projection.py` (workflow + calendar projection), `chorus/persistence/redpanda.py`, `tests/persistence/test_redpanda_projection.py` | Implementation in code: R3 F decomposed `projection.py` along port boundaries; the projection port keeps the workflow + calendar surface. |
| The read surface is read-only | `chorus/bff/app.py` (per-port `PortReaders` dependency), `frontend/src/routes/` | Implementation in code. |
| Replaying the same events twice converges | `tests/persistence/test_redpanda_projection.py`, `chorus/eval/invariants.py` (`assert_projection_convergence`) | Implementation in code. |

Decision records: [ADR 0003](../adrs/0003-redpanda-event-visibility.md),
[ADR 0005](../adrs/0005-postgres-first-storage.md).

## Observability sink

The observability sink carries traces, metrics, logs, and optional LLM
observability.

| Claim | Artefacts | Status |
|---|---|---|
| Traces, metrics, and logs flow through one pipeline | `chorus/observability/`, `compose.yml` (OTel collector, Tempo, Loki, Prometheus, Grafana), `infrastructure/grafana/` | Implementation in code. |
| Operational surfaces correlate by one identifier | `chorus/observability/` (`set_current_span_attributes`, `current_otel_ids`), `runbook.md` | Implementation in code. |
| Audit and telemetry stay separate | [`architecture.md`](architecture.md) (cross-cutting concerns) | Design complete. |

Decision records: [ADR 0010](../adrs/0010-observability-pipeline.md).

## Cross-cutting

### Contracts

| Claim | Artefacts | Status |
|---|---|---|
| Cross-port payloads are JSON Schema with a drift gate | `contracts/` (regrouped around the six ports plus `eval/`), `chorus/contracts/generated/`, `chorus/contracts/check.py` | Implementation in code: R3 A landed the regroup; 24 schemas. |

Decision records: [ADR 0006](../adrs/0006-json-schema-contracts.md).

### Replay as eval substrate

| Claim | Artefacts | Status |
|---|---|---|
| Eval runs over the audit ports, not in-test bookkeeping | `chorus/eval/invariants.py`, `chorus/eval/scenario_player.py`, `chorus/eval/fixtures/uc1_happy_path.json`, `chorus/eval/fixtures/uc1_validator_redraft.json`, `tests/eval/test_run.py` | Implementation in code: R3 G replaced path-enumeration with the invariant suite over captured-run artefacts. |
| Cross-provider replay is a first-class eval mode | `chorus/eval/replay.py`, `chorus/eval/fixtures/transcripts/uc1_classifier_happy.json` | Implementation in code: R3 G ships the `eval replay` subcommand through the recorded-replay route; cross-provider replay through the OpenAI-SDK adapter lands in R4. |

Decision records: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md)
(audit ports and replay-eval),
[ADR 0007](../adrs/0007-trace-evaluation-harness.md).

### Workflow durability

| Claim | Artefacts | Status |
|---|---|---|
| The workflow spine is durable and replay-stable | `chorus/workflows/spine.py` (`WorkflowSpine`, `WorkflowDefinition`, `WorkflowStepDefinition`), `chorus/workflows/uc1.py` (UC1 enquiry-qualification workflow), `tests/workflows/` | Implementation in code: R3 E factored the spine out of the Lighthouse / Support duplication; UC1 runs on the spine; Lighthouse and Support Triage retired. |

Decision records: [ADR 0002](../adrs/0002-temporal-durable-orchestration.md).

## Pre-reset evidence

The chronological phase ledger (Phase 0 through Phase 2E) is not reproduced in
this map. It is preserved in
[`transformation/phase-2-archive.md`](transformation/phase-2-archive.md). The
disposition of each pre-reset component - preserved, reframed, or retired - is
recorded in
[`transformation/current-state-inventory.md`](transformation/current-state-inventory.md)
and [`r1-exit-criteria.md`](r1-exit-criteria.md). R3 sign-off is in
[`r3-exit-criteria.md`](r3-exit-criteria.md).
