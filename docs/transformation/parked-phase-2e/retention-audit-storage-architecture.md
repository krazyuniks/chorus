---
type: project-doc
status: planning
date: 2026-05-19
---

# Retention and Audit Storage Architecture

## Purpose

This document is the Phase 2E-05 docs-first architecture artefact promised by
[ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md). It
defines how future Chorus work should classify retention for telemetry,
journey projections, audit/accountability, decision-trail and Tool Gateway
audit records, approval and policy-change packages, eval/replay artefacts,
connector evidence, event-stream and schema evidence, secret metadata lifecycle
evidence, backup/restore/DR evidence, and incident/on-call evidence.

This is architecture-only. It does not add retention automation, archive
automation, export jobs, long-retention store implementation, Scylla or another
append-store implementation, migrations, managed databases, object storage
resources, cloud resources, services, runtime enforcement changes, or runtime
behaviour changes.

## Source Boundaries

This artefact composes the existing authority, observability, recovery, and
production-readiness models:

| Source | Provides |
|---|---|
| [ADR 0005](../adrs/0005-postgres-first-storage.md) | Postgres-first storage and deferred Scylla posture. |
| [ADR 0010](../adrs/0010-observability-pipeline.md) | Telemetry pipeline and audit-to-trace join boundary. |
| [ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md) | Infrastructure telemetry, journey evidence, audit/accountability, and sidecar plane split. |
| [ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md) | Phase 2E scope, non-goals, safe-data rules, and ordered backlog. |
| [observability-user-journey-model.md](observability-user-journey-model.md) | Field placement rules for telemetry, projections, audit, and baggage. |
| [human-approval-audit-lifecycle.md](human-approval-audit-lifecycle.md) | Approval package refs, lifecycle states, expiry, SLA, and audit events. |
| [policy-change-governance-workflow.md](policy-change-governance-workflow.md) | Policy-change package refs, apply/rollback refs, eval evidence refs, expiry, and audit events. |
| [secrets-credential-handling.md](secrets-credential-handling.md) | Secret metadata lifecycle, rotation, revocation, break-glass refs, and value exclusion rules. |
| [deployment-topology-architecture.md](deployment-topology-architecture.md) | Future store, stream, telemetry, identity, and secret-injection placement. |
| [backup-restore-dr-architecture.md](backup-restore-dr-architecture.md) | RPO/RTO classes, authoritative store order, restore dependency order, and recovery evidence. |
| [llm-observability-sidecar-evaluation.md](llm-observability-sidecar-evaluation.md) | Optional sidecar export, sampling, retention, and non-authoritative export rules. |

## Scope

2E-05 defines:

- retention classes and ownership for each evidence plane;
- a Postgres-first retention posture for audit/accountability records;
- audit-storage scaling signals that would justify evaluating Scylla or
  another append-heavy store;
- archival and export criteria before any archive or export job exists;
- delete, expire, and hold-style retention categories;
- restore and DR interactions for retained, expired, archived, and held data;
- safe field rules for examples, audit records, projections, fixtures, and
  continuation records;
- synthetic/local evidence expectations;
- promotion criteria and backlog implications.

## Non-Goals

This item does not add:

- retention jobs, expiry jobs, delete jobs, archive jobs, export jobs, or
  legal-hold automation;
- Scylla, Cassandra, object storage, data lake, warehouse, queue, search index,
  append store, or long-retention store implementation;
- migrations, partitioning, table changes, schema changes, managed databases,
  managed event streams, managed telemetry, object storage resources, cloud
  resources, Terraform, Kubernetes manifests, ECS/EKS/Lambda configuration,
  DNS, certificates, network resources, or deployment automation;
- production SSO, production identity-provider integration, IAM enforcement,
  secret-manager integration, credential entry, credential mutation,
  production connectors, hosted observability exporters, production provider
  calls, services, runtime enforcement changes, or runtime behaviour changes;
- reviewer decision UI, policy mutation UI, policy apply paths, ticket status
  execution, backup automation, restore tooling, replication, or PITR policy.

## Design Rules

- Retention policy must not change authority ownership. Temporal remains the
  workflow-state authority, Postgres audit remains the accountability
  authority, event streams remain projection/visibility paths, and telemetry
  remains operational evidence.
- Postgres remains the default audit store until measured append volume, query
  shape, retention horizon, restore pressure, or operational cost proves that a
  second store is justified.
