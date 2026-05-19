---
type: project-doc
status: planning
date: 2026-05-19
---

# Deployment Topology Architecture

## Purpose

This document is the Phase 2E-03 docs-first architecture artefact promised by
[ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md). It
defines the future production deployment topology for Chorus before any cloud
resources, infrastructure-as-code, orchestrator configuration, DNS,
certificates, deployment automation, managed databases, production SSO,
identity-provider integration, secret-manager integration, production provider
calls, production connector writes, migrations, services, runtime enforcement,
or runtime behaviour changes are added.

The goal is to show where the existing Chorus ownership boundaries would sit in
a production topology: Temporal, Agent Runtime, Tool Gateway, BFF/UI,
projection, connectors, observability, identity, data stores, event streams,
and secret injection. The document separates local Compose evidence from a
future deployable architecture and defines the promotion criteria for any
later executable deployment or infrastructure spike.

## Source Boundaries

This artefact composes the existing production-readiness and authority models:

| Source | Provides |
|---|---|
| [ADR 0002](../adrs/0002-temporal-durable-orchestration.md) | Temporal remains the durable workflow owner. |
| [ADR 0003](../adrs/0003-redpanda-event-visibility.md) | Event streaming supports visibility and projections, not critical workflow state. |
| [ADR 0004](../adrs/0004-agent-runtime-and-tool-gateway.md) | Agent Runtime and Tool Gateway remain explicit authority boundaries. |
| [ADR 0009](../adrs/0009-local-only-operating-model.md) | The current implementation is local-only and Compose-based. |
| [ADR 0010](../adrs/0010-observability-pipeline.md) | Local telemetry shape and audit-to-trace join contract. |
| [ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md) | Authentication, business authority, telemetry, journey evidence, and audit split. |
| [ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md) | Phase 2E scope, non-goals, safe-data rules, and ordered production-readiness backlog. |
| [production-identity-iam-mapping.md](production-identity-iam-mapping.md) | Future trust domains, workload principal refs, RBAC refs, and identity mapping. |
| [secrets-credential-handling.md](secrets-credential-handling.md) | Future secret refs, injection boundaries, rotation, revocation, and break-glass controls. |
| [observability-user-journey-model.md](observability-user-journey-model.md) | Safe telemetry, projection, BFF/UI, and audit field placement. |

## Scope

2E-03 defines:

- a future production service topology;
- environment classes and promotion boundaries;
- deployment unit boundaries and workload principal placement;
- network and trust zones;
- ingress and egress boundaries;
- data-store and event-stream placement;
- placement for Temporal, Agent Runtime, Tool Gateway, BFF/UI, projection,
  connector adapters, observability, identity, and secret injection;
- the local-to-production boundary;
- managed-versus-self-hosted component decisions;
- IaC spike criteria;
- evidence expectations, safe field rules, promotion criteria, and backlog
  implications.

## Non-Goals

This item does not add:

- Terraform, Kubernetes manifests, ECS, EKS, Lambda, serverless, container
  service, VM, networking, DNS, certificate, load-balancer, cloud account, or
  deployment automation configuration;
- managed databases, managed event streams, managed Temporal, managed
  observability, managed identity, or managed secret-store resources;
- production SSO, production identity-provider integration, IAM enforcement,
  workload identity enforcement, RBAC enforcement, or tenant-admin UI;
- secret-manager integration, credential entry, credential mutation, actual
  credentials, provider keys, connector credentials, signing keys,
  identity-provider client secrets, certificate material, or workload identity
  material;
- production provider calls, production connector writes, production
  connectors, hosted observability exporters, sidecar exporter code, or
  production telemetry destinations;
- migrations, services, contracts, eval fixtures, replay histories, workflow
  behaviour, runtime enforcement, Tool Gateway behaviour, BFF/UI behaviour,
  policy apply paths, reviewer decision paths, ticket status execution, or
  mutating admin paths.

## Design Rules

- Deployment topology is not authority. Business authority remains in Agent
  Runtime, Tool Gateway, approval audit, policy-change audit, and eval/replay
  gates.
- Network placement must not give agents ambient provider, connector, cloud, or
  database access.
- BFF/UI is the only human-facing application ingress in the future topology.
  It remains read-oriented until later RBAC, approval, or policy work opens
  mutation deliberately.
