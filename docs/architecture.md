---
type: project-doc
status: active
date: 2026-05-24
---

# Chorus - Architecture

## Purpose

This is the architecture reference for Chorus. It describes the hexagon, the
six named ports, the contract-first discipline, and the invariants each port
enforces.

The thesis statement this document elaborates is
[`transformation/engineering-thesis.md`](transformation/engineering-thesis.md);
that document and the rest of the reset bundle in
[`transformation/`](transformation/) are the architectural authority. For the
worked UC1 use case see [`product-brief.md`](product-brief.md) and
[`domain-model.md`](domain-model.md); for the modelled UC2 use case see
[`product-brief-uc2.md`](product-brief-uc2.md) and
[`domain-model-uc2.md`](domain-model-uc2.md). For how each use case exercises
the ports see [`r1-adapter-mapping.md`](r1-adapter-mapping.md).

This document describes the architecture the project carries today. R3
landed the named-port surface in code; the
[implementation status](#implementation-status) section at the end records
which checkpoints landed which pieces and what R4 picks up.

## The hexagon and the six named ports

A small fixed set of named ports separates the domain core from anything that
talks to the outside world or to a swappable subsystem. The domain core does
not know which adapter is active.

```mermaid
flowchart TB
    subgraph ADAPTERS_IN["Intake adapters"]
      IA["email-channel, web-form-channel,<br/>partner-portal-channel, synthetic-channel"]
    end

    subgraph CORE["Domain core - inside the hexagon"]
      WF["Workflow spine - durable, Temporal"]
      AR["Agent reasoning"]
      TG["Tool Gateway - connector authority"]
    end

    subgraph ADAPTERS_OUT["Adapters behind the swappable ports"]
      LLMA["LLM provider: OpenAI-SDK adapter"]
      CONNA["Connector: Tool Gateway adapter registry"]
      AUDA["Audit: decision-trail + transcript"]
      PROJA["Projection: read-only BFF"]
      OBSA["Observability: OTLP / Prometheus / Loki / Tempo"]
    end

    IA -->|Intake port| CORE
    CORE -->|LLM provider port| LLMA
    CORE -->|Connector port| CONNA
    CORE -->|Audit / transcript ports| AUDA
    CORE -->|Projection sink port| PROJA
    CORE -->|Observability sink port| OBSA
```

The adapter inventory behind each port, as defined by the R1 adapter mapping
and R4 product/domain artefacts. UC1 is the current runnable worked set, UC2 is
modelled for R4 implementation, and UC3 is confirmed pending its R4 product
brief and domain model.

| Port | UC1 adapters | UC2 adapters | UC3 adapters |
|---|---|---|---|
| Intake | email-channel, web-form-channel, partner-portal-channel, synthetic-channel | email-channel, corporate-intake-form, intermediary-referral-channel | web-form-channel, email-channel, introducer-referral-channel |
| LLM provider | OpenAI-SDK adapter; routes: DeepSeek V4-Flash (dev), gpt-5.4-mini (demo / eval) | same adapter and route shape | same adapter and route shape |
| Connector | sandbox-crm, sandbox-referral-inbox, sandbox-decline-ledger, sandbox-outbound-comms, sandbox-customer-profile, sandbox-product-catalogue | adds sandbox-conflict-check, sandbox-kyc-bo, sandbox-aml-record-store, sandbox-engagement-letter-store | adds sandbox-attitude-to-risk-profiler, sandbox-capacity-for-loss-tool, sandbox-suitability-report-store, sandbox-platform-research |
| Audit / transcript | decision-trail adapter, transcript adapter (Postgres-backed) | same | same |
| Projection sink | Postgres projection adapter; Redpanda event consumer feeding the read-only BFF | same | same |
| Observability sink | OTLP adapter; Prometheus / Loki / Tempo adapters; optional LLM observability sidecar adapter | same | same |

## Contract-first discipline at every port

Every payload crossing a port is validated against an explicit schema before
the domain core sees it and before any adapter accepts it. Contracts are the
source of truth for shape, not the implementation. An adapter that violates the
contract fails at the boundary, with a contract violation, rather than
surfacing later as a wrong decision deep in business logic.

Contracts are JSON Schema. Generated models, representative samples, and a
drift gate move with every schema change. R3 rewrites the contract set around
the six named ports, with use-case-specific payload schemas at the intake and
connector ports.

## Workflow durability is not a port

Workflow durability is internal to the domain core. The workflow shape - the
ordered sequence of intake, classification, context gathering, a proposed
action, approval where the regulator demands it, routing, and closure - is the
domain's operational backbone, and it does not vary per use case. Temporal is
the workflow engine; the Temporal integration is held to the same adapter
discipline as anything else, but the architectural thesis is not "Temporal
everywhere". It is the named-port surface. The workflow spine, the agent
reasoning paths, and the Tool Gateway authority logic all sit on the domain
side of the hexagon.

## The intake port

The intake port receives inbound business work. Each channel adapter
contract-validates its inbound payload and normalises it to a domain-side
record, with the channel preserved as provenance.

| Aspect | Detail |
|---|---|
| Role | Inbound business work entering the system. |
| Adapter contract shape | A per-channel inbound payload schema (for UC1: `EmailEnquiry`, `WebFormEnquiry`, `PartnerPortalSubmission`), each normalised to a single domain-side record. |
| Adapter inventory | UC1: email-channel, web-form-channel, partner-portal-channel, plus a synthetic-channel that injects authored fixtures through the same path. UC2 and UC3 swap the channel set; the port does not change. |
| Invariants | Every inbound payload validates against its channel contract before the domain core accepts it. Each channel adapter carries a channel-specific idempotency key, and the port maps that key to one domain work identifier. |

## The LLM provider port

The LLM provider port carries model invocations. It is the most consequential
adapter surface in the project and must be provider-agnostic by construction.
The domain core calls the port with structured invocation arguments and
receives a structured invocation result; it never talks to a provider directly.

| Aspect | Detail |
|---|---|
| Role | Model invocations, with a route catalogue and provider neutrality. |
| Adapter contract shape | A structured invocation-argument schema and a structured invocation-result schema, plus a route-catalogue-entry recorded on every call. |
| Adapter inventory | One adapter: the OpenAI Python SDK against any OpenAI-compatible chat-completions endpoint, configured per route. |
| Invariants | No invocation leaves the port without a route catalogue entry, an audit and transcript pair, and contract-validated arguments. Agent code cannot reach a provider SDK outside the adapter. |

The adapter is the OpenAI Python SDK treated as a transport, not as a
commitment to OpenAI as a provider. Provider-specific code is contained inside
the adapter and exposed only as configuration: base URL, API key, model
identifier, and provider-specific parameters such as thinking-mode toggles and
tool-use schema variants.

### The route catalogue

The route catalogue is the LLM provider port's metadata layer. Every captured
invocation records, at minimum, the route name, the provider identifier, the
model identifier, the model parameters used, and the adapter version.

| Route | Purpose | Provider and model |
|---|---|---|
| Dev | Day-to-day reasoning during local development. | DeepSeek V4-Flash with thinking-mode, on an OpenAI-compatible endpoint. |
| Demo / eval canonical | The canonical demo path and the canonical eval baseline. | OpenAI gpt-5.4-mini. |
| Replay | Re-targets any captured transcript against any route the catalogue knows. | Configurable via the route catalogue. |

The route catalogue plus the transcript port together make cross-provider
replay possible. Without route metadata, replay can only target the original
provider; with it, replay can target any other provider the catalogue knows
how to address.

## The connector port

The connector port is the system's external-action authority. Every connector
call is mediated; the domain core proposes an action, and the port decides
whether and how it happens.

| Aspect | Detail |
|---|---|
| Role | External-action authority. |
| Adapter contract shape | A per-tool argument schema and return schema, plus the gateway verdict schema. Each connector adapter declares the tool names and contracts it satisfies. |
| Adapter inventory | UC1: sandbox-crm, sandbox-referral-inbox, sandbox-decline-ledger, sandbox-outbound-comms, sandbox-customer-profile, sandbox-product-catalogue. UC2 and UC3 register their own connector adapters. All are local sandbox implementations during the local POC. |
| Invariants | No tool call leaves the port without a grant check, a mode decision, an argument validation, a verdict, and an audit record. Workflow code cannot reach past the connector port; there is no back channel to a side service. |

### The Tool Gateway

The Tool Gateway is the connector port's authority layer. Its call path is:
validate the grant, validate the arguments, apply the mode, dispatch to the
right adapter, capture audit, return a verdict.

- **Adapter registry.** Each connector adapter declares its supported tool
  names plus the argument and return contracts it satisfies, and registers
  with the gateway. Dispatch is a registry lookup. New connector adapters do
  not edit the gateway. See
  [`transformation/code-refactor-directions.md`](transformation/code-refactor-directions.md).
- **Grants.** The agent's policy snapshot declares which connector adapters
  the agent may call and in which modes.
- **Modes.** A call runs in dry-run mode or effect mode. Replay through the
  connector port uses dry-run so captured replays do not duplicate side
  effects.
- **Idempotency.** Each call carries an idempotency key; a repeat returns the
  recorded result without re-invoking the connector.
- **Approval hooks.** A call that the policy snapshot gates is held for human
  approval before it reaches effect mode.
- **Redaction.** Audited arguments are redacted per the policy snapshot.
- **Verdict capture.** Every call produces an explicit verdict, recorded to
  the audit ports.

The gateway separates two responsibilities: routing a call to the right
adapter (the registry concern) and enforcing policy on that call (the gateway's
actual value). Those must not be entangled.

## The audit and transcript ports

A single audit stream cannot serve both compliance and engineering without
distorting one of them. Chorus splits the audit surface into two ports.

### The structured decision-trail port

| Aspect | Detail |
|---|---|
| Role | The compliance record: who decided what, under which policy, on what input, with what output. |
| Adapter contract shape | A structured decision-trail record schema: workflow correlation references, agent identity and version, policy snapshot reference, input and output summaries, tool calls in summary form, timestamps, cost. |
| Adapter inventory | A Postgres-backed decision-trail adapter. |
| Invariants | Every governed decision has exactly one decision-trail record. No decision is unattributed. |

The decision-trail port is structured, queryable, and stable. It is what a
regulator or a control-framework reviewer reads.

### The full-fidelity transcript port

| Aspect | Detail |
|---|---|
| Role | The engineering record: what exactly the model saw and what it returned. |
| Adapter contract shape | A transcript record schema: full message sequence, full tool-call and tool-result sequence, full response body, route catalogue entry, model parameters as called, provider-side metadata, token counts. |
| Adapter inventory | A Postgres-backed transcript adapter. Storage could split later without changing the port. |
| Invariants | The transcript for every governed decision carries enough metadata to be replayed against an alternate provider through the LLM provider port. |

The transcript port is dense and large and is not queried directly for
compliance. Its job is to make the invocation replayable.

### Replay as eval substrate

The transcript port stores enough about every captured invocation to replay
that invocation against an alternate provider and model. That property is the
project's eval substrate, not an incidental capability.

A captured transcript can be loaded, re-routed through the LLM provider port
against a different provider and model, and compared to the original on
contract validity, decision agreement under the same policy snapshot,
tool-call divergence, response-shape divergence, and cost and latency deltas.
Cross-provider replay is a first-class eval mode, not a research afterthought.
It bounds the standard objection to a provider-agnostic architecture -
hallucination and quality risk on cheaper providers - because the divergence
is observable on real, in-domain invocations, and the same data structure that
proves accountability proves model quality. The full eval reshape is in
[`transformation/eval-reshape-directions.md`](transformation/eval-reshape-directions.md).

## The projection sink port

| Aspect | Detail |
|---|---|
| Role | Derives read models for inspection. |
| Adapter contract shape | Domain event schemas on the event stream; per-use-case read-model schemas. |
| Adapter inventory | A Postgres projection adapter feeding the read-only BFF; a Redpanda event consumer that drives the derivation. |
| Invariants | Replaying the same event stream twice produces the same read-model state. The sink is read-only; there is no write path back through it. |

## The observability sink port

| Aspect | Detail |
|---|---|
| Role | Traces, metrics, logs, and optional LLM observability. |
| Adapter contract shape | A trace, metric, and log envelope with stable correlation identifiers, and safe-attribute rules. |
| Adapter inventory | OTLP, Prometheus, Loki, and Tempo adapters; an optional LLM observability sidecar adapter configured per route. |
| Invariants | Every workflow run emits the expected trace, metric, and log envelope with stable correlation identifiers. Where the LLM observability sidecar is enabled, the transcript port stays authoritative. No secrets, credentials, raw sensitive content, or PII reach span attributes, baggage, or dashboard labels. |

## Cross-cutting concerns

### Contracts

Contracts are the discipline that holds the port surface together. They are
JSON Schema, with generated models, representative samples, and a drift gate.
A contract change moves the schema, the generated model, the sample, and any
consuming code in one piece of work.

### Observability and correlation

Every material operation carries a correlation identifier. The decision-trail
and transcript ports answer accountability questions; the observability sink
answers operational questions. The two are kept separate: audit is the
accountability record, telemetry is for diagnosis, and the join between them
is a correlation identifier, not shared storage.

### The audit completeness invariant

For every workflow run, the decision-trail port and the transcript port
between them cover every LLM invocation and every connector call. Neither port
has gaps. This invariant is what makes the audit surface trustworthy as an eval
substrate: a replay-eval that runs over the transcript port is only as
complete as the transcript port itself.

## Constraints the thesis imposes

The thesis is meant to do work. It constrains downstream decisions:

- Workflow code cannot reach past the connector port. There is no back channel
  to a side service.
- Agent code cannot reach past the LLM provider port. There is no direct
  provider SDK use outside the adapter.
- Tool calls cannot leave the connector port without a verdict, a grant check,
  a contract validation, and an audit record.
- LLM invocations cannot leave the LLM provider port without a route catalogue
  entry, an audit and transcript pair, and contract-validated arguments.
- Eval cannot bypass the audit ports. The transcript port is the eval
  substrate.

That is what makes the architecture a thesis rather than a vocabulary.

## Implementation status

The runtime code carries the named-port surface this document describes.

| Surface | Where in code |
|---|---|
| Six-port contract layout | `contracts/intake/`, `contracts/llm_provider/`, `contracts/connector/`, `contracts/audit/`, `contracts/projection/`, `contracts/observability/`, `contracts/eval/`; use-case-specific contracts live under `uc1/`, `uc2/`, and `uc3/` subdirectories as they are added. |
| LLM provider port | `chorus/llm_provider/port.py` (surface), `chorus/llm_provider/adapter_openai.py` (OpenAI-SDK transport), `chorus/llm_provider/adapter_replay.py` (deterministic recorded-replay substrate), `chorus/llm_provider/route_catalogue.py` (route metadata). |
| Audit / transcript port split | `chorus/persistence/audit_port.py`, `contracts/audit/agent_invocation_record.schema.json`, `contracts/audit/agent_invocation_transcript.schema.json`, `infrastructure/postgres/migrations/001_current_state_baseline.sql`. The runtime writes both records on every invocation. |
| Connector adapter registry | `chorus/connectors/types.py` (`ConnectorAdapter`, `ConnectorRegistry`, `ToolSpec`), `chorus/connectors/uc1.py` (six UC1 sandbox adapters), `chorus/connectors/calendar.py`. The gateway dispatches through the registry. |
| Workflow spine + UC1 on the spine | `chorus/workflows/spine.py` (`WorkflowSpine`, `WorkflowDefinition`, `WorkflowStepDefinition` over generic activity names), `chorus/workflows/uc1.py` (UC1 enquiry-qualification workflow). |
| Per-port persistence read surface | `chorus/persistence/projection.py` (workflow + calendar), `chorus/persistence/audit_port.py`, `chorus/persistence/runtime_policy.py`, `chorus/persistence/provider_governance.py`. The BFF binds them through `PortReaders` per request. |
| Per-port doctor probes | `chorus/doctor/scaffold.py` (paths / executables / compose), `chorus/doctor/projection_port.py`, `chorus/doctor/connector_port.py`, `chorus/doctor/observability_port.py`, `chorus/doctor/workflow_runtime.py`, `chorus/doctor/ui.py`. CLI entry at `chorus/doctor/__main__.py`. |
| Invariant-plus-replay eval | `chorus/eval/invariants.py` (the UC1 invariant suite), `chorus/eval/scenario_player.py` (drives the recorded-replay route through a fixture's scenario), `chorus/eval/replay.py` (`eval replay` subcommand), `chorus/eval/run.py` (CLI). |

The ADRs that govern the named-port surface are
[ADR 0017](../adrs/0017-langgraph-removed-from-agent-execution.md)
(agent execution without LangGraph),
[ADR 0018](../adrs/0018-llm-provider-port.md) (LLM provider port),
[ADR 0019](../adrs/0019-audit-ports-and-replay-eval.md) (audit ports and
replay-eval), and
[ADR 0020](../adrs/0020-domain-refocus-uk-regulated-use-cases.md) (UK-regulated
use cases).

R4 (local POC readiness across UC1, UC2, and UC3 with cross-provider
replay-eval) is the next phase. It wires the UC2 and UC3 workflow
definitions alongside UC1 on the same spine, stands up the OpenAI-SDK
adapter against gpt-5.4-mini (canonical demo / eval) and DeepSeek V4-Flash
(dev), and runs the cross-provider replay-eval ADR 0019 names as a
first-class mode. The active R4 backlog and continuation handoff are in
[`transformation/r4-implementation-backlog.md`](transformation/r4-implementation-backlog.md).
