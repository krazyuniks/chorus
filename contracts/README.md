# Contracts

JSON Schema is the canonical source for cross-boundary contracts. Pydantic models are generated from the schemas; representative samples and generated-model drift are checked by `just contracts-check`.

The schemas are organised around the six named ports of the hexagon plus the eval contract surface:

- `intake/` — inbound channel adapters. `intake/uc1/` holds UC1 (UK personal-lines insurance broking) channel payloads; port-shared intake schemas sit at the port root.
- `llm_provider/` — LLM provider port: agent IO envelopes, the provider catalogue, immutable model-route versions, and route metadata (ADR 0018).
- `connector/` — Tool Gateway connector contracts: the `tool_call` and `gateway_verdict` envelopes plus per-tool argument schemas. `connector/uc1/` holds UC1-specific tool payloads.
- `audit/` — audit ports: the decision-trail record (`agent_invocation_record`), the full-fidelity transcript, and the tool-action `audit_event` (ADR 0019).
- `projection/` — domain event-stream contract (`workflow_event`) and read-model schemas. The shared workflow event contract admits the declared UC1, UC2, and UC3 workflow families and their safe root-subject refs; use-case-specific payload breadth lands in later slices.
- `observability/` — observability sink contracts.
- `eval/` — eval fixture expectation schema for invariants plus use-case scenarios (ADR 0019).

Each contract has a sample in its port's `samples/` directory. Generated Pydantic models are committed under [`../chorus/contracts/generated/`](../chorus/contracts/generated/) and mirror the contract tree.

Useful commands:

- `just contracts-gen` — regenerate Pydantic models from every `*.schema.json` under `contracts/`.
- `just contracts-check` — validate schemas, validate samples, and fail on generated-model drift.
