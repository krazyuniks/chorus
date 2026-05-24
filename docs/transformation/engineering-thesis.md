---
type: project-doc
status: active
date: 2026-05-24
---

# Engineering Thesis

Chorus is a **hexagonal, ports-and-adapters exemplar for governed agentic
systems with data-contract-first design at every port**.

This document is the long-form thesis statement. Other design-control docs
derive from it.

## The Two Commitments

1. **Ports and adapters as the load-bearing structure.** A small fixed set
   of named ports separates the domain core from anything that talks to
   the outside world or to a swappable subsystem. The domain core does
   not know which adapter is active. The workflow code, the agent
   reasoning paths, and the tool authority logic all live on the domain
   side of the hexagon. Providers, transports, sandboxes, audit stores,
   and observability backends live on the adapter side.
2. **Contract-first at every port.** Every payload crossing a port is
   validated against an explicit schema before the domain core sees it
   and before any adapter accepts it. Contracts are the source of truth
   for shape. Adapters that violate the contract fail at the boundary,
   not deep in business logic.

The point of the thesis is not "Chorus has a clean architecture". The
point is that governed agentic systems benefit specifically from this
shape, because agents amplify the cost of every leaky boundary: a
provider quirk, a transport-level type drift, or a connector that
mutates outside its grant becomes hard to detect and harder to undo when
reasoning sits between input and effect.

## The Named Ports

The hexagon has six named ports. The list is intentionally short.

| Port | Role | What sits behind it |
|---|---|---|
| **Intake** | Inbound business work entering the system. | Email channel adapter, broker portal adapter, web form adapter, synthetic fixture adapter. |
| **LLM provider** | Model invocations with route catalogue and provider neutrality. | OpenAI Python SDK against any OpenAI-compatible endpoint (DeepSeek `deepseek-v4-flash` dev, OpenAI `gpt-5.4-mini-2026-03-17` demo / eval, local recorded replay). |
| **Connector** | External-action authority via the Tool Gateway. | UC1 broker-firm adapters, calendar, outbound communications, and use-case-specific connector adapters; sandbox adapters during local POC. |
| **Audit / transcript** | Two streams: structured decision-trail port and full-fidelity transcript port. | Postgres-backed decision-trail adapter and transcript adapter (could split storage later). |
| **Projection sink** | Derives read models for inspection. | Postgres projection adapter feeding the read-only BFF; Redpanda event consumer for derivation. |
| **Observability sink** | Traces, metrics, logs, optional LLM observability. | OTLP adapter, Prometheus / Loki / Tempo adapters, optional LLM observability sidecar adapter. |

Workflow durability (Temporal) is not a port. It is internal to the
domain core, in the sense that the workflow shape is the domain's
operational backbone. The Temporal adapter for workflow execution is
abstracted under the same discipline, but the architectural thesis is
not "Temporal everywhere"; it is the named-port surface above.

## The LLM Provider Port

The LLM provider port is the most consequential adapter surface in the
project. It must be provider-agnostic by construction.

### Adapter

The adapter is the **OpenAI Python SDK** pointed at any
OpenAI-compatible chat-completions endpoint. The SDK is treated as a
transport, not as a commitment to OpenAI as a provider.

Provider-specific code is contained inside the adapter and exposed
only as configuration:

- base URL;
- API key;
- model identifier;
- provider-specific parameters (thinking-mode toggles, response-format
  options, tool-use schema variants).

The domain code calls the port with structured invocation arguments
and receives a structured invocation result. It never talks to a
provider directly.

### Routes

| Route | Purpose | Provider | Model |
|---|---|---|---|
| Dev | Day-to-day reasoning during local development. | DeepSeek (OpenAI-compatible endpoint) | `deepseek-v4-flash` with thinking mode enabled for reasoning steps. |
| Demo / eval canonical | Canonical demo path and the canonical eval baseline. | OpenAI | `gpt-5.4-mini-2026-03-17` pinned snapshot. |
| Replay (any) | Any provider plus model recorded in a captured transcript can be re-targeted for cross-provider replay eval. | Configurable via route catalogue. | Configurable via route catalogue. |

### Route Catalogue

The LLM provider port maintains a route catalogue. Every captured
invocation records, at minimum:

