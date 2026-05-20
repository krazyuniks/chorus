---
type: project-doc
status: active
date: 2026-05-20
---

# Chorus - Evidence Map

## Purpose

This document maps Chorus's engineering claims to the artefacts that support
them, organised by named port. It is the navigation aid for a reviewer who
wants to move from a claim to the code, contract, test, or decision record
behind it.

The map describes two kinds of evidence and keeps them distinct:

- **Design evidence** - the reset bundle, the R1 product and domain artefacts,
  and this R2 documentation set. This is complete for UC1 and confirmed for
  UC2 and UC3.
- **Implementation evidence** - the runtime code. The code in the repository
  is the pre-reset implementation. It exercises all six ports, but it does not
  yet carry the named-port surface or the UC1 adapter inventory; R3 lands that
  refactor and R4 wires the three use cases. Status columns below say so
  honestly.

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
| Inbound work enters through a contract-validated channel adapter | `chorus/workflows/mailpit.py`, `chorus/workflows/intake.py`, `contracts/events/`, `tests/workflows/test_mailpit_intake.py` | Pre-reset implementation present (Mailpit email channel); named-port surface and the UC1 channel adapters pending R3. |
| Channel-specific idempotency maps to one work identifier | `chorus/workflows/mailpit.py` (Message-ID dedupe, stable workflow ID) | Pre-reset implementation present. |
| UC1 intake shape is fully specified | [`product-brief.md`](product-brief.md), [`domain-model.md`](domain-model.md), [`r1-adapter-mapping.md`](r1-adapter-mapping.md) | Design complete. |

Decision records: [ADR 0008](../adrs/0008-email-intake-via-mailpit.md).

## LLM provider port

The LLM provider port carries model invocations and must be provider-agnostic
by construction.

| Claim | Artefacts | Status |
|---|---|---|
| Reasoning runs behind a provider boundary, not a direct SDK call | `chorus/agent_runtime/runtime.py`, `contracts/agents/`, `tests/agent_runtime/test_runtime.py` | Pre-reset implementation present. The pre-reset code routes reasoning through a LangGraph executor; R3 removes LangGraph and the OpenAI-SDK adapter takes its place. |
| Every invocation records provider and model metadata | `contracts/governance/` (provider catalogue, immutable route versions), `infrastructure/postgres/migrations/005_provider_governance_catalogue.sql` | Pre-reset implementation present; the route catalogue shape is rewritten in R3. |
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
| Every connector call passes grant, mode, argument validation, verdict, and audit | `chorus/tool_gateway/gateway.py`, `contracts/tools/`, `tests/tool_gateway/test_gateway.py` | Pre-reset implementation present. |
| Connectors are real software in sandbox or local mode, not mocks | `chorus/connectors/local.py`, `chorus/connectors/calendar.py`, `chorus/connectors/ticket.py` | Pre-reset implementation present. |
| Dispatch is an adapter registry, not a hardcoded match block | `chorus/tool_gateway/gateway.py`, [`transformation/code-refactor-directions.md`](transformation/code-refactor-directions.md) (Smell 2) | Pending R3. The pre-reset code uses a hardcoded match block. |
| UC1 connector inventory is specified | [`r1-adapter-mapping.md`](r1-adapter-mapping.md) | Design complete. |

Decision records: [ADR 0004](../adrs/0004-agent-runtime-and-tool-gateway.md),
[ADR 0014](../adrs/0014-connector-expansion-approval-hardening-scope.md).

## Audit / transcript ports

The audit surface is two ports: a structured decision-trail port and a
full-fidelity transcript port.

