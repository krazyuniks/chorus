---
type: adr
status: accepted
date: 2026-05-20
---

# ADR 0018 - LLM Provider Port

## Decision

The LLM provider is a named port of the hexagon. Domain code calls the port
with structured invocation arguments and receives a structured invocation
result. Domain code never imports or calls a provider SDK directly.

The default transport adapter is the OpenAI Python SDK pointed at
OpenAI-compatible chat-completions endpoints. Provider-specific details are
configuration: base URL, API key environment variable, model identifier, and
route parameters.

The port maintains a route catalogue. Every invocation records the route ID,
provider identifier, model identifier, parameters, adapter version, and
correlation metadata needed by the audit and transcript ports.

## Route Classes

| Route | Purpose |
|---|---|
| Recorded replay | Offline deterministic eval and fixture replay. |
| Dev | Day-to-day local reasoning once credentials are present. |
| Demo / eval canonical | Canonical live-provider baseline once credentials are present. |
| Alternate replay | Re-targets a captured transcript against another configured route. |

## Consequences

- Provider neutrality is structural: adding an OpenAI-compatible provider is a
  route-catalogue and configuration change, not a domain-code change.
- Live-provider R4 work must align route catalogue entries, DB route policy,
  immutable route-version evidence, provider catalogue rows, BFF views, and
  eval route selection.
- Cross-provider replay depends on transcript records carrying route,
  provider, model, parameter, and adapter metadata.

## Constraints

- No invocation leaves the port without a route catalogue entry.
- No provider SDK use is allowed outside this port.
- Live routes must enforce task-specific structured output before they can be
  used as R4 evidence.
