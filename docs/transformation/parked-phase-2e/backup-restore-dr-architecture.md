---
type: project-doc
status: planning
date: 2026-05-19
---

# Backup, Restore, and DR Architecture

## Purpose

This document is the Phase 2E-04 docs-first architecture artefact promised by
[ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md). It
defines how future Chorus work should classify recovery objectives, decide
which stores are authoritative, scope backups by data class, restore components
in dependency order, and rehearse disaster recovery with synthetic/local
evidence.

This is architecture-only. It does not add backup automation, restore tooling,
replication, PITR configuration, managed database configuration, managed event
streams, object storage resources, cloud resources, infrastructure-as-code,
deployment automation, secret-manager integration, credential entry,
credential mutation, migrations, services, runtime enforcement, or runtime
behaviour changes.

## Source Boundaries

This artefact composes the existing Phase 2E and authority models:

| Source | Provides |
|---|---|
| [ADR 0002](../adrs/0002-temporal-durable-orchestration.md) | Temporal owns workflow durability and replay. |
| [ADR 0003](../adrs/0003-redpanda-event-visibility.md) | Event streams support visibility and projections, not critical workflow state. |
| [ADR 0005](../adrs/0005-postgres-first-storage.md) | Postgres owns local application state, audit, projections, and policy materialisation. |
| [ADR 0009](../adrs/0009-local-only-operating-model.md) | The current implementation is local-only with no production backup or DR automation. |
| [ADR 0010](../adrs/0010-observability-pipeline.md) | Telemetry is operational and non-authoritative; audit remains Postgres-owned. |
| [ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md) | Identity, authority, telemetry, journey evidence, and audit are separate planes. |
| [ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md) | Phase 2E scope, non-goals, safe-data rules, and ordered backlog. |
| [production-identity-iam-mapping.md](production-identity-iam-mapping.md) | Future workload, actor, approval, policy, trust-domain, and RBAC refs. |
| [secrets-credential-handling.md](secrets-credential-handling.md) | Secret metadata versus secret value boundaries, rotation, revocation, and break-glass refs. |
| [deployment-topology-architecture.md](deployment-topology-architecture.md) | Future service topology, zones, deployment units, stores, streams, and egress boundaries. |
| [observability-user-journey-model.md](observability-user-journey-model.md) | Field-placement rules for telemetry, projections, audit, and journey evidence. |

## Scope

2E-04 defines:

- RPO and RTO classes for future production recovery planning;
- authoritative store order and conflict rules;
- backup scope by data class;
- restore responsibility by component;
- restore dependency order;
- Temporal persistence handling;
- application Postgres, decision-trail, audit, approval, policy, and local
  connector-state handling;
- event-stream and schema-registry handling;
- projection rebuild rules;
- telemetry store treatment;
- eval/replay artefact handling;
- secret metadata versus secret value handling;
- configuration and deployment ref handling;
- restore drill model and synthetic/local evidence expectations;
- safe field rules, promotion criteria, and backlog implications.

## Non-Goals

This item does not add:

- backup jobs, restore commands, replication, PITR policy, snapshots, archive
  jobs, retention jobs, object storage, managed database configuration, managed
  event-stream configuration, or DR infrastructure;
- Terraform, Kubernetes manifests, ECS, EKS, Lambda, DNS, certificate,
  load-balancer, network, cloud account, or deployment automation work;
- production SSO, production identity-provider integration, IAM enforcement,
  workload identity enforcement, tenant-admin UI, reviewer decision UI,
  policy mutation UI, policy apply paths, or ticket status execution;
- secret-manager integration, credential entry, credential mutation, provider
  keys, connector credentials, signing keys, identity-provider client secrets,
  certificate material, workload identity material, or production provider
  calls;
- production connectors, production connector writes, hosted observability
  exporters, migrations, services, contracts, eval fixtures, replay histories,
  workflow behaviour, BFF/UI behaviour, Tool Gateway behaviour, connector
  behaviour, or runtime enforcement changes.