| Claim | Artefacts | Status |
|---|---|---|
| Every governed decision has a structured decision-trail record | `infrastructure/postgres/migrations/001_phase_1a_persistence_foundation.sql` (`decision_trail_entries`, `tool_action_audit`), `chorus/agent_runtime/runtime.py` | Pre-reset implementation present as a single audit store. |
| The transcript carries enough to replay an invocation | [`transformation/engineering-thesis.md`](transformation/engineering-thesis.md) (transcript port section) | Design complete. The single audit store splits into the decision-trail and transcript ports in R3. |
| Audit completeness: no LLM invocation or connector call is unattributed | [`transformation/eval-reshape-directions.md`](transformation/eval-reshape-directions.md) (audit completeness invariant) | Design complete; invariant-based eval enforces it in R3 and R4. |

Decision records: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md)
(audit ports and replay-eval),
[ADR 0005](../adrs/0005-postgres-first-storage.md).

## Projection sink

The projection sink derives read models for inspection.

| Claim | Artefacts | Status |
|---|---|---|
| Domain events project into read models | `chorus/persistence/projection.py`, `chorus/persistence/redpanda.py`, `tests/persistence/test_redpanda_projection.py` | Pre-reset implementation present; `projection.py` is decomposed along port boundaries in R3. |
| The read surface is read-only | `chorus/bff/app.py`, `frontend/src/routes/` | Pre-reset implementation present. |
| Replaying the same events twice converges | `tests/persistence/test_redpanda_projection.py` | Pre-reset implementation present (idempotent projection). |

Decision records: [ADR 0003](../adrs/0003-redpanda-event-visibility.md),
[ADR 0005](../adrs/0005-postgres-first-storage.md).

## Observability sink

The observability sink carries traces, metrics, logs, and optional LLM
observability.

| Claim | Artefacts | Status |
|---|---|---|
| Traces, metrics, and logs flow through one pipeline | `chorus/observability/`, `compose.yml` (OTel collector, Tempo, Loki, Prometheus, Grafana), `infrastructure/grafana/` | Pre-reset implementation present. |
| Operational surfaces correlate by one identifier | `chorus/observability/` (`set_current_span_attributes`, `current_otel_ids`), `runbook.md` | Pre-reset implementation present. |
| Audit and telemetry stay separate | [`architecture.md`](architecture.md) (cross-cutting concerns) | Design complete. |

Decision records: [ADR 0010](../adrs/0010-observability-pipeline.md).

## Cross-cutting

### Contracts

| Claim | Artefacts | Status |
|---|---|---|
| Cross-port payloads are JSON Schema with a drift gate | `contracts/`, `chorus/contracts/generated/`, `chorus/contracts/check.py` | Pre-reset implementation present; the contract set is rewritten around the six ports in R3. |

Decision records: [ADR 0006](../adrs/0006-json-schema-contracts.md).

### Replay as eval substrate

| Claim | Artefacts | Status |
|---|---|---|
| Eval runs over the audit ports, not in-test bookkeeping | `chorus/eval/run.py`, `chorus/eval/fixtures/`, `tests/eval/test_run.py` | Pre-reset implementation present as path-enumeration fixtures. |
| Eval moves to invariant-based shape plus cross-provider replay | [`transformation/eval-reshape-directions.md`](transformation/eval-reshape-directions.md) | Design complete; implemented in R3 and R4. |

Decision records: [ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md)
(audit ports and replay-eval),
[ADR 0007](../adrs/0007-trace-evaluation-harness.md).

### Workflow durability

| Claim | Artefacts | Status |
|---|---|---|
| The workflow spine is durable and replay-stable | `chorus/workflows/`, `tests/workflows/` | Pre-reset implementation present; the Lighthouse and Support Triage duplication is factored to a shared spine in R3. |

Decision records: [ADR 0002](../adrs/0002-temporal-durable-orchestration.md).

## Pre-reset evidence

The chronological phase ledger (Phase 0 through Phase 2E) is not reproduced in
this map. It is preserved in
[`transformation/phase-2-archive.md`](transformation/phase-2-archive.md). The
disposition of each pre-reset component - preserved, reframed, or retired - is
recorded in
[`transformation/current-state-inventory.md`](transformation/current-state-inventory.md)
and [`r1-exit-criteria.md`](r1-exit-criteria.md).