- route name;
- provider identifier;
- model identifier;
- model parameters used;
- adapter version.

The route catalogue plus the transcript port together make
cross-provider replay possible. Without route metadata, replay can only
target the original provider; with it, replay can target any other
provider that the catalogue knows how to address.

## The Two Audit Ports

A single audit stream cannot serve both compliance and engineering
without distorting one of them. Chorus splits the audit surface into two
ports.

### Structured Decision-Trail Port

This port answers the compliance question: who decided what, under
which policy, on what input, with what output.

Records carry:

- workflow correlation refs;
- agent identity and version;
- policy snapshot reference (route, prompts, grants, modes);
- input summary;
- output summary and justification;
- tool calls in summary form;
- timestamps and cost.

It is structured, queryable, and stable. It is what a regulator or a
control-framework reviewer reads.

### Full-Fidelity Transcript Port

This port answers the engineering question: what exactly did the model
see, and what did it return.

Records carry:

- the full message sequence sent to the LLM provider;
- the full tool-call and tool-result sequence;
- the full response body;
- the route catalogue entry that selected the provider and model;
- model parameters as called;
- provider-side metadata if exposed;
- input and output token counts where the provider reports them.

It is dense, large, and not queried directly for compliance. Its job is
to make the invocation **replayable**.

## Replay As Eval Substrate

The transcript port stores enough about every captured invocation that
the same invocation can be replayed against an alternate provider or
model. That property is not an incidental capability. It is the project's
eval substrate.

### What Replay Means Here

A captured transcript can be loaded, re-routed through the LLM provider
port against a different provider plus model combination, and compared
to the original. The comparison can be:

- output equality on tool calls and final response shape;
- contract validity (does the replay still satisfy the same schemas?);
- decision agreement under the same policy snapshot;
- cost and latency delta;
- downstream effect equivalence if the replay is taken back through the
  connector port in dry-run mode.

### Why That Property Matters

Hallucination and quality risk on cheaper providers is the standard
objection to a provider-agnostic architecture. Replay-as-eval bounds
that risk structurally:

- hallucinations are captured in the transcript;
- the same input can be re-run on a canonical model
  (`gpt-5.4-mini-2026-03-17`);
- the divergence is observable on real, in-domain invocations rather
  than synthetic benchmarks;
- the same data structure that proves accountability proves model
  quality, on the same traffic, at the same level of detail.

### Cross-Provider Replay As A First-Class Eval Mode

Cross-provider replay is not a research afterthought. It is one of the
eval shapes Chorus must support:

```
eval replay --provider <name> --model <id> --invocation-id <uuid>
```

The eval suite must be able to take any captured transcript and re-run
it against any route the catalogue knows, then report:

- contract validity of the replayed invocation;
- decision agreement against the original;
- structural divergence in tool calls;
- cost and latency deltas.

Operational consequences for the rest of the architecture follow:

- the transcript port has to capture enough metadata to support replay
  (route + model + parameters + full message and tool-call history);
- the connector port has to support dry-run mode on captured replays so
  side effects do not duplicate;
- the contract layer has to validate the replay as strictly as the
  original;
- the eval harness has to treat replay as a normal eval shape, not a
  separate code path.

## How The Thesis Constrains The Rest Of The Project

The thesis is meant to do work. It constrains downstream decisions:

- Workflow code cannot reach past the connector port. There is no
  back-channel to a side service.
- Agent code cannot reach past the LLM provider port. There is no
  direct provider SDK use outside the adapter.
- Tool calls cannot leave the connector port without a verdict, a
  grant check, a contract validation, and an audit record.
- LLM invocations cannot leave the LLM provider port without a route
  catalogue entry, an audit / transcript pair, and contract-validated
  arguments.
- Eval cannot bypass the audit ports. The transcript port is the eval
  substrate.

That is what makes the architecture a thesis rather than a vocabulary.

## Current Decision Records

The matching current ADRs are:

- [ADR 0017](../../adrs/0017-langgraph-removed-from-agent-execution.md)
- [ADR 0018](../../adrs/0018-llm-provider-port.md)
- [ADR 0019](../../adrs/0019-audit-ports-and-replay-eval.md)
- [ADR 0020](../../adrs/0020-domain-refocus-uk-regulated-use-cases.md)
