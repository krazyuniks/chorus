# Architecture Decision Record

This directory is the durable decision record for Chorus. ADRs capture material
architectural choices, rejected alternatives, and consequences. The current
architecture is described in [`../docs/architecture.md`](../docs/architecture.md).

ADRs 0001 to 0016 are the pre-reset record. ADRs 0017 onward record the
decisions of the 2026-05-19 transformation reset; where they supersede an
earlier ADR, the table says so.

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
| [0009](0009-local-only-operating-model.md) | Local-only operating model for Phase 1. |
| [0010](0010-observability-pipeline.md) | Observability pipeline shape - OTel + Tempo/Loki/Prometheus + audit join. |
| [0011](0011-phase-2-governed-platform-expansion.md) | Phase 2 governed platform expansion. |
| [0012](0012-langgraph-agent-execution-runtime.md) | LangGraph as first-class agent execution runtime inside Agent Runtime. Superseded by 0017. |
| [0013](0013-identity-authority-observability-boundaries.md) | Identity, authority, observability, journey evidence, and audit boundaries. |
| [0014](0014-connector-expansion-approval-hardening-scope.md) | Phase 2C connector expansion and approval-hardening scope. |
| [0015](0015-second-workflow-proof-scope.md) | Phase 2D second workflow proof scope. Second-workflow exemplar superseded by 0020. |
| [0016](0016-production-readiness-architecture-pack-scope.md) | Phase 2E production-readiness architecture pack scope. |
| [0017](0017-langgraph-removed-from-agent-execution.md) | LangGraph removed from the agent execution path (reverses 0012). |
| [0018](0018-llm-provider-port.md) | LLM provider port - OpenAI-SDK adapter, route catalogue, provider neutrality. |
| [0019](0019-audit-ports-and-replay-eval.md) | Audit ports - structured decision-trail and full-fidelity transcript - and replay as eval substrate. |
| [0020](0020-domain-refocus-uk-regulated-use-cases.md) | Domain refocus to UK-regulated use cases (supersedes the Lighthouse and Support Triage exemplars). |
