---
type: adr
status: accepted
date: 2026-04-28
---

# ADR 0006: JSON Schema Canonical Contracts and Generated Pydantic Models

## Context

Agent, event, and tool contracts must be explicit enough for CI, reviewers, and runtime validation. Duplicating contract shapes across hand-written models would make drift likely.

## Decision

Use JSON Schema as the canonical source for events and agent/tool contracts. Generate committed Pydantic models with `datamodel-code-generator`. Register event schemas in Redpanda Schema Registry. Validate sample payloads and generated-code drift in CI.

Use PydanticAI dynamic schema support only where static generation is awkward and the exception is documented.

## Consequences

- Contract changes are reviewable as schema diffs.
- Producers and consumers share generated types.
- Breaking changes use versioned subjects/topics and migration windows.
- CI must fail when schemas, generated models, samples, or registered compatibility assumptions drift.