- Audit data is append-first. Future expiry or archive work may mark data with
  lifecycle categories or move cold copies, but it must not hide, rewrite, or
  silently delete authority-sensitive history.
- Projection and telemetry retention can be shorter than audit retention
  because they are derived or operational. They must be rebuildable or clearly
  disposable.
- Retention examples use refs and bounded categories only. Raw payloads,
  prompts, outputs, arguments, connector payloads, rationale, credentials,
  identity-provider claims, operational identifiers, or PII are excluded.
- A future export is derived evidence, not authority, unless a later ADR makes
  the exported store an explicitly governed audit replica with restore,
  integrity, redaction, and query evidence.
- Deletion and expiry categories are policy language in this item. They are not
  executable data mutation.

## Retention Classes

Retention classes name the intended durability and accountability stance. They
are future policy categories, not implemented time periods.

| Retention class | Purpose | Default owner | Default store posture | Expiry posture |
|---|---|---|---|---|
| `retention_telemetry_short` | Operational traces, logs, metrics, and dashboard time series. | Observability owner. | Telemetry stores or future managed backend; not Postgres audit. | Expire by operational need; audit joins must remain queryable without traces. |
| `retention_projection_refresh` | BFF/UI read models, workflow summaries, calendar/support inspection views, and journey projections. | Application projection owner. | Postgres read models while local; rebuildable from authority inputs. | Rebuild or expire as derived data; do not use as audit authority. |
| `retention_audit_accountability` | Authority-sensitive decisions, approvals, policy changes, tool verdicts, and invocation decisions. | Application audit owner. | Postgres-first append-only authority store. | Retain by accountability requirement; future expiry requires audit-safe lifecycle evidence. |
| `retention_decision_tool_audit` | Decision trail and Tool Gateway audit rows. | Agent Runtime and Tool Gateway audit owners. | Postgres-first; partition or archive only after scaling evidence. | Do not delete silently; future archive must keep queryable refs. |
| `retention_release_evidence` | Eval fixtures, replay histories, contract refs, gate result refs, and release evidence. | Release/eval owner. | Source control and CI/release artefact retention; local Postgres only for run evidence. | Retain enough to reproduce release claims; raw production payloads remain excluded. |
| `retention_connector_evidence` | Connector invocation refs, idempotency refs, compensation refs, sandbox state refs, and bounded outcomes. | Tool Gateway and connector owner. | Postgres audit and local connector state while local. | Keep authority refs with audit; derived connector state may expire or reconcile. |
| `retention_stream_schema_evidence` | Event-stream refs, outbox refs, schema subject/version refs, compatibility refs, and projection offsets. | Event/schema owner. | Event stream plus Postgres outbox and source-controlled contracts. | Stream history can expire when authoritative rows and contracts can rebuild projections. |
| `retention_secret_lifecycle` | Secret refs, lifecycle categories, rotation, revocation, expiry, and break-glass evidence refs. | Secret metadata owner and audit owner. | Metadata-only Postgres audit/catalogue posture when promoted. | Retain lifecycle refs; never retain secret values. |
| `retention_recovery_evidence` | Backup refs, restore refs, drill refs, RPO/RTO class refs, dependency-order refs, and gate refs. | Recovery owner. | Runbook/gate evidence plus future metadata store. | Retain for recovery claims; do not store raw restore logs or payloads. |
| `retention_incident_evidence` | Incident refs, severity/status categories, escalation refs, change-freeze refs, post-incident refs, and linked policy/approval refs. | Incident owner and audit owner. | Future incident audit/projection store; Postgres-first for authority links. | Retain incident-to-audit links; detailed telemetry can expire separately. |
| `retention_optional_sidecar` | Optional LLM observability sidecar trace/eval exports. | Observability/export owner. | Derived opt-in export only. | Sidecar retention is non-authoritative and must not gate release or accountability. |

## Evidence Retention Matrix

