---
type: project-doc
status: active
date: 2026-05-24
---

# Code Direction

This document states the implementation shape Chorus must preserve while R4
adds UC2, UC3, and live-provider replay.

## Workflow Spine

Workflow plumbing is domain-core territory and must not vary per use case.
Each use case defines its step sequence, contracts, policies, and connector
requirements on top of the shared `WorkflowSpine`.

Rules:

- workflow code stays deterministic;
- effectful work stays in activities;
- use-case modules declare workflow definitions instead of copying the
  orchestration loop;
- UC2 and UC3 add workflow definitions beside UC1, not another framework;
- Temporal remains the durable workflow engine.

## Connector Port

The Tool Gateway is the connector authority layer. It owns grants, mode
enforcement, argument validation, approval hooks, idempotency, redaction,
verdicts, and audit rows.

Rules:

- connector dispatch goes through `ConnectorRegistry`;
- each adapter declares its tool names and contracts;
- new adapters do not edit the gateway dispatch path;
- connector writes require explicit mode and approval policy where relevant;
- agents never receive ambient connector authority.

## Port-Oriented Modules

Code should be organised by port or by one clear concern.

Rules:

- projection read models live under the projection surface;
- decision-trail and transcript reads live under the audit port surface;
- runtime policy and provider-governance reads stay separate from projection
  mechanics;
- doctor probes stay split by scaffold, projection, connector, observability,
  workflow runtime, and UI concerns;
- eval keeps a common invariant core with per-use-case conduct invariants.

## Provider Boundary

The Agent Runtime is the domain-side caller of the LLM provider port.

Rules:

- provider SDKs are imported only by provider adapters;
- prompt references, prompt hashes, route IDs, route versions, and budget caps
  are resolved before invocation;
- live-provider routes must enforce task-specific structured output;
- provider route catalogue, DB policy, provider catalogue rows, BFF views, and
  eval route selection must agree.

## R4 Refactor Priorities

R4 should address these before adding breadth:

- widen UC1-shaped projection contracts, DB constraints, DLQ payloads, and eval
  fixture enums for UC2 and UC3;
- generalise approval packages beyond calendar-shaped writes;
- complete UC1 broker-firm-side persistence behind existing adapters;
- make live provider output schema-bound and replay-comparable;
- make eval reusable through common invariants plus use-case conduct modules.