- Workflow workers call Agent Runtime and Tool Gateway boundaries; workflow
  code itself stays deterministic and does not perform network, identity,
  secret, or persistence work.
- Connectors execute only behind Tool Gateway allow, propose, or approved-apply
  decisions. Connector adapters do not accept direct agent or UI calls.
- Secret injection happens at owning effectful workload boundaries and exposes
  only secret refs, lifecycle categories, and evidence refs outside the
  injected process.
- Event streams and projections are visibility and read-model paths. Temporal
  remains the durable workflow state owner.
- Observability is operational and derived. Postgres audit, Temporal replay,
  Tool Gateway audit, approval audit, policy-change audit, and eval remain
  authoritative for accountability and release claims.

## Future Production Service Topology

The target production topology keeps the current local ownership boundaries but
places them into explicit deployable units and zones. The names below are safe
refs, not deployed services or resource names.

```text
external_actor_ref
  -> zone_ingress
     -> svc_ui
     -> svc_bff
        -> zone_application
           -> svc_projection_reader
           -> store_application

external_event_ref
  -> zone_intake
     -> svc_intake_adapter
        -> temporal_workflow_start

zone_application
  -> svc_temporal_worker
     -> svc_agent_runtime
     -> svc_tool_gateway
        -> svc_connector_adapter
           -> external_connector_ref

svc_agent_runtime
  -> external_provider_ref

svc_projection_worker
  <- stream_workflow_events
  -> store_application

svc_observability_collector
  <- all_workload_telemetry
  -> store_telemetry_or_export_ref

svc_identity_boundary
  -> actor_subject_ref and workload_principal_ref only

svc_secret_injection_boundary
  -> owning workload only
```

Topology notes:

- `svc_ui` may be a static UI distribution boundary or a frontend workload.
  It does not call connectors, Agent Runtime, or Temporal directly.
- `svc_bff` exposes read-only workflow, support, calendar, runtime, graph, and
  future journey projections. Future mutating paths require their own ledger
  item and RBAC/approval evidence.
- `svc_temporal_worker` owns workflow activity execution but delegates
  authority-sensitive work to Agent Runtime and Tool Gateway boundaries.
- `svc_agent_runtime` resolves agent version, prompt ref, route, provider,
  budget, graph execution, and decision-trail evidence. It is the only boundary
  that may receive future provider credentials.
- `svc_tool_gateway` resolves grants, schemas, modes, approval state,
  idempotency, redaction, connector routing, verdicts, and tool audit. It is
  the only boundary that may authorise connector actions.
- `svc_connector_adapter` executes provider-specific or protocol-specific
  connector calls only after Tool Gateway decision and scoped secret injection.
- `svc_projection_worker` builds BFF/UI read models from event and audit
  sources. It does not own critical workflow state.
- `svc_observability_collector` receives safe operational telemetry and applies
  export filtering before any future managed destination.
- `svc_identity_boundary` normalises actor and workload refs if production SSO
  or workload identity is later implemented. It does not decide business
  authority by itself.
- `svc_secret_injection_boundary` resolves secret refs and injects values only
  into owning workloads. It does not expose values to workflows, prompts,
  projections, telemetry, eval fixtures, docs, or handoff records.

## Environment Model

Environment classes are bounded categories. They are not hostnames, DNS names,
account identifiers, or deployment targets.

| Environment class | Purpose | Allowed evidence | Promotion rule |
|---|---|---|---|
| `local` | Current Compose evidence path for Lighthouse, support, local connectors, OTel/Grafana, contracts, replay, and eval. | Local safe refs, fixture refs, contract samples, deterministic tests, runbook commands. | Already implemented as local evidence, not production deployment. |
| `ci` | Non-interactive contract, doctor-quick, lint, tests, replay, eval, and docs gates. | Fixture refs, gate result refs, build refs, safe service refs. | Must not require production secrets, cloud accounts, hosted exporters, or networked providers. |
| `dev` | Future isolated deployment experiment for topology or service-boundary spikes. | Synthetic tenant refs, workload refs, deployment refs, secret refs with no values. | Requires an explicit later ledger item and non-mutating or disposable evidence first. |
| `staging` | Future pre-production verification for identity, secrets, deployment, DR, retention, incidents, observability, and provider/connector hardening. | Synthetic or approved non-sensitive data refs, gate refs, rollback refs, audit refs. | Requires 2E-04 through 2E-08 artefacts as applicable before use. |
| `prod` | Future production runtime. | Opaque tenant refs, workload refs, audit refs, incident refs, backup/restore refs, deployment refs. | Requires all relevant architecture artefacts, runbooks, gates, identity, secret, DR, retention, incident, observability, and provider/connector promotion evidence. |
| `break_glass` | Exceptional time-bounded recovery or incident state. | Break-glass refs, incident refs, approval refs, expiry categories, rotation/revocation refs. | Requires incident/on-call and secret break-glass architecture plus executable audit evidence before any use. |