## Design Rules

- Recovery planning must not change authority ownership. Temporal remains the
  workflow-state authority. Postgres audit remains the accountability
  authority. Event streams and projections remain visibility/read-model
  surfaces.
- Restore procedures must be dependency ordered. Workers and connectors stay
  paused until Temporal, application stores, schemas, policy refs, secret refs,
  and migrations are at compatible versions.
- A projection can be rebuilt from authoritative inputs; it must not be used to
  recreate workflow state, audit, approval, policy, or connector authority.
- Telemetry is useful for incident diagnosis but is not a restore source for
  workflow, audit, approval, policy, or eval claims.
- Secret metadata can be backed up as refs and lifecycle categories. Secret
  values, token payloads, private keys, certificate material, and credential
  bodies are outside Chorus application backup scope.
- Restore evidence uses synthetic tenant, workflow, correlation, backup,
  restore, deployment, secret, incident, runbook, gate, and fixture refs only.
- A future backup or restore workload is an authority-sensitive operational
  boundary. It must have workload principal refs, audit refs, runbook refs,
  forbidden-field checks, and evidence gates before it can be executable.

## RPO and RTO Classes

The classes below are future planning targets, not implemented service-level
objectives. They are used to discuss backup design without adding backup
automation in this item.

| Class | Applies to | RPO target | RTO target | Notes |
|---|---|---|---|---|
| `dr_class_critical_authority` | Temporal persistence, application Postgres audit/accountability, approval/policy package evidence when promoted. | Minimal acknowledged authoritative data loss for the selected environment. | Restore first; workers remain paused until consistency checks pass. | Requires a later executable item to choose backup method, replication, or PITR. |
| `dr_class_operational_state` | Outbox rows, local connector state, schema registry, event streams used for projection feed. | Short bounded loss is acceptable only when authoritative stores can re-emit or reconcile. | Restore after critical authority stores and before projection rebuild. | Event streams are not workflow authority. |
| `dr_class_rebuildable_projection` | Workflow read models, support/calendar inspection projections, dashboard-derived views. | Rebuild from authoritative stores or retained events. | Rebuild after stores and streams are available. | Never restore projections over newer authoritative audit. |
| `dr_class_release_evidence` | Contracts, eval fixtures, replay histories, gate-result refs, release refs. | Source-control or CI artefact retention target. | Available before runtime is declared restored. | Used to prove post-restore release and behaviour gates. |
| `dr_class_operational_telemetry` | Traces, logs, metrics, dashboard time series. | Best-effort retention; no accountability dependency. | Optional for service recovery; useful for incident analysis. | 2E-07 defines managed telemetry retention/export later. |
| `dr_class_secret_metadata` | Secret refs, lifecycle state, rotation/revocation/break-glass refs. | Same class as the authority workflow that uses the metadata. | Restored before workloads that require injection checks. | Values are not backed up by Chorus. |
| `dr_class_external_dependency_ref` | Provider refs, connector refs, identity-provider refs, deployment refs. | Refs must match the restored configuration version. | Validate before egress is enabled. | External systems have their own recovery model. |

Future production work must turn these classes into environment-specific
targets with named evidence. Until then, they are classification language only.

## Authoritative Store Order

When two surfaces disagree after restore, use this authority order:

| Order | Surface | Authoritative for | Conflict rule |
|---|---|---|---|
| 1 | Source-controlled release refs, contracts, migrations, and runbook refs | Schema, code, contract, and gate expectations for the restore target. | Do not restore runtime data into an incompatible release ref. |
| 2 | Secret value store or equivalent external secret authority | Secret values and active credential material. | Chorus restores only refs and lifecycle categories, never values. |
| 3 | Temporal persistence | Workflow histories, timers, retries, waits, signals, durable workflow state. | Do not rebuild workflow state from Redpanda, telemetry, or projections. |
| 4 | Application Postgres authority tables | Agent registry, model policy materialisation, tool grants, decision trail, tool audit, approval packages, policy changes, outbox, and local connector state. | Audit/accountability rows win over read models and telemetry. |
| 5 | Event stream and schema registry | Projection feeds, schema visibility, async delivery status. | Reconcile from outbox and contracts where retained; do not use stream data as workflow truth. |
| 6 | Projections and BFF/UI read models | Refresh-safe inspection and journey views. | Rebuild from authoritative inputs; discard stale projections. |
| 7 | Telemetry stores and dashboards | Operational diagnosis. | Use for incident context only; never as authority for business actions. |
| 8 | Eval/replay/gate artefact refs | Release and behaviour evidence. | Use to validate restored behaviour, not to recreate runtime state. |

