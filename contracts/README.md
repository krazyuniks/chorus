# Contracts

JSON Schema is the canonical source for cross-boundary contracts. Pydantic models are generated from the schemas; representative samples and generated-model drift are checked by `just contracts-check`.

The schemas are organised around the six named ports of the hexagon plus the eval contract surface (see ADR 0006 and the R3 checkpoint ledger):

- `intake/` — inbound channel adapters. `intake/uc1/` holds UC1 (UK personal-lines insurance broking) channel payloads; port-shared intake schemas sit at the port root.
- `llm_provider/` — LLM provider port: agent IO envelopes, the provider catalogue, and immutable model-route versions. R3 reshapes these into structured invocation arguments and a route catalogue (ADR 0018).
- `connector/` — Tool Gateway connector contracts: the `tool_call` and `gateway_verdict` envelopes plus per-tool argument schemas (email, calendar, ticket). `connector/uc1/` is reserved for UC1-specific tool payloads authored in R3 (ADR 0019).
- `audit/` — audit ports: the decision-trail record (`agent_invocation_record`) and the tool-action `audit_event`. R3 splits this into a structured decision-trail port and a full-fidelity transcript port (ADR 0019).
- `projection/` — domain event-stream contract (`workflow_event`) and read-model schemas.
- `observability/` — observability sink contracts. Empty in this revision; populated later in R3.
- `eval/` — eval fixture expectation schema. R3 reshapes the fixture surface into invariants plus one happy path per use case (ADR 0019).

Each contract has a sample in its port's `samples/` directory. Generated Pydantic models are committed under [`../chorus/contracts/generated/`](../chorus/contracts/generated/) and mirror the contract tree.

Useful commands:

- `just contracts-gen` — regenerate Pydantic models from every `*.schema.json` under `contracts/`.
- `just contracts-check` — validate schemas, validate samples, and fail on generated-model drift.
