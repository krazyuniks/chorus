# Contracts

JSON Schema is the canonical source for cross-boundary contracts. Pydantic models are generated from the schemas during build; samples are validated and drift-checked in CI.

Subdirectories:

- `events/` — workflow events published to Redpanda (intake, transitions, completions, escalations).
- `agents/` — agent input/output contracts (per agent role: intake, research, draft, validation).
- `tools/` — tool call argument schemas and gateway verdict shape.
- `eval/` — eval fixture expectation schemas (path, outcome, governance, cost, latency, contract assertions).

Lead intake is part of `events/` (the parsed email payload — see [ADR 0008](../adrs/0008-email-intake-via-mailpit.md) and [ADR 0006](../adrs/0006-json-schema-contracts.md)).

Schema drafts land here in Phase 0; generated Pydantic models and drift-check CI follow in Phase 1A.

See [implementation-plan.md](../docs/implementation-plan.md).