| Evidence family | Retention class | Authority stance | Minimum retained refs | Expire/delete/hold category |
|---|---|---|---|---|
| Infrastructure telemetry | `retention_telemetry_short` | Operational only. | `trace_ref`, `span_ref`, service ref, workload ref, correlation ref, bounded failure category. | `expire_operational`, `sample_operational`, `incident_window_hold`. |
| Application and user journey projections | `retention_projection_refresh` | Derived journey evidence. | tenant, workflow, correlation, actor-session, journey-event, projection, fixture refs, status category. | `rebuildable_expire`, `projection_rebuild`, `projection_hold`. |
| Audit/accountability | `retention_audit_accountability` | Canonical accountability store. | tenant, workflow, correlation, invocation, approval, policy-change, workload, trace join, evidence refs. | `retain_accountability`, `archive_candidate`, `hold_accountability`. |
| Decision trail records | `retention_decision_tool_audit` | Agent Runtime authority record. | invocation, agent, prompt ref/hash, route, provider/model, budget, graph, trace join, outcome refs. | `retain_accountability`, `archive_candidate`, `hold_accountability`. |
| Tool Gateway audit records | `retention_decision_tool_audit` | Tool authority record. | tool call, tool name, requested/enforced mode, grant, verdict, idempotency, connector invocation, trace join refs. | `retain_accountability`, `archive_candidate`, `hold_accountability`. |
| Approval packages and audit | `retention_audit_accountability` | Future approval authority record. | approval, package version, actor subject, actor session, role, decision, expiry/SLA, workload, policy refs. | `retain_accountability`, `expire_pending_package`, `hold_accountability`. |
| Policy-change packages and audit | `retention_audit_accountability` | Future policy mutation authority record. | policy-change, target refs, before/after refs, eval refs, approval refs, apply/rollback refs, actor/workload refs. | `retain_accountability`, `expire_pending_package`, `hold_accountability`. |
| Eval and replay artefacts | `retention_release_evidence` | Release evidence, not runtime authority. | fixture, replay, gate, release, workflow type, expected/actual outcome, failure category refs. | `retain_release_ref`, `superseded_release_ref`, `hold_release_ref`. |
| Connector evidence | `retention_connector_evidence` | Tool Gateway audit owns authority; connector state is supporting evidence. | connector, tool, idempotency, compensation, retry, external-ref-safe, outcome, grant refs. | `retain_authority_ref`, `expire_connector_cache`, `hold_connector_ref`. |
| Event-stream and schema evidence | `retention_stream_schema_evidence` | Visibility/projection evidence; contracts remain source. | event, outbox, schema subject, schema version, compatibility, consumer, projection refs. | `expire_stream_history`, `retain_schema_ref`, `hold_stream_window`. |
| Secret metadata lifecycle evidence | `retention_secret_lifecycle` | Metadata-only authority evidence when promoted. | secret ref, version ref, lifecycle state, owner boundary, rotation/revocation/break-glass, approval, incident refs. | `retain_secret_metadata`, `expire_inactive_ref`, `hold_secret_metadata`. |
| Backup, restore, and DR evidence | `retention_recovery_evidence` | Recovery claim evidence. | backup, restore, drill, runbook, gate, store, environment, RPO/RTO class, dependency-order refs. | `retain_recovery_ref`, `superseded_drill_ref`, `hold_recovery_ref`. |
| Incident and on-call evidence | `retention_incident_evidence` | Future incident accountability and operations bridge. | incident, severity, status, escalation, change-freeze, runbook, approval, policy-change, restore refs. | `retain_incident_ref`, `incident_window_hold`, `post_incident_archive_candidate`. |

## Audit Storage Ownership

Audit storage ownership follows the boundary that makes the authority decision.

| Owner | Owns | Must not own |
|---|---|---|
| Agent Runtime | Decision-trail records for agent invocation authority, route/model selection, graph execution, budget, output validation, and fallback evidence. | Tool grant decisions, connector invocation authority, telemetry retention policy. |
| Tool Gateway | Tool request validation, grant/mode enforcement, approval-required verdicts, idempotency, redaction, connector invocation refs, compensation refs, and tool audit. | Agent reasoning, model route selection, workflow state, reviewer decisions. |
| Approval boundary | Future approval packages, decision refs, reviewer actor refs, expiry/SLA categories, and approval audit. | Direct connector execution or policy apply. |
| Policy-change boundary | Future policy-change packages, target refs, eval refs, apply/rollback refs, and policy-change audit. | Direct table mutation outside governed apply or release-gate authority. |
| Projection owner | Derived BFF/UI read models and journey projections. | Canonical accountability or workflow state. |
| Observability owner | Telemetry retention, sampling, dashboard config, and optional sidecar export policy. | Audit accountability, release gating, or business authority. |
| Recovery owner | Backup/restore/DR evidence refs and drill metadata. | Secret values, workflow history mutation, or audit rewriting. |
| Incident owner | Future incident refs, severity/status, escalation, change-freeze, and post-incident linkage. | Retrospective audit mutation or hidden policy changes. |

