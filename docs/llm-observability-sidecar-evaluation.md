---
type: project-doc
status: planning
date: 2026-05-17
---

# Optional LLM Observability Sidecar Evaluation

## Purpose

This document is the Phase 2B-06 evaluation promised by
[ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md). It
decides how LangSmith, Langfuse, or similar LLM observability tools may fit
around Chorus without changing the local authority model.

The decision is deliberately narrow: optional sidecars may consume derived
OpenTelemetry and eval evidence for debugging, annotation, graph inspection,
and experiment comparison. They are not the accountability store, release
gate, policy mutation path, prompt source of truth, or required local
dependency.

No exporter, contract, migration, seed, hosted service, credential path, SDK
dependency, or runtime behaviour change is added by this item.

## Capability Snapshot

The current tool category is compatible with a derived-export posture:

| Tool category | Useful capability | Chorus boundary |
|---|---|---|
| LangSmith | OpenTelemetry trace ingestion through an OTel Collector fan-out path and evaluation workflows over OTel-instrumented applications. | Optional trace/eval consumer only. Do not use as the release gate, prompt authority, policy mutation workflow, or audit store. |
| Langfuse | OpenTelemetry-based tracing, sessions, graph-style agent inspection, evaluation, annotation, datasets, and self-hosting options. | Optional trace/eval consumer only. Self-hosting is allowed as a future spike, but it still must not become a required local dependency. |
| Similar tools | OTel or file/API ingestion for traces, scores, annotations, and experiment comparison. | Must accept the same derived, redacted field set and must not require application code to send raw prompts, outputs, arguments, credentials, or identity claims. |

Langfuse prompt management and LangSmith/Langfuse experiment tooling are useful
product features, but Chorus already has prompt references, route metadata,
policy-change packages, Postgres audit, and eval gates as the local authority
surfaces. A sidecar can compare experiments; it cannot approve or apply them.

## Exporter Decision

The current decision is **do not implement a sidecar exporter in the default
local stack**.

The acceptable future exporter shape is:

1. Keep the default Compose evidence stack as Grafana, Tempo, Loki,
   Prometheus, Postgres audit, Temporal replay, and `just eval`.
2. Add any sidecar as an opt-in local profile or documented spike, disabled
   unless an operator supplies an endpoint and credentials through local
   environment configuration outside the repository.
3. Prefer OpenTelemetry Collector fan-out over application SDK fan-out so
   Chorus services emit once and the collector applies export filtering.
4. Export only a redacted derived subset of spans and eval summaries. Do not
   export Postgres audit rows as full payloads.
5. Make exporter failure non-blocking. The workflow, Tool Gateway, Agent
   Runtime, Postgres audit writes, and eval gates must continue to run without
   the sidecar.
6. Add a deterministic local export sketch only if a later item needs it. That
   sketch should emit NDJSON or JSON report rows from eval output and safe
   trace joins, not raw prompt/output/tool payloads.

Direct SDK integration from Agent Runtime or Tool Gateway is rejected for the
current phase because it would add a second export path beside OTel, create
credential pressure in service code, and make it easier to leak authority or
payload fields.

## Allowed Sidecar Field Set

Sidecar exports may contain only fields already allowed by the 2B-01 through
2B-05 placement models.

Allowed resource fields:

- `service.name`
- `service.namespace`
- `deployment.environment`
- `service.version`
- `chorus.workload.principal_id`
- `chorus.workload.trust_domain`

Allowed span and trace fields:

- `trace_id` and `span_id`
- `chorus.tenant_id`
- `chorus.correlation_id`
- `chorus.workflow_id`
- `chorus.workflow.type`
- `chorus.workflow.step`
- `chorus.invocation_id`
- `chorus.agent.id`
- `chorus.agent.version`
- `chorus.agent.role`
- `chorus.task_kind`
- `chorus.execution.engine`
- `chorus.execution.graph_version`
- `chorus.provider.id`
- `chorus.model.id`
- `chorus.route.id`
- `chorus.route.version`
- `chorus.fallback.applied`
- `chorus.fallback.reason`
- `chorus.tool.name`
- `chorus.tool.requested_mode`
- `chorus.tool.enforced_mode`
- `chorus.gateway.verdict`
- `chorus.event.type`
- `chorus.fixture.id`
- `chorus.actor.session_id`

Allowed eval summary fields:

- eval run ID or fixture run ID
- fixture ID
- workflow type
- expected outcome category
- actual outcome category
- pass/fail status
- bounded failure category
- route/provider/model IDs
- graph version
- fallback reason
- aggregate cost and latency values
- refs to local replay fixtures, eval fixtures, or persisted audit rows

Allowed join fields:

- `correlation_id`
- `workflow_id`
- `invocation_id`
- `trace_id`
- `span_id`
- eval run ID or fixture run ID
- fixture ID

Approval IDs, policy-change IDs, authority-context IDs, and grant refs remain
Postgres audit/accountability fields by default. If a future sidecar spike
needs one of those IDs for a specific review question, it must be promoted by
an explicit docs update and export allow-list test.

## Forbidden Data

The sidecar export path must never carry:

- secrets, credentials, API keys, access tokens, session tokens, signing keys,
  provider keys, or credential state;
- raw sensitive content, raw customer content, raw lead/email bodies, raw
  request or response bodies, raw prompts, raw model outputs, raw tool
  arguments, raw connector responses, raw retrieval documents, or file
  contents;
- raw approval rationale, raw policy-change rationale, policy diff bodies, or
  unbounded exception text;
- identity-provider claim dumps, email addresses, personal names, IP addresses,
  hostnames, local filesystem paths, cookies, request headers, full user-agent
  strings, or PII;
- telemetry baggage beyond the strict 2B-01 allow-list;
- full Postgres audit records or full authority packages.

Do not treat redacted audit as automatically exportable. Exporting audit-derived
summaries requires a separate allow-list review because audit remains the
accountability store.

## Retention and Sampling Assumptions

Local retention remains authoritative for local evidence:

- Postgres audit and projections survive until the local database is reset.
- Tempo and Loki are short-retention operational stores, currently pinned in
  the runbook to 24 hours for local development.
- Eval fixtures and replay fixtures are durable repo artefacts.
- `just eval` remains deterministic without any sidecar.

Sidecar retention is not authoritative. A hosted or self-hosted sidecar may
sample, expire, compact, reprocess, or delete data according to its own policy.
Chorus must therefore be able to answer accountability and release questions
without querying the sidecar.

Default sidecar sampling, if later added, should be opt-in and bounded:

- export failed eval runs and explicitly selected fixture runs first;
- export live workflow traces only for a named `correlation_id` or local
  reviewer session;
- avoid continuous 100 percent live export unless there is a measured
  debugging need and a documented retention setting;
- never retry sidecar export in a way that blocks workflow progress, gateway
  verdicts, audit writes, or eval completion.

## Local Authority

The authority split after this evaluation is:

| Question | Authoritative local surface |
|---|---|
| Did the platform run and where was latency or failure? | Grafana, Tempo, Loki, Prometheus, service logs, and health checks. |
| Which workflow, UI, fixture, or reviewer path was followed? | Postgres projections, BFF/UI read models, workflow history, and future journey events. |
| Who or what was authorised under which policy? | Postgres decision trail, Tool Gateway audit, future approval audit, and future policy-change audit. |
| Did a behaviour meet the release criteria? | `just eval`, replay tests, contract checks, and focused tests. |
| How did prompt/model/graph behaviour compare across runs? | Optional sidecar export, if explicitly configured, using derived safe fields only. |

LangSmith, Langfuse, or similar tools can improve debugging and reviewer
annotation. They do not decide whether a policy change is approved, whether a
route is promoted, whether a connector write is authorised, or whether a release
gate passed.

## Promotion Criteria

Keep sidecar support docs-only until all of these are true:

- a specific reviewer or development workflow needs prompt/model/graph
  comparison that Grafana, Postgres audit views, and `just eval` do not answer
  well;
- the candidate tool accepts OTel Collector fan-out or a deterministic file/API
  import that can be disabled by default;
- an export allow-list exists and is tested against representative spans/eval
  summaries;
- forbidden field detection covers prompt/output/tool/policy/approval/raw
  payload names and common credential names;
- exporter failure is proven non-blocking;
- retention and deletion assumptions are documented for the selected tool;
- README, architecture, runbook, evidence map, and phase plan state that the
  sidecar is optional and non-authoritative.

Promotion must not add AWS, production SSO, production cloud deployment,
credential entry, production identity-provider integration, production
connector writes, credential mutation, production provider calls, a hosted
observability dependency, mutating admin UI, raw prompts/outputs, raw tool
arguments, raw sensitive content, raw approval or policy rationale,
identity-provider claims, or PII.