Environment promotion must be explicit. A passing local fixture or CI gate does
not imply that `dev`, `staging`, or `prod` exists.

## Deployment Unit Boundaries

| Deployment unit | Future workload ref | Owns | Must not own |
|---|---|---|---|
| UI distribution | `wp_ui` | Static or browser-facing UI assets and safe projection views. | Workflow state, model calls, connector calls, secrets, policy mutation. |
| BFF | `wp_bff` | Read endpoints, SSE/progress, projection aggregation, future RBAC checks. | Workflow execution, model calls, connector calls, authority decisions beyond UI access. |
| Intake adapter | `wp_intake_adapter` | External event normalisation and Temporal workflow start requests. | Business workflow decisions after start, direct connector writes. |
| Temporal server | `wp_temporal_server` | Workflow scheduling, durability, timers, activity dispatch. | Agent policy, tool grants, connector authority, audit accountability. |
| Temporal worker | `wp_temporal_worker` | Code-defined workflow and activity execution. | Non-deterministic workflow logic, direct secrets in workflow state, direct connector authority. |
| Agent Runtime | `wp_agent_runtime` | Agent registry resolution, prompt refs, model routes, provider boundary, budget, decision trail, LangGraph invocation. | Workflow state, connector action authority, policy mutation UI, direct human approval. |
| Tool Gateway | `wp_tool_gateway` | Tool grants, argument schemas, modes, approval hooks, idempotency, redaction, connector dispatch, tool audit. | Agent reasoning, model route selection, workflow state, direct UI decisions. |
| Connector adapter | `wp_connector_adapter` | Protocol or provider-specific connector execution after gateway decision. | Tool grant decisions, approval decisions, direct agent/UI ingress. |
| Projection worker | `wp_projection_worker` | Event consumption, idempotent read-model updates, projection health evidence. | Critical workflow state, business authority, connector execution. |
| Eval/replay runner | `wp_eval_runner` | Deterministic release gates, fixture execution, replay checks, gate refs. | Runtime policy mutation or production traffic handling. |
| Observability collector | `wp_observability_collector` | Safe telemetry collection, filtering, sampling, optional future export. | Audit authority, release gate authority, unfiltered raw prompt/output export. |
| Identity boundary | `wp_identity_boundary` | Actor/workload ref normalisation and future claim filtering. | Tool grants, model route decisions, connector writes, identity-provider claim persistence in projections. |
| Secret injection boundary | `wp_secret_injection` | Secret-ref resolution, lifecycle state checks, scoped value injection. | Business authority decisions, secret value persistence, prompt/tool argument injection. |

The current local implementation keeps several of these as package or activity
boundaries inside the same runtime. A future deployment may split them into
separate workloads only when service-boundary authentication, injection,
scaling, or evidence needs justify the operational cost.

## Network and Trust Zones

