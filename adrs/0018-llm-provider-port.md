---
type: adr
status: accepted
date: 2026-05-20
---

# ADR 0018 - LLM provider port

## Context

ADR 0004 established the Agent Runtime as the governance boundary for model
invocations. Phase 2A added a provider catalogue, immutable route-version
tables, and a provider-keyed model adapter registry. ADR 0017 removed
LangGraph from the agent execution path.

The transformation reset names the LLM provider as one of the six named ports
of the hexagon and the most consequential adapter surface in the project. The
thesis requires it to be provider-agnostic by construction: agent code cannot
reach a provider SDK outside the port's adapter, and a provider change must be
contained inside the adapter rather than rippling into domain code.

The pre-reset surface had the right intent but the wrong shape for the thesis.
The provider catalogue is governance metadata, not a call boundary; the
provider-keyed adapter registry implied a separate adapter per provider; and
the Phase 2A `commercial.example` provider was a disabled placeholder rather
than a real route.

## Decision

Establish the LLM provider port as a named port of the hexagon.

The adapter is the OpenAI Python SDK pointed at any OpenAI-compatible
chat-completions endpoint. The SDK is treated as a transport, not as a
commitment to OpenAI as a provider. Provider-specific code is contained inside
the adapter and exposed only as configuration: base URL, API key, model
identifier, and provider-specific parameters such as thinking-mode toggles and
tool-use schema variants.

The domain core calls the port with structured invocation arguments and
receives a structured invocation result. It never touches a provider SDK
directly.

The port maintains a route catalogue. Every captured invocation records, at
minimum, the route name, the provider identifier, the model identifier, the
model parameters used, and the adapter version.

| Route | Purpose | Provider and model |
|---|---|---|
| Dev | Day-to-day reasoning during local development. | DeepSeek V4-Flash with thinking-mode, on an OpenAI-compatible endpoint. |
| Demo / eval canonical | The canonical demo path and the canonical eval baseline. | OpenAI gpt-5.4-mini. |
| Replay | Re-targets any captured transcript against any route the catalogue knows. | Configurable via the route catalogue. |

The port enforces one invariant: no invocation leaves the port without a route
catalogue entry, an audit and transcript pair (see ADR 0019), and
contract-validated arguments.

## Consequences

- R3 implements the OpenAI-SDK adapter. The Phase 2A provider catalogue and
  route-version tables are reshaped into the route catalogue, which becomes
  the port's route-metadata layer rather than a separate abstraction.
- The Phase 2A `commercial.example` disabled-provider placeholder is retired.
  The dev and demo routes are real OpenAI-compatible endpoints.
- Provider neutrality is structural: adding a provider is a route catalogue
  entry plus endpoint configuration, not a code change.
- The route catalogue plus the transcript port make cross-provider replay
  addressable; ADR 0019 depends on this.
- The Agent Runtime governance role from ADR 0004 is retained as the
  domain-side caller of the port (see ADR 0017).
- Provider-side non-determinism that the route catalogue declares allowed is
  the only divergence replay tolerates; the catalogue is therefore part of the
  eval contract.

## Alternatives considered

### A provider-specific adapter per provider

Rejected as the default. Current and candidate providers expose
OpenAI-compatible chat-completions endpoints; one transport adapter plus
per-route configuration is simpler and is what provider-agnostic by
construction means in practice. A genuinely non-compatible provider can be
given its own adapter later behind the same port without changing the port.

### Keep the Phase 2A provider catalogue as the primary abstraction

Rejected. The catalogue is useful governance metadata, but it is not a port. A
port is a call boundary with an adapter and invariants. The catalogue becomes
the port's route-metadata layer, not the boundary itself.

### Adopt a vendor-neutral SDK or an LLM gateway library

Rejected. It adds a dependency to do what the OpenAI-compatible endpoint
convention already does. The thesis prefers a thin transport adapter the
project owns and can hold to the contract-first discipline directly.
