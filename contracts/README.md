# Contracts

JSON Schema is the canonical source for cross-boundary contracts. Pydantic models are generated from the schemas; representative samples and generated-model drift are checked by `just contracts-check`.

Subdirectories:

- `events/` — lead intake, support request intake, workflow events,
  decision-trail invocation records, and audit events.
- `agents/` — Lighthouse and Support Desk Triage agent request/result envelopes.
- `tools/` — tool-call request, gateway-verdict, email argument, and calendar
  and ticket argument contracts.
- `eval/` — eval fixture expectation schema for workflow path, outcome, governance, cost, latency, and contract assertions. It now recognises Phase 2D and `support_triage` as contract values only; no support eval fixture is implemented by this contract baseline.
- `governance/` — provider catalogue and immutable model-route version contracts for Phase 2 provider governance.

Lead intake is part of `events/` (the parsed email payload — see [ADR 0008](../adrs/0008-email-intake-via-mailpit.md) and [ADR 0006](../adrs/0006-json-schema-contracts.md)). Support request intake is contract-only for Phase 2D and carries only safe refs and bounded categories. Ticket argument contracts now back the 2D-02 local ticket desk Tool Gateway dispatch baseline for read/propose actions; `ticket.update_status` remains approval-required.

Each contract has a sample in its category's `samples/` directory. Generated Pydantic models are committed under [`../chorus/contracts/generated/`](../chorus/contracts/generated/).

Useful commands:

- `just contracts-gen` — regenerate Pydantic models from all `*.schema.json` files.
- `just contracts-check` — validate schemas, validate samples, and fail on generated-model drift.

See [implementation-plan.md](../docs/implementation-plan.md).