## Backup Scope by Data Class

| Data class | Backup scope | Exclusions | Restore stance |
|---|---|---|---|
| Workflow state | Temporal persistence and workflow metadata refs. | Workflow code source, raw connector payloads, secret values. | Restore through Temporal-supported future mechanism only; workers paused until verified. |
| Application authority and audit | Postgres authority tables for registry, route materialisation, grants, decision trail, tool audit, approval packages, policy changes, outbox, and local connector refs. | Raw prompts/outputs beyond current redaction policy, secret values, raw external payloads. | Restore with schema-compatible release and tenant isolation checks. |
| Local connector state | Local CRM/ticket/calendar safe refs and bounded state categories where Chorus owns the sandbox state. | Production provider state, external connector payloads, raw customer content. | Restore only Chorus-owned safe state; reconcile external refs separately when production connectors exist. |
| Event stream | Stream topics, offsets, and retained event payloads where the future platform owns them. | Critical workflow authority. | Restore or replay only after schema compatibility and outbox reconciliation. |
| Schema registry | Subject refs, versions, and compatibility metadata. | Generated code as runtime truth. | Rebuild from contracts where possible, then validate compatibility. |
| Projections | Read models, support/calendar inspection summaries, journey projections when promoted. | Audit/accountability source data. | Prefer rebuild. Restore only as a cache when authoritative inputs match. |
| Telemetry | Dashboard definitions, telemetry config refs, selected incident-window traces/logs/metrics if later required. | Full raw logs containing forbidden fields, raw prompts/outputs, credentials. | Non-authoritative; restore only if incident analysis needs it. |
| Eval and replay | Fixture refs, replay history refs, gate result refs, release refs. | Raw production prompts/outputs, raw connector payloads, credential-bearing logs. | Restore from source control and CI artefact retention before declaring release evidence available. |
| Secret metadata | Secret refs, lifecycle categories, owner boundary refs, rotation/revocation/break-glass evidence refs. | Secret values, tokens, private keys, certificate bodies, credential payloads. | Restore metadata, then re-bind to external secret authority and deny missing/revoked values. |
| Configuration and deployment refs | Release refs, environment class, deployment refs, workload refs, store refs, stream refs, runbook refs. | Hostnames, IP addresses, DNS names, certificate subjects, cloud account IDs, full ARNs. | Validate refs before workloads resume; do not treat local config as production recovery. |

## Restore Responsibility by Component

