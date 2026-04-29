# Contracts

JSON Schema is the canonical source for cross-boundary contracts. Pydantic models are generated from the schemas; representative samples and generated-model drift are checked by `just contracts-check`.

Subdirectories:

- `events/` — lead intake, workflow events, decision-trail invocation records, and audit events.
- `agents/` — Lighthouse agent request/result envelope.
- `tools/` — tool-call request and gateway-verdict contracts.
- `eval/` — eval fixture expectation schema for workflow path, outcome, governance, cost, latency, and contract assertions.

Lead intake is part of `events/` (the parsed email payload — see [ADR 0008](../adrs/0008-email-intake-via-mailpit.md) and [ADR 0006](../adrs/0006-json-schema-contracts.md)).

Each contract has a sample in its category's `samples/` directory. Generated Pydantic models are committed under [`../chorus/contracts/generated/`](../chorus/contracts/generated/).

Useful commands:

- `just contracts-gen` — regenerate Pydantic models from all `*.schema.json` files.
- `just contracts-check` — validate schemas, validate samples, and fail on generated-model drift.

See [implementation-plan.md](../docs/implementation-plan.md).