| Zone | Contains | Inbound | Outbound | Trust notes |
|---|---|---|---|---|
| `zone_ingress` | UI and BFF ingress boundary. | External actor refs and future identity callbacks. | BFF to application read models and identity boundary. | Only safe projection and future RBAC traffic belongs here. |
| `zone_application` | BFF, workers, Agent Runtime, Tool Gateway, projection worker, eval runner. | Internal workload calls from approved workload refs. | Calls to data, event, identity, secret injection, provider, connector, and observability boundaries as scoped. | Business authority is enforced here after authentication. |
| `zone_control_plane` | Temporal server, event stream, schema registry or equivalents. | Worker and platform workload refs. | Persistence, event, and telemetry boundaries. | Supports orchestration and visibility; does not own business authority. |
| `zone_data` | Application store, Temporal persistence, event persistence, audit/projection stores. | Approved application and platform workload refs. | Backup/restore, projection, telemetry metadata as scoped. | Stores are authoritative only for their owned data class. |
| `zone_connector` | Connector adapters and external connector egress controls. | Tool Gateway-approved adapter calls only. | External connector refs. | No direct agent, workflow, BFF, or UI access. |
| `zone_provider` | Model-provider egress controls. | Agent Runtime model adapter calls only. | External provider refs. | Provider credentials stay with Agent Runtime/model adapter boundary. |
| `zone_identity` | Future IdP binding, workload identity, actor/session ref normalisation. | BFF and workload authentication flows when promoted. | External IdP or workload identity refs. | Emits opaque refs and bounded auth categories only. |
| `zone_secret` | Future secret lookup and injection boundary. | Owning workload ref requests only. | Secret-store ref when promoted. | Secret values do not leave the owning operation. |
| `zone_observability` | Collector, telemetry stores, optional exporter boundary. | Telemetry from workloads. | Managed telemetry or sidecar refs if later promoted. | Operational and derived, never audit authority. |

## Ingress Boundaries

| Ingress path | Future owner | Allowed payload class | Required controls before implementation |
|---|---|---|---|
| Human UI/BFF access | `svc_bff` and `svc_identity_boundary` | Actor refs, session refs, tenant refs, route refs, projection filters. | Production identity/RBAC artefact, safe projection tests, no claim dumps, no mutating UI unless separately scoped. |
| External event intake | `svc_intake_adapter` | Event refs, source refs, request refs, bounded categories, redacted summary refs. | Contract schema, idempotency, tenant mapping, replay/eval path, no raw sensitive examples. |
| Approval decision ingress | Future approval boundary | Approval refs, reviewer actor refs, decision state, bounded reason category. | Approval lifecycle implementation item, RBAC, audit, Tool Gateway apply re-checks. |
| Policy proposal/review ingress | Future policy boundary | Policy-change refs, target refs, eval refs, state categories. | Policy-change implementation item, eval evidence, apply/rollback audit. |
| Operator diagnostics ingress | Future operator boundary | Runbook refs, workflow refs, trace refs, incident refs. | Incident/on-call and RBAC architecture, read-only scope by default. |

No ingress path may accept secrets, raw prompts/outputs, raw tool arguments,
raw connector payloads, identity-provider claims, credential values, host data,
or PII in public examples or local fixtures.

## Egress Boundaries

| Egress path | Only allowed caller | Allowed evidence | Required controls before implementation |
|---|---|---|---|
| Model provider call | Agent Runtime/model adapter. | Provider refs, route refs, invocation refs, credential state category, bounded failure category. | Secret-ref injection, provider hardening, rate-limit/retry policy, eval gates, rollback. |
| Connector provider call | Tool Gateway-approved connector adapter. | Connector refs, tool refs, grant refs, approval refs, idempotency refs, bounded outcome. | Tool grants, approval where required, connector hardening, secret-ref injection, redaction, compensation where applicable. |
| Identity provider call | Identity boundary. | Identity-provider ref, actor subject ref, auth method category, claim-filter result category. | Claim filtering, RBAC mapping, no token/claim persistence. |
| Secret-store lookup | Secret injection boundary. | Secret ref, lifecycle category, workload ref, policy refs. | Secret manager selection, injection tests, no value persistence, rotation/revocation evidence. |
| Managed telemetry export | Observability collector/export workload. | Allow-listed resource/span/eval fields, exporter ref, retention class. | Managed observability artefact, exporter allow-list tests, non-blocking failure proof. |
| Backup or restore operation | Future backup/restore workload. | Backup refs, restore refs, store refs, data-class categories. | 2E-04 architecture and restore drill evidence. |

## Data Store and Event Stream Placement