Where ownership crosses boundaries, retain join refs rather than copying full
packages. For example, incident evidence can link to approval and policy-change
refs, but it should not duplicate full approval or policy bodies.

## Postgres-First Retention Posture

Postgres remains the authoritative audit store for Phase 2E planning.

The default posture is:

- keep `decision_trail_entries`, `tool_action_audit`, future approval audit,
  future policy-change audit, secret lifecycle metadata, and incident-to-audit
  refs Postgres-owned until a later item proves otherwise;
- use Postgres read models for projections, but classify them as rebuildable;
- use event streams for visibility and projection feed retention, not as the
  audit source of truth;
- use telemetry stores for operational retention, not for accountability;
- prefer schema design, indexes, partitioning, and cold-query rules before
  adding a second audit store;
- require restore and DR evidence before any cold audit copy is treated as
  recoverable authority.

This posture deliberately defers Scylla or another append-store. The decision
to evaluate another store should come from evidence, not from anticipating
scale in a local reference implementation.

## Audit Scaling Signals

Evaluate audit storage changes only when one or more measured signals appears
in local, synthetic, or production-like evidence:

| Signal | What it means | First response before new store |
|---|---|---|
| Append throughput pressure | Audit writes for decision trail, Tool Gateway, approval, policy, connector, or incident evidence exceed the selected Postgres write target. | Batch boundaries, indexes, partitioning, connection limits, and write-path profiling. |
| Hot query latency pressure | Reviewer, eval, BFF, or incident queries over audit refs exceed agreed query targets. | Query plans, covering indexes, materialised projections, and bounded query windows. |
| Retention horizon pressure | Required accountability retention makes hot Postgres storage or backup windows impractical. | Partition/cold-table strategy and archive-read requirements. |
| Restore pressure | Audit volume prevents meeting the selected recovery class. | Restore-scope partitioning and recovery drill evidence. |
| Isolation pressure | Tenant or workflow retention classes need stronger physical separation than current tables provide. | Tenant partitioning or scoped archive design. |
| Query-shape divergence | Audit workloads become append-heavy and historical-range-heavy while OLTP paths remain hot. | Separate read replicas or cold partitions before a new primary store. |
| Export/replay pressure | Eval, incident, or compliance review needs deterministic long-range replay over audit refs. | Derived audit reports and signed manifests before adopting another authority store. |

None of these signals implements a store. They trigger an ADR or spike proposal
with evidence and non-goals.

## Scylla or Append-Store Evaluation Triggers

Scylla, Cassandra, another append-heavy store, or an immutable ledger-like
append store may be evaluated only when all of these are true:

- Postgres-first mitigations have been measured and documented;
- the data family is clearly append-heavy, long-retention, and queryable by
  safe refs such as tenant, workflow, correlation, invocation, tool, approval,
  policy-change, incident, fixture, or retention refs;
- the candidate store has an explicit owner, schema model, consistency model,
  backup/restore model, retention model, and redaction model;
- Postgres remains the source of truth during the evaluation, or the ADR
  explicitly defines the cut-over and reconciliation path;
- restore drills prove the new store does not weaken Temporal workflow
  recovery, Postgres audit recovery, eval/replay evidence, or incident
  reconstruction;
- examples, manifests, and tests use safe refs and bounded categories only.

Evaluation is not implementation. A later ledger item must separately approve
schema, migration, dual-write, backfill, replay, retention, and operational
work before another store can become executable.

## Archival and Export Criteria

A future archive or export path must satisfy these criteria before any job is
implemented:

| Criterion | Requirement |
|---|---|
| Scope | Names one retention class, owner, source store, destination category, and reason category. |
| Field allow-list | Includes only safe refs, bounded categories, redacted summaries where explicitly allowed, and integrity refs. |
| Authority stance | States whether the export is derived evidence, cold audit copy, release evidence, incident evidence, or recovery evidence. |
| Integrity | Defines manifest refs, source range refs, schema refs, count refs, and verification refs without raw payloads. |
| Access boundary | Names workload principal refs, approval or policy-change refs where required, and read-only query refs. |
| Restore stance | Defines whether the export can restore data, rebuild projections, or only support review. |
| Deletion stance | Defines how expired, superseded, and held refs are represented. |
| Failure stance | Defines bounded failure categories and retry/idempotency refs. |
| Gate stance | Adds focused tests, forbidden-field checks, runbook inspection, and evidence-map updates. |