| Component | Restore responsibility | Must not do |
|---|---|---|
| `svc_temporal_server` | Restore Temporal persistence compatibility and expose workflow histories to workers. | Accept direct workflow state writes from application services. |
| `svc_temporal_worker` | Resume code-defined workflows only after Temporal, application policy, schemas, and secret refs are compatible. | Start workflows during partial restore or call connectors directly. |
| `svc_agent_runtime` | Validate agent registry, route refs, prompt refs, provider refs, graph refs, and decision-trail write path. | Use provider credentials before secret refs and provider hardening are verified. |
| `svc_tool_gateway` | Validate grants, schemas, approval refs, idempotency refs, connector refs, and tool audit write path. | Execute connector writes from restored packages without re-checking package state, expiry, grant, mode, and idempotency. |
| `svc_connector_adapter` | Reconcile Chorus-owned connector refs and bounded local state after gateway readiness. | Recreate production provider state from local projections or audit examples. |
| `svc_projection_worker` | Rebuild read models from authoritative stores and event feeds after schemas are available. | Overwrite audit or workflow state from projection data. |
| `svc_bff` and `svc_ui` | Serve safe read-only projections after rebuild and RBAC checks when later implemented. | Expose raw restore logs, secret refs with values, or mutating recovery controls by default. |
| `svc_observability_collector` | Restore telemetry config and optional export filters after core authority surfaces are up. | Make telemetry availability a dependency for workflow or audit correctness. |
| `svc_identity_boundary` | Re-bind actor/workload refs after identity architecture is executable. | Persist identity-provider claims or use identity alone as business authority. |
| `svc_secret_injection_boundary` | Validate secret metadata refs and lifecycle categories against the external secret authority. | Restore or print secret values from Chorus backups. |
| `wp_eval_runner` | Run contracts, replay, eval, and docs gates against restored refs. | Treat a passing eval as evidence that backup automation exists. |

## Restore Dependency Order

Future restore drills should use this order:

1. Freeze the target environment class and restore scope using a `restore_ref`.
2. Select the release ref, contract set, migration set, runbook ref, and gate
   refs that define the restore target.
3. Validate secret metadata refs and external secret authority availability
   without exposing values.
4. Restore or validate Temporal persistence for the target workflow namespace
   before workers resume.
5. Restore application Postgres authority tables and apply schema-compatible
   migrations only under a future scoped restore procedure.
6. Reconcile outbox rows, idempotency refs, approval/package refs,
   policy-change refs, and connector invocation refs.
7. Restore or rebuild schema registry subjects from contracts, then validate
   event compatibility.
8. Restore or reconcile event-stream retained data and offsets where the future
   event platform owns them.
9. Rebuild projections, support/calendar inspection summaries, and future
   journey views from authoritative inputs.
10. Restore telemetry config and optional incident-window telemetry if needed.
11. Run contracts, doctor-quick, replay/eval, persistence, and focused runtime
    gates selected by the restore scope.
12. Unfreeze workloads and egress only after authority checks pass and skipped
    gates are documented.

This order is a model. It is not an executable procedure.

## Temporal Persistence Handling

Temporal persistence is authoritative for workflow history and durable workflow
state. It is not rebuilt from Redpanda, BFF projections, Grafana, or eval
output.

Future Temporal recovery must:

- restore histories, timers, signals, retries, and workflow execution metadata
  through a Temporal-compatible recovery mechanism selected by a later item;
- keep workflow workers paused until code, contracts, activities, and
  application policy are compatible with the restored histories;
- run replay gates for any workflow families affected by the restore target;
- preserve workflow IDs, correlation IDs, workflow type categories, and safe
  run refs as join evidence;
- reconcile activities that may have called Agent Runtime or Tool Gateway
  before failure by checking idempotency refs and audit rows;
- branch ambiguous side-effect recovery to escalation or manual review refs,
  not hidden connector execution.

Temporal restore must not directly mutate workflow histories, synthesize
missing histories from events, or use telemetry spans as workflow-state
evidence.

## Application Postgres and Audit Handling

Application Postgres remains the authority for local policy materialisation,
decision trail, Tool Gateway audit, approval packages, policy-change packages
when promoted, outbox rows, local connector state, and projections.

Future application-store recovery must:

- restore authority tables before read models;
- validate schema version, migration refs, tenant isolation, RLS expectations,
  and generated-contract compatibility before workloads resume;
- keep `decision_trail_entries`, `tool_action_audit`, approval audit, and
  policy-change audit append-only;
- reconcile idempotency refs before retrying or replaying activities;
- preserve redaction labels and bounded reason categories without expanding
  audit data after restore;
- retain outbox status categories so event relay can distinguish pending,
  sent, failed, and terminal evidence states;
- rebuild read models after authoritative rows are validated.