| Store or stream | Future placement | Authoritative for | Rebuildable from | Notes |
|---|---|---|---|---|
| Application Postgres or equivalent | `zone_data` | Agent registry, model policy materialisation, tool grants, decision trail, tool audit, approval packages, policy changes, read models, local app data. | Migrations, seeds, event stream, audit inputs depending on table. | Audit/accountability remains Postgres-owned until 2E-05 justifies a different store. |
| Temporal persistence | `zone_data` behind Temporal server. | Workflow histories, timers, retries, waits, and durable workflow state. | Not rebuilt from Redpanda; recovery uses Temporal backup/restore model. | 2E-04 must define RPO/RTO and restore order. |
| Event stream | `zone_control_plane` with persistence in `zone_data` or managed equivalent. | Projection feeds, visibility, schema-governed events. | Source stores and outbox where retained. | Not critical workflow state. |
| Schema registry | `zone_control_plane` | Event subject and compatibility evidence. | Contracts and registration process. | Must align with contract gates. |
| Telemetry stores | `zone_observability` | Operational traces, metrics, logs, dashboards. | Not authoritative; may be sampled or expired. | 2E-07 defines managed retention/export rules. |
| Eval/replay artefact store | Release evidence boundary. | Fixture, replay, and gate-result refs. | Source control and CI artefact retention. | Must avoid raw sensitive payloads. |
| Secret metadata catalogue | `zone_secret` or application audit boundary when promoted. | Secret refs, lifecycle state, owner boundary, evidence refs. | Not secret values. | 2E-02 excludes values from all docs and fixtures. |

## Component Placement Summary

| Component | Future placement | Identity ref | Secret injection | Audit/evidence |
|---|---|---|---|---|
| Temporal | `zone_control_plane` plus data persistence. | `wp_temporal_server`, `wp_temporal_worker`. | Server persistence credentials only; workflow code receives none. | Workflow history and replay evidence. |
| Agent Runtime | `zone_application`, private workload. | `wp_agent_runtime`. | Provider credentials only when provider work is promoted. | Decision trail, route refs, graph refs, eval refs. |
| Tool Gateway | `zone_application`, private workload. | `wp_tool_gateway`. | Connector or signing refs only when scoped. | Tool audit, approval package refs, idempotency refs. |
| BFF/UI | `zone_ingress` and application read boundary. | `wp_ui`, `wp_bff`. | No secret values. | Safe projections and journey refs. |
| Projection worker | `zone_application` to `zone_data`. | `wp_projection_worker`. | Store access only. | Projection lag, read-model state, event refs. |
| Connector adapters | `zone_connector`. | `wp_connector_adapter`. | Connector credential values only for authorised operation. | Connector invocation refs and bounded outcomes. |
| Observability | `zone_observability`. | `wp_observability_collector`. | Export credential only if 2E-07 promotes it. | Operational telemetry, not audit authority. |
| Identity | `zone_identity`. | `wp_identity_boundary`. | IdP credential only if identity work is promoted. | Actor/workload refs and claim-filter categories. |
| Secret injection | `zone_secret`. | `wp_secret_injection`. | Owns lookup and scoped injection. | Secret lifecycle refs, rotation/revocation refs, break-glass refs. |

## Local-to-Production Boundary

The current local stack is evidence for architecture and behaviour, not a
deployable production topology.

| Local evidence | Future production equivalent | Boundary |
|---|---|---|
| Compose workloads and local ports. | Environment-specific deployment units and private service boundaries. | No deployment resources exist until a later item opens them. |
| Local Postgres. | Application store and Temporal persistence choices. | 2E-04 and 2E-05 must define DR, retention, and audit scaling first. |
| Local Redpanda and Schema Registry. | Event stream and schema registry choice. | Event stream remains visibility/projection, not workflow authority. |
| Local Grafana/Tempo/Loki/Prometheus. | Managed or self-hosted observability choice. | 2E-07 must define exporter allow-list and retention. |
| Local Mailpit/Radicale/ticket sandbox. | Production connector adapters behind Tool Gateway. | 2E-08 must define credential refs, approval, idempotency, rate-limit, retry, and rollback before real providers. |
| Disabled provider boundary. | Production provider adapters behind Agent Runtime. | 2E-08 plus 2E-02 credential work must land before calls. |
| Seeded tenants and local refs. | Tenant/RBAC and identity model. | 2E-01 is architecture-only; executable RBAC remains future work. |
| Local environment variables. | Secret refs and scoped injection. | 2E-02 is architecture-only; no secret-manager integration exists. |

## Managed Versus Self-Hosted Decision Table