Exports must not include raw prompts, raw outputs, raw tool arguments, raw
connector payloads, raw approval or policy rationale, credentials,
identity-provider claims, operational identifiers, or PII.

## Delete, Expire, and Hold Categories

2E-05 defines retention categories, not mutation behaviour.

| Category | Meaning | Applies to |
|---|---|---|
| `active_retained` | Evidence remains in its normal store and query path. | Audit, projections, release evidence, current recovery refs. |
| `expired_operational` | Operational telemetry is no longer needed for normal diagnosis. | Telemetry, sidecar exports, selected logs/metrics. |
| `expired_rebuildable` | Derived projections can be rebuilt or discarded. | BFF/UI read models, journey projections, connector caches. |
| `expired_pending_package` | Undecided or unapplied packages passed expiry and cannot authorise action. | Future approval and policy-change packages. |
| `superseded_ref` | A newer package, release, schema, drill, or policy version replaces the old one, but refs remain inspectable. | Eval/replay, policy, schema, restore, incident evidence. |
| `archive_candidate` | Evidence may move to a cold query path if future archive work is approved. | Long-retention audit, connector evidence, incident evidence. |
| `hold_accountability` | Deletion or expiry is suspended for an accountability reason category. | Audit, approval, policy, connector, secret lifecycle, incident evidence. |
| `incident_window_hold` | Operational telemetry or stream windows are retained for a bounded incident review. | Telemetry, event-stream windows, sidecar exports. |
| `erase_derived_view` | A derived projection can be deleted and rebuilt from authority inputs. | Projections and UI read models only. |
| `tombstone_ref_only` | Future deletion leaves a minimal non-secret ref and lifecycle category where accountability requires it. | Selected packages, connector caches, secret metadata refs, projection rows. |

Future executable deletion must be scoped by a separate item with tests that
prove authority records are not silently removed and held refs are respected.

## Restore and DR Interactions

Retention and recovery must agree before either becomes executable.

Rules:

- restore processes must not re-activate expired approval, policy-change,
  secret, connector, or incident refs;
- held accountability refs must remain held after restore until a future
  authorised release category is recorded;
- derived projections should be rebuilt from retained authority inputs rather
  than restored over newer audit;
- event-stream expiry is acceptable only when Postgres outbox/audit rows,
  contracts, and schema refs can rebuild required projections;
- telemetry expiry must not block workflow restore, audit review, or eval
  release evidence;
- cold archive or export copies cannot become restore authority until their
  integrity, schema, retention, and recovery procedures are proved;
- recovery drills must record which retention classes were retained, expired,
  rebuilt, held, or skipped using refs and bounded categories only.

If restore evidence conflicts with retention evidence, pause workloads and
reconcile by safe refs: release, migration, contract, workflow, correlation,
invocation, approval, policy-change, idempotency, connector, backup, restore,
incident, and gate refs.

## Synthetic and Local Evidence Expectations

For this docs-first item, evidence is the artefact itself plus phase-plan,
architecture, evidence-map, implementation-plan, runbook, overview, README,
agent-guide, and handoff alignment. Expected gates:

```bash
just contracts-check
just doctor-quick
git diff --check
```

The smallest additional relevant gate is a docs alignment search that proves
the new artefact is linked from the Phase 2 ledger, architecture, evidence map,
implementation plan, runbook, overview, README, agent guide, and continuation
records.

Future executable retention work must add focused evidence appropriate to the
behaviour it changes:

| Future change | Minimum evidence |
|---|---|
| Retention metadata persistence | Migration, safe seeds, lifecycle state tests, forbidden-field tests, runbook inspection. |
| Projection expiry or rebuild | Rebuild tests, stale-view tests, source authority checks, BFF safe-view tests. |
| Audit partitioning | Append-only tests, query compatibility tests, migration/rollback evidence, restore impact. |
| Archive/export job | Field allow-list tests, manifest verification, idempotency tests, no raw payload export tests. |
| Legal-hold-style category implementation | Hold/release state tests, deletion-denial tests, audit evidence, incident/policy linkage. |
| Scylla or append-store spike | ADR, dual-read/write or derived-copy plan, consistency tests, restore drill, rollback and cost-boundary evidence. |
| Retention-aware restore | Restore tests proving expired refs stay inactive, held refs stay held, and projections rebuild from authority. |
| Incident-window retention | Incident ref tests, bounded telemetry/stream window tests, non-authoritative telemetry stance. |

