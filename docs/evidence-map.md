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

The map keeps design evidence and implementation evidence distinct. UC1 has
the concrete runnable path today. UC2 now has product/domain scope, while UC3
has confirmed scope and adapter deltas pending its R4 product/domain slice.

## How to use this map

Read top to bottom for the port-by-port narrative. Each port section carries a
claim-to-artefact table and the current decision records that govern it.

## Intake port

The intake port receives inbound business work; channel adapters
contract-validate and normalise it.

| Claim | Artefacts | Status |
|---|---|---|
| Inbound work enters through a contract-validated channel adapter | `chorus/workflows/mailpit.py`, `chorus/workflows/intake.py`, `contracts/intake/uc1/` (email-channel, web-form-channel, partner-portal-channel), `tests/workflows/test_mailpit_intake.py` | UC1 Mailpit/email intake is runnable; web-form and partner-portal contracts are present, with runnable adapter paths an R4 decision. |
| Channel-specific idempotency maps to one work identifier | `chorus/workflows/mailpit.py` (Message-ID dedupe, stable workflow ID) | Implementation in code. |
| UC1 intake shape is fully specified | [`product-brief.md`](product-brief.md), [`domain-model.md`](domain-model.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md) | Design complete. |
| UC2 intake and conduct shape is fully specified | [`product-brief-uc2.md`](product-brief-uc2.md), [`domain-model-uc2.md`](domain-model-uc2.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md) | Design complete. Runtime implementation is later R4 work. |

Decision record: [ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md).

## LLM provider port

The LLM provider port carries model invocations and must be provider-agnostic
by construction.

| Claim | Artefacts | Status |
|---|---|---|
| Reasoning runs behind a provider boundary, not a direct SDK call | `chorus/llm_provider/port.py` (surface), `chorus/llm_provider/adapter_openai.py` (OpenAI-SDK transport), `chorus/llm_provider/adapter_replay.py` (recorded-replay substrate), `chorus/agent_runtime/runtime.py` (sequential five-step pipeline), `contracts/llm_provider/uc1_agent_io.schema.json`, `tests/agent_runtime/test_runtime.py` | The port is the only path to a provider SDK. |
| Every invocation records provider and model metadata | `chorus/llm_provider/route_catalogue.py`, `contracts/llm_provider/provider_catalogue.schema.json`, `contracts/llm_provider/model_route_version.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`provider_catalogues`, `provider_catalogue_models`, `model_route_versions`) | Implementation in code. |
| Provider neutrality and the route catalogue are specified | [`transformation/engineering-thesis.md`](transformation/engineering-thesis.md) (LLM provider port section) | Design complete. |

Decision records: [ADR 0018](../adrs/0018-llm-provider-port.md) and
[ADR 0017](../adrs/0017-langgraph-removed-from-agent-execution.md).

## Connector port

The connector port is the external-action authority; the Tool Gateway is its
authority layer.

| Claim | Artefacts | Status |
|---|---|---|
| Every connector call passes grant, mode, argument validation, verdict, and audit | `chorus/tool_gateway/gateway.py`, `chorus/connectors/types.py` (`ConnectorAdapter`, `ConnectorRegistry`, `ToolSpec`), `contracts/connector/`, `tests/tool_gateway/test_gateway.py` | Implementation in code. |
| Connectors are real software in sandbox or local mode, not mocks | `chorus/connectors/uc1.py` (six UC1 sandbox adapters), `chorus/connectors/calendar.py` (Radicale-backed CalDAV adapter) | Implementation in code. |
| Dispatch is an adapter registry, not a hardcoded match block | `chorus/connectors/types.py` + `chorus/connectors/__init__.py` (`default_registry`), `chorus/tool_gateway/gateway.py` | New adapters register without editing the gateway. |
| UC1 connector inventory is specified and live | [`r1-adapter-mapping.md`](r1-adapter-mapping.md), `chorus/connectors/uc1.py` | UC1 adapters exist. R4 completes broker-firm-side persistence and full verdict routing behind those adapters. |

Decision records: [ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md)
and [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

## Audit / transcript ports

The audit surface is two ports: a structured decision-trail port and a
full-fidelity transcript port.

| Claim | Artefacts | Status |
|---|---|---|
| Every governed decision has a structured decision-trail record | `chorus/persistence/audit_port.py` (`AuditPortStore.list_decision_trail`), `contracts/audit/agent_invocation_record.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`decision_trail_entries`), `chorus/agent_runtime/runtime.py` (`record_decision`) | Implementation in code. |
| The transcript carries enough to replay an invocation | `chorus/persistence/audit_port.py`, `contracts/audit/agent_invocation_transcript.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql` (`agent_invocation_transcripts`), `chorus/agent_runtime/runtime.py` (`record_transcript`) | The transcript port records replay inputs. |
| Audit completeness: no LLM invocation or connector call is unattributed | `chorus/eval/invariants.py` (`assert_audit_completeness`), [`transformation/eval-reshape-directions.md`](transformation/eval-reshape-directions.md) | The invariant suite asserts it. |

Decision record: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

## Projection sink

The projection sink derives read models for inspection.

| Claim | Artefacts | Status |
|---|---|---|
| Domain events project into read models | `chorus/persistence/projection.py` (workflow + calendar projection), `chorus/persistence/redpanda.py`, `tests/persistence/test_redpanda_projection.py` | The projection port keeps the workflow + calendar surface. |
| The read surface is read-only | `chorus/bff/app.py` (per-port `PortReaders` dependency), `frontend/src/routes/` | Implementation in code. |
| Replaying the same events twice converges | `tests/persistence/test_redpanda_projection.py`, `chorus/eval/invariants.py` (`assert_projection_convergence`) | Implementation in code. |

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
| Eval runs over the audit ports, not in-test bookkeeping | `chorus/eval/invariants.py`, `chorus/eval/scenario_player.py`, `chorus/eval/fixtures/uc1_happy_path.json`, `chorus/eval/fixtures/uc1_validator_redraft.json`, `tests/eval/test_run.py` | Invariants assert over captured-run artefacts. |
| Cross-provider replay is a first-class eval mode | `chorus/eval/replay.py`, `chorus/eval/fixtures/transcripts/uc1_classifier_happy.json` | Recorded-replay exists today; live cross-provider replay lands in R4. |

Decision record: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md).

### Workflow durability

| Claim | Artefacts | Status |
|---|---|---|
| The workflow spine is durable and replay-stable | `chorus/workflows/spine.py` (`WorkflowSpine`, `WorkflowDefinition`, `WorkflowStepDefinition`), `chorus/workflows/uc1.py` (UC1 enquiry-qualification workflow), `tests/workflows/` | UC1 runs on the spine; UC2 and UC3 add workflow definitions alongside it. |

Decision records: [ADR 0017](../adrs/0017-langgraph-removed-from-agent-execution.md)
and [ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md).

## Active Backlog

The active R4 backlog and continuation handoff are in
[`transformation/r4-implementation-backlog.md`](transformation/r4-implementation-backlog.md).