If an application-store restore conflicts with Temporal histories, pause
workers and reconcile by workflow ID, correlation ID, invocation ID,
idempotency refs, approval refs, policy-change refs, and audit refs. Do not use
projections or telemetry to overwrite audit.

## Event Stream and Schema Registry Handling

The event stream is a projection and visibility path. It does not own workflow
state or audit accountability.

Future event recovery must:

- restore schema-registry subjects or rebuild them from source-controlled JSON
  Schema contracts before producers resume;
- validate compatibility between restored subjects, generated models, and the
  release ref;
- restore retained stream data and consumer offsets only where the future event
  platform owns those artefacts;
- use Postgres outbox rows as the reconciliation source for events that were
  persisted but not published;
- dedupe consumers by source event ID, workflow sequence, workflow ID,
  invocation ID, or idempotency refs as appropriate;
- treat missing stream history as projection loss when authoritative stores
  can rebuild the read model.

Do not use event-stream data to reconstruct Temporal state, approval decisions,
policy decisions, or connector authority.

## Projection Rebuild Rules

Projection rebuild is the default for BFF/UI read models after restore.

Rules:

- Rebuild projections only after Temporal, application authority tables,
  schema registry, and event/outbox reconciliation are stable.
- Prefer deterministic rebuild from `outbox_events`, workflow event payloads,
  decision trail, tool audit, approval packages, policy packages, and local
  connector safe refs.
- Preserve idempotency by source event ID and workflow sequence.
- Ignore events older than the current authoritative sequence for the same
  workflow or projection key.
- Rebuild support and calendar inspection views from safe persisted refs only.
- Mark ambiguous or partially rebuilt projections with bounded status
  categories such as `projection_rebuild_pending`,
  `projection_rebuild_complete`, or `projection_rebuild_blocked`.
- Verify rebuilt views by counts and safe refs, not by raw payload content.

Projections must not contain secret values, raw prompts/outputs, raw tool
arguments, raw connector payloads, identity-provider claims, names, email
addresses, host data, or PII.

## Telemetry Store Treatment

Telemetry stores are operational evidence and incident context. They are not
restore authority.

Future telemetry recovery may restore:

- dashboard definitions and telemetry configuration refs;
- exporter allow-list refs when 2E-07 promotes managed observability;
- selected incident-window telemetry refs if retention policy later requires
  it;
- aggregate service-health and failure-category data.

Telemetry recovery should not block workflow restore unless the target drill is
specifically an observability recovery drill. Missing traces, logs, or metrics
do not invalidate Temporal history, Postgres audit, Tool Gateway verdicts, or
eval gates.

## Eval and Replay Artefact Handling

Eval and replay artefacts are release evidence. They are restored from source
control and CI/release artefact retention, not from production runtime stores.

Future recovery must preserve:

- contract refs and generated-model drift gate refs;
- eval fixture refs and replay fixture refs;
- gate result refs and release refs;
- fixture run refs, workflow type categories, expected outcome categories, and
  bounded failure categories;
- post-restore gate evidence showing which tests passed and which were skipped.

Do not store raw production prompts, raw model outputs, raw connector payloads,
raw approval or policy rationale, credentials, identity-provider claims, names,
email addresses, host data, or PII in eval/replay artefacts.

## Secret Metadata Versus Secret Values

Secret metadata and secret values have different recovery owners.

| Item | Chorus backup stance | Restore rule |
|---|---|---|
| Secret refs | Back up as metadata if a future catalogue exists. | Restore refs and lifecycle categories before workload injection checks. |
| Secret lifecycle state | Back up planned, active, rotating, rotated, revoked, expired, break-glass, and retired categories. | Deny use of revoked, expired, retired, or missing refs. |
| Rotation/revocation evidence | Back up refs and bounded outcome categories. | Preserve evidence and require follow-up gates where recovery uses a replacement ref. |
| Break-glass evidence | Back up break-glass refs, incident refs, approval refs, expiry categories, and follow-up refs. | Never convert break-glass state into permanent authority. |
| Secret values | Outside Chorus application backup scope. | Recover through the external secret authority selected by later work; never from docs, fixtures, logs, or audit examples. |