Runtime, replay, eval, persistence, BFF/UI, frontend, Tool Gateway, connector,
provider, identity-provider, hosted observability, cloud, deployment, backup,
restore, retention, archive, export, and append-store gates remain skipped for
2E-05 because no runtime behaviour changes.

## Safe Field Rules

Allowed examples and docs may use:

- stable refs: tenant, workflow, correlation, workload, workload session,
  actor session, invocation, authority context, approval, policy-change, route,
  grant, fixture, eval, release, incident, backup, restore, deployment, secret,
  provider, connector, event stream, schema subject, store, projection,
  retention, archive, export, hold, runbook, gate, trust-domain, role,
  identity-provider, environment, and data-class refs;
- bounded categories: retention class, retention state, lifecycle state,
  archive status, export status, hold reason category, RPO/RTO class, restore
  status, backup status, environment class, trust zone, workload kind, tenant
  scope, RBAC role, workflow type, task kind, tool mode, approval state,
  policy-change state, credential category, data class, failure class,
  severity, and status.

Forbidden everywhere in docs, examples, diagrams, plans, telemetry examples,
audit examples, eval fixtures, runbook examples, exports, manifests, and
handoff records:

- secrets, credentials, API keys, access tokens, session tokens, provider keys,
  connector credentials, database passwords, signing keys, private keys,
  certificate material, refresh tokens, cookies, token hints, or credential
  values;
- raw sensitive content, raw prompts, raw model outputs, raw tool arguments,
  raw connector payloads, raw approval rationale, raw policy rationale, policy
  diff bodies, raw request or response bodies, retrieval documents, file
  contents, unbounded exception text, raw logs, raw telemetry payloads, or raw
  restore/export payloads;
- identity-provider claims, profile data, names, email addresses, group claim
  payloads, hostnames, IP addresses, filesystem paths, local account material,
  cloud account IDs, full ARNs, external IDs, DNS names, certificate subjects,
  raw SPIFFE IDs, or PII;
- environment payloads, command lines that expose sensitive values or
  environment-specific identifiers, request headers, full user-agent strings,
  URL query strings, configuration dumps, archive manifests with sensitive
  fields, or restore logs containing raw payloads.

## Promotion Criteria

Promote this architecture into executable retention or audit-storage work only
when a later ledger item explicitly opens one of these behaviours:

- retention metadata persistence for a named data class;
- projection expiry, projection rebuild, or read-model pruning;
- audit table partitioning, cold-table movement, or long-retention query path;
- archive job, export job, manifest generation, or cold-copy verification;
- hold-style category persistence and release workflow;
- Scylla or another append-store evaluation spike;
- retention-aware backup/restore drill;
- incident-window telemetry or stream retention;
- sidecar export retention or deletion policy;
- production retention policy claim.

Promotion must start with the narrowest deterministic evidence path. It must
not bundle cloud resources, managed databases, object storage, production SSO,
identity-provider integration, secret-manager integration, provider calls,
connector writes, hosted observability export, reviewer decisions, policy
apply, ticket status execution, mutating admin UI, deployment automation, or
network resources unless those behaviours have their own ledger item, evidence
expectations, gates, and runbook updates.

## Backlog Implications

- `2E-06` incident and on-call integration must use the retention classes,
  incident-window hold category, audit ownership, and safe incident refs
  defined here when it scopes severity, escalation, change freezes, and
  post-incident evidence.
- `2E-07` managed observability must preserve the telemetry/sidecar retention
  stance: telemetry is short-retention operational evidence, optional sidecar
  exports are derived, and Postgres audit remains authoritative.
- `2E-08` production provider and connector hardening must keep provider,
  connector, idempotency, compensation, approval, policy, secret lifecycle, and
  incident evidence in the appropriate retention classes before production
  calls or writes are promoted.
- Any future backup, restore, DR, archive, export, object storage, managed
  database, managed event-stream, Scylla, append-store, or retention job work
  must include restore and deletion semantics before implementation.

Until those items land, Chorus remains a local reference implementation with
retention and audit storage defined as architecture, not implemented behaviour.