| Component | Managed option | Self-hosted option | Preferred decision rule | Must remain true either way |
|---|---|---|---|---|
| Temporal | Managed workflow service. | Self-hosted Temporal. | Prefer the option that gives the clearest replay, backup, operational visibility, and data-boundary evidence for the chosen environment. | Temporal owns workflow state; Agent Runtime and Tool Gateway keep authority. |
| Application database | Managed relational database. | Self-hosted relational database. | Prefer managed when backup, restore, patching, and availability requirements exceed local ops value. | Postgres audit semantics, RLS/tenant evidence, migrations, and restore order remain explicit. |
| Event stream | Managed event stream. | Self-hosted Kafka-compatible stream. | Prefer managed when operational burden is higher than the value of local protocol control. | Event stream is projection/visibility, not critical workflow state. |
| Schema registry | Managed schema registry. | Self-hosted registry. | Choose with the event-stream decision unless contract compatibility needs differ. | JSON Schema contracts and generated-model drift gates remain canonical. |
| BFF/UI | Managed edge/static hosting plus app workload. | Self-hosted web and BFF workloads. | Choose after identity, RBAC, and ingress controls are scoped. | UI/BFF cannot call connectors or mutate authority without separate scope. |
| Agent Runtime | Chorus-owned workload. | Chorus-owned workload. | Keep application-owned; do not outsource authority to provider SDKs. | Provider calls stay behind route, budget, eval, and credential controls. |
| Tool Gateway | Chorus-owned workload. | Chorus-owned workload. | Keep application-owned; do not replace grants with cloud IAM alone. | Every connector action is gateway-mediated and audited. |
| Connector adapters | Managed connector service where safe. | Chorus-owned adapter workloads. | Prefer the smallest adapter that preserves Tool Gateway authority and audit. | No direct agent/UI connector access; production writes require 2E-08 gates. |
| Observability | Managed telemetry backend or optional sidecar. | Self-hosted telemetry stack. | Choose after 2E-07 exporter allow-list, retention, and failure behaviour. | Postgres audit, Temporal replay, and eval remain authoritative. |
| Identity provider | Managed external identity provider. | Self-hosted identity service. | Choose after RBAC and claim-filtering requirements are explicit. | IdP authenticates; Chorus decides business authority. |
| Secret store | Managed secret store. | Self-hosted secret store. | Choose after 2E-02 follow-up artefacts define catalogue, injection, rotation, and break-glass. | Secret values never appear in docs, telemetry, projections, fixtures, eval, or audit examples. |

This table is a decision frame, not a selection. A later ADR or executable
spike must make concrete choices with evidence.

## IaC Spike Criteria

No IaC exists in 2E-03. A later IaC spike may start only when all of these are
true:

- the spike has its own ledger item, scope, non-goals, and rollback rule;
- target environment class is named with a bounded category such as `dev`;
- deployment units, workload refs, trust zones, data stores, event streams,
  identity refs, secret refs, and observability refs are mapped without values;
- 2E-01 and 2E-02 constraints are preserved;
- 2E-04 backup/restore and DR impact is known for any stateful component;
- 2E-07 exporter rules are known for any telemetry destination;
- no apply path is included unless a later item explicitly allows resource
  creation;
- generated plans, examples, logs, and docs are checked for forbidden fields;
- the spike has a deterministic teardown and cost-boundary plan;
- evidence map, runbook, phase plan, and handoff records are updated before
  the spike is called complete.

Minimum future IaC spike evidence:

| Evidence | Required shape |
|---|---|
| Topology inventory | Deployment refs, workload refs, zones, stores, streams, ingress/egress categories. |
| Policy checks | Forbidden-field scan, least-privilege review, no secret values, no public connector path. |
| Plan evidence | Non-mutating or disposable plan refs with no account IDs, hostnames, IPs, DNS names, certificate subjects, or secret values in public artefacts. |
| Gate evidence | Contracts, doctor-quick, docs alignment, plus focused IaC validation gate chosen by the spike. |
| Rollback/teardown | Teardown refs and state-store protection plan before any resource creation is allowed. |

## Evidence Expectations

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

Runtime, replay, eval, persistence, BFF/UI, frontend, Tool Gateway, connector,
provider, identity-provider, hosted observability, cloud, and deployment gates
remain skipped for 2E-03 because no runtime behaviour changes.