Restoring a database or deployment backup must not revive a revoked credential
value. If secret metadata says a ref is revoked or expired, workloads fail
closed until a later credential recovery item replaces it.

## Configuration and Deployment Ref Handling

Configuration recovery is based on refs, not environment dumps.

Future restore evidence may include:

- release refs;
- migration refs;
- contract refs;
- environment class;
- deployment refs;
- workload refs;
- store refs;
- stream refs;
- schema subject refs;
- secret refs;
- runbook refs;
- gate refs;
- rollback refs.

Future restore evidence must not include hostnames, IP addresses, DNS names,
certificate subjects, cloud account IDs, full ARNs, environment payloads,
command lines with sensitive values, local filesystem paths, or credential
values.

Deployment refs must match the topology model before restore automation can be
promoted. Local Compose evidence remains local evidence; it is not a production
DR plan.

## Restore Drill Model

Future drills should start local and synthetic before any production recovery
claim is made.

| Drill | Purpose | Evidence |
|---|---|---|
| `drill_tabletop_refs` | Walk through data classes, authority order, owners, and skipped gates. | Runbook refs, decision refs, gap refs, no runtime mutation. |
| `drill_projection_rebuild_local` | Rebuild safe projections from synthetic/local authoritative rows. | Projection status refs, count refs, gate refs. |
| `drill_temporal_replay_post_restore` | Prove workflow histories remain compatible after restoring the release ref. | Replay fixture refs, workflow type refs, gate result refs. |
| `drill_audit_consistency_local` | Verify decision trail, tool audit, approval refs, and policy refs join after restore. | Audit refs, idempotency refs, safe trace join refs. |
| `drill_event_schema_reconcile` | Rebuild schema registry from contracts and reconcile outbox/stream state. | Contract refs, subject refs, compatibility gate refs. |
| `drill_secret_metadata_fail_closed` | Prove missing/revoked secret refs deny injection without exposing values. | Secret refs, lifecycle category refs, denial gate refs. |
| `drill_full_synthetic_recovery` | Rehearse restore order with synthetic tenant/workflow refs only. | Restore ref, gate refs, skipped-gate refs, follow-up backlog refs. |

Current 2E-04 evidence is docs-first only. These drills are future backlog
models, not implemented commands.

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
the new artefact is linked from the Phase 2 ledger, architecture, evidence
map, implementation plan, runbook, overview, README, agent guide, and
continuation records.

Future executable restore work must add focused evidence appropriate to the
behaviour it changes:

| Future change | Minimum evidence |
|---|---|
| Backup automation | Data-class matrix, owner refs, forbidden-field scan, backup metadata tests, runbook evidence, failure classification. |
| Restore tooling | Dependency-order tests, fail-closed secret refs, schema compatibility tests, idempotency and audit consistency tests. |
| Replication or PITR | Consistency-window evidence, RPO/RTO measurement refs, recovery conflict tests, rollback refs. |
| Temporal restore | Replay gates, worker pause/resume checks, activity idempotency reconciliation, workflow history inspection. |
| Application Postgres restore | Migration compatibility, tenant isolation, audit append-only checks, idempotency reconciliation, projection rebuild. |
| Event-stream restore | Schema compatibility, outbox reconciliation, consumer dedupe, projection rebuild evidence. |
| Secret metadata recovery | No-value persistence tests, revoked/missing-denial tests, rotation/revocation evidence. |
| Telemetry recovery | Export allow-list tests, incident-window retention checks, non-authoritative status in runbook. |
| Full synthetic DR drill | Restore order evidence, gate result refs, skipped-gate refs, backlog follow-up refs, safe field scan. |

Runtime, replay, eval, persistence, BFF/UI, frontend, Tool Gateway, connector,
provider, identity-provider, hosted observability, cloud, deployment, backup,
and restore gates remain skipped for 2E-04 because no runtime behaviour
changes.

