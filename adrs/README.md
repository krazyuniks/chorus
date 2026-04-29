# Architecture Decision Record

This directory is the durable decision record for Chorus. ADRs capture material
architectural choices, rejected alternatives, and consequences. The current
architecture is described in [`../docs/architecture.md`](../docs/architecture.md).

| ADR | Decision |
|---|---|
| [0001](0001-evidence-first-scope-and-lighthouse.md) | Evidence-first scope and Lighthouse vertical slice. |
| [0002](0002-temporal-durable-orchestration.md) | Temporal as durable orchestration spine. |
| [0003](0003-redpanda-event-visibility.md) | Redpanda for event visibility and async projections. |
| [0004](0004-agent-runtime-and-tool-gateway.md) | Agent Runtime and Tool Gateway boundaries. |
| [0005](0005-postgres-first-storage.md) | Postgres-first storage with deferred Scylla option. |
| [0006](0006-json-schema-contracts.md) | JSON Schema canonical contracts and generated Pydantic models. |
| [0007](0007-trace-evaluation-harness.md) | Trace/evaluation harness as Phase 1 requirement. |
| [0008](0008-email-intake-via-mailpit.md) | Email intake via Mailpit. |
| [0009](0009-local-only-operating-model.md) | Local-only operating model for Phase 1 (proposed). |
| [0010](0010-observability-pipeline.md) | Observability pipeline shape — OTel + Tempo/Loki/Prometheus + audit join (proposed). |
