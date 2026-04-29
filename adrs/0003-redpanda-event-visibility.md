---
type: adr
status: accepted
date: 2026-04-28
---

# ADR 0003: Redpanda for Event Visibility and Async Projections

## Context

Chorus needs a visible event stream for domain events, audit feeds, read-model projection, progress updates, and exhausted-retry handling. The messaging layer should be inspectable locally without becoming the workflow source of truth.

## Decision

Use Redpanda Community Edition for Kafka-compatible messaging, Redpanda Console, and Schema Registry-backed event subjects. Use transactional outbox from Postgres-owned writes into Redpanda.

## Consequences

- Redpanda Console becomes a reviewer-facing evidence surface.
- Schema Registry governs event compatibility; producers and consumers still validate and serialise with generated contract code.
- Temporal remains the workflow authority.
- Consumers must be idempotent and dedupe by event ID or invocation ID.
- DLQ topics are used for exhausted async processing.