## Safe Field Rules

Allowed examples and docs may use:

- stable refs: tenant, workflow, correlation, workload, workload session,
  actor session, invocation, authority context, approval, policy-change, route,
  grant, fixture, eval, incident, backup, restore, deployment, secret,
  provider, connector, event stream, schema subject, store, runbook, gate,
  trust-domain, role, identity-provider, environment, retention, and data-class
  refs;
- bounded categories: RPO/RTO class, restore status, backup status,
  environment class, trust zone, workload kind, tenant scope, RBAC role,
  workflow type, task kind, tool mode, approval state, policy-change state,
  credential category, lifecycle state, retention class, data class, failure
  class, severity, and status;
- abstract service refs such as `svc_temporal_worker`, `svc_agent_runtime`,
  `svc_tool_gateway`, `svc_projection_worker`, and `svc_bff`.

Forbidden everywhere in docs, examples, diagrams, plans, telemetry examples,
audit examples, eval fixtures, runbook examples, and handoff records:

- secrets, credentials, API keys, access tokens, session tokens, provider keys,
  connector credentials, database passwords, signing keys, private keys,
  certificate material, refresh tokens, cookies, token hints, or credential
  values;
- raw sensitive content, raw prompts, raw model outputs, raw tool arguments,
  raw connector payloads, raw approval rationale, raw policy rationale, policy
  diff bodies, raw request or response bodies, retrieval documents, file
  contents, or unbounded exception text;
- identity-provider claims, profile data, names, email addresses, group claim
  payloads, hostnames, IP addresses, filesystem paths, local account material,
  cloud account IDs, full ARNs, external IDs, DNS names, certificate subjects,
  raw SPIFFE IDs, or PII;
- environment payloads, command lines that expose sensitive values or
  environment-specific identifiers, request headers, full user-agent strings,
  URL query strings, configuration dumps, backup manifests with sensitive
  fields, or restore logs containing raw payloads.

## Promotion Criteria

Promote this architecture into executable backup, restore, or DR work only
when a later ledger item explicitly opens one of these behaviours:

- backup automation for a named data class;
- restore tooling for a named component or store;
- replication, PITR, snapshot, archive, or object-store configuration;
- Temporal persistence backup or restore integration;
- application Postgres backup or restore integration;
- event-stream or schema-registry backup or restore integration;
- projection rebuild tooling;
- secret metadata recovery or external secret authority recovery;
- telemetry retention or incident-window recovery;
- full synthetic DR drill with measurable RPO/RTO evidence;
- production DR runbook claim.

Promotion must start with the narrowest deterministic evidence path. It must
not bundle cloud resources, production SSO, identity-provider integration,
secret-manager integration, provider calls, connector writes, hosted
observability export, reviewer decisions, policy apply, ticket status
execution, mutating admin UI, deployment automation, or network resources
unless those behaviours have their own ledger item, evidence expectations,
gates, and runbook updates.

## Backlog Implications

- `2E-05` retention and audit storage must use these data classes to define
  retention periods, archive/export criteria, audit scaling triggers, and
  deletion/expiry semantics without adding retention jobs or a new store.
- `2E-06` incident and on-call integration must bind incident refs to restore
  refs, backup refs, break-glass refs, severity categories, change-freeze
  categories, and post-incident evidence.
- `2E-07` managed observability must decide whether telemetry backup is
  configuration-only, incident-window retention, or managed-backend retention,
  while keeping telemetry non-authoritative.
- `2E-08` production provider and connector hardening must define how external
  provider/connector state is reconciled after Chorus restore without
  bypassing Agent Runtime, Tool Gateway, approval, idempotency, eval, and
  rollback evidence.
- Any future IaC, cloud, managed database, managed event-stream, object-store,
  or deployment work must include the DR impact before resources are created.

Until those items land, Chorus remains a local reference implementation with
backup, restore, and DR defined as architecture, not implemented behaviour.