Future executable deployment work must add focused evidence appropriate to the
behaviour it changes:

| Future change | Minimum evidence |
|---|---|
| Split Agent Runtime or Tool Gateway into separate workloads | Service-boundary authentication tests, authority-context tests, denial-path tests, audit joins, replay/eval review. |
| Add environment promotion | Promotion checklist, environment ref audit, rollback, gate-result refs, forbidden-field scan. |
| Add network policy or ingress controls | Denial tests, allowed path tests, connector isolation evidence, runbook inspection. |
| Add managed database or event stream | Backup/restore impact, migration/runbook update, projection/event compatibility tests. |
| Add managed Temporal | Replay and history inspection, backup/restore plan, workflow worker connectivity tests. |
| Add secret injection to workloads | Injection tests, no-value persistence tests, rotation/revocation evidence, owner-boundary denial tests. |
| Add hosted telemetry export | Export allow-list tests, non-blocking failure tests, retention and sampling evidence. |
| Add connector or provider egress | Tool Gateway or Agent Runtime tests, credential-ref checks, rate-limit/retry/failure classification, eval evidence. |

## Safe Field Rules

Allowed examples and docs may use:

- stable refs: tenant, workflow, correlation, workload, workload session,
  actor session, invocation, authority context, approval, policy-change, route,
  grant, fixture, eval, incident, backup, restore, deployment, secret,
  provider, connector, event stream, store, runbook, gate, trust-domain, role,
  identity-provider, and environment refs;
- bounded categories: environment class, trust zone, workload kind, tenant
  scope, RBAC role, workflow type, task kind, tool mode, approval state,
  policy-change state, credential category, retention class, data class,
  deployment class, failure class, severity, and status;
- abstract service refs such as `svc_bff`, `svc_agent_runtime`, and
  `svc_tool_gateway`.

Forbidden everywhere in docs, examples, diagrams, plans, telemetry examples,
audit examples, eval fixtures, runbook examples, and handoff records:

- secrets, credentials, API keys, access tokens, session tokens, provider keys,
  connector credentials, database passwords, signing keys, private keys,
  certificate material, refresh tokens, cookies, or token hints;
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
  URL query strings, or configuration dumps.

## Promotion Criteria

Promote this architecture into executable deployment work only when a later
ledger item explicitly opens one of these behaviours:

- a non-mutating IaC inventory or validation spike;
- a disposable environment-class deployment experiment;
- service-boundary split for Agent Runtime, Tool Gateway, connector adapters,
  projection worker, BFF, or Temporal worker;
- workload identity enforcement for a service boundary;
- ingress/RBAC enforcement for BFF/UI;
- managed database, event stream, Temporal, observability, identity, or secret
  store evaluation;
- secret injection for a named workload boundary;
- provider or connector egress hardening;
- environment promotion, rollout, rollback, or teardown automation.

Promotion must start with the narrowest deterministic evidence path. It must
not bundle cloud resources, production SSO, identity-provider integration,
secret-manager integration, provider calls, connector writes, hosted
observability export, reviewer decisions, policy apply, ticket status
execution, or mutating admin UI unless those behaviours have their own ledger
item, evidence expectations, gates, and runbook updates.

## Backlog Implications

- `2E-04` backup, restore, and DR must use this topology to identify
  authoritative stores, rebuildable projections, event-stream durability,
  Temporal persistence, telemetry retention, and restore order.
- `2E-05` retention and audit storage must classify each topology data store
  and decide when Postgres audit remains sufficient or when another store is
  justified.
- `2E-06` incident and on-call integration must bind incident refs to
  workload refs, zones, deployment refs, secret refs, and rollback refs without
  exposing operational identifiers.
- `2E-07` managed observability must decide how `zone_observability` maps to a
  managed backend or optional sidecar while preserving audit and eval
  authority.
- `2E-08` production provider and connector hardening must use the provider
  and connector egress boundaries defined here, plus the 2E-02 secret-injection
  model.
- Any future service-boundary split for Agent Runtime, Tool Gateway, connector
  adapters, BFF, projection, or workers must add workload-principal,
  authority-context, secret-injection, audit, and runbook evidence before it is
  treated as delivered.

Until those items land, Chorus remains a local reference implementation with
deployment topology defined as architecture, not implemented behaviour.
