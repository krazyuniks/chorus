---
type: adr
status: accepted
date: 2026-04-28
---

# ADR 0005: Postgres-First Storage with Deferred Scylla Option

## Context

The research inputs considered append-heavy stores such as Scylla for high-volume decision trails and episodic histories. Phase 1 needs convincing evidence, not production-scale storage breadth.

## Decision

Use Postgres for Phase 1 service-owned storage: agent registry, policy materialisation, tool grants, outbox rows, workflow projections, decision trail, episodic history, and optional pgvector-backed semantic memory if Lighthouse needs retrieval.

Temporal uses its own persistence. Redpanda carries in-flight events and projection feeds.

## Consequences

- Local development and review stay simpler.
- Append-heavy tables should be partitionable and accessed through storage adapters so Scylla remains a production migration option.
- Scylla implementation is out of scope for Phase 1.
- Postgres row-level security and tenant IDs are part of the Phase 1 tenant-isolation evidence.
