---
type: adr
status: accepted
date: 2026-05-19
---

# ADR 0016 - Phase 2E Production-Readiness Architecture Pack Scope

## Context

Phase 1 proved the local Lighthouse evidence slice. Phase 2A added LangGraph
inside Agent Runtime and provider-governance evidence. Phase 2B defined
identity, authority, approval, policy-change, observability, and optional
sidecar boundaries before mutating runtime controls. Phase 2C proved local
calendar connector approval, idempotency, retry, compensation, and safe
projection inspection. Phase 2D proved a second code-defined workflow through
local Support Desk Triage.

The remaining production-readiness questions are now visible, but implementing
them directly would cut across cloud identity, secrets, deployment, backup,
retention, incident response, managed observability, production providers, and
production connectors. Those concerns need an architecture pack before any
runtime implementation so the local evidence baseline stays clear.

## Decision

Phase 2E starts with a docs-first production-readiness architecture pack. The
pack scopes future artefacts and evidence expectations; it does not implement
production runtime behaviour.

The pack must cover these categories:

| Category | Scope | Required future artefacts | Evidence expectation |
|---|---|---|---|
| Production identity and IAM mapping | Map Chorus human, workload, agent, invocation, approval, and policy principals to a production identity model without moving business authority into cloud IAM. | Identity/IAM mapping doc, tenant/RBAC boundary sketch, workload-principal promotion criteria, invocation-authority binding plan, approval/policy actor mapping. | Show how local `tenant_id`, workload refs, invocation refs, approval refs, and policy-change refs map to production trust domains, IAM roles or equivalent workload identity, and application RBAC using safe refs only. |
| Secrets and credential handling | Define how provider, connector, database, signing, and observability credentials are named, stored, rotated, revoked, and injected. | Secret-ref catalogue, credential lifecycle model, rotation and break-glass runbook, local-to-production config boundary, forbidden-data checklist. | Prove that docs, contracts, samples, telemetry, audit examples, and fixtures use secret refs and bounded categories only, never secret values or credential payloads. |
| Deployment topology | Describe the production service topology and network boundaries while preserving Temporal, Agent Runtime, Tool Gateway, Postgres audit, event, and BFF ownership. | Deployment topology diagram/text, environment model, network trust boundary sketch, managed versus self-hosted component decision table, IaC spike criteria. | Distinguish local Compose evidence from future deployable topology; no Terraform, Kubernetes, AWS resources, DNS, certificates, or deployment automation until a later item explicitly opens it. |
| Backup, restore, and DR | Define RPO/RTO targets and restore responsibilities for audit, projections, workflow state, event streams, configs, and eval artefacts. | Backup/restore matrix, DR runbook outline, restore drill plan, data classification and dependency order. | Identify which stores are authoritative and which can be rebuilt; future drills must use safe refs and synthetic/local data. |
| Retention and audit storage | Define retention classes for telemetry, journey projections, audit/accountability, eval/replay artefacts, approval/policy packages, and connector evidence. | Retention matrix, audit-storage scaling decision, archival/export criteria, Scylla or append-store evaluation trigger if needed. | Keep Postgres audit authoritative until volume/query evidence justifies another store; no long-retention store implementation in this ADR. |
| Incident and on-call integration | Define how production incidents, severity, escalation, change freezes, and post-incident evidence would relate to Chorus audit and eval gates. | Incident lifecycle model, severity taxonomy, on-call integration sketch, runbook index, incident-to-policy-change linkage. | Use bounded severity/status categories and incident refs only; no pager integration, alert routing, or production incident tooling is added. |
| Managed observability | Define when local Grafana/OTel evidence can map to managed telemetry backends or optional LLM sidecars. | Managed observability mapping, exporter allow-list, sampling/retention plan, sidecar promotion checklist, redaction tests if exported. | Preserve Postgres audit, Temporal replay, and `just eval` as authoritative; no hosted exporter or managed backend dependency is added by the pack. |
| Production provider or connector hardening | Define readiness gates for real provider adapters and real connector providers behind Agent Runtime and Tool Gateway. | Provider/connector hardening checklist, credential-ref requirements, rate-limit and retry model, circuit-breaker and kill-switch expectations, sandbox-to-production promotion plan. | Future provider or connector work must prove contract validation, grant enforcement, idempotency, approval, redaction, eval, replay where relevant, failure classification, and rollback before production calls or writes. |

The pack is a planning boundary. It may create ADRs, diagrams, checklists,
runbook sections, evidence-map rows, and phase-plan backlog items. It must not
create migrations, services, credentials, cloud resources, production
connectors, hosted observability exporters, mutating admin paths, reviewer
decision paths, policy apply paths, ticket status execution, production
provider calls, or runtime behaviour changes.

## Safe Data Rules

Production-readiness examples may use:

- stable refs such as tenant, workflow, correlation, workload, invocation,
  approval, policy-change, route, grant, fixture, incident, backup, restore,
  deployment, secret, provider, connector, and runbook refs;
- bounded categories such as severity, status, trust domain, workload kind,
  data class, retention class, failure class, decision state, and environment
  class;
- synthetic local identifiers already safe under the Phase 2B field-placement
  rules.

Production-readiness examples must not include secrets, credentials, API keys,
access tokens, session tokens, signing keys, raw sensitive content, raw
prompts, raw model outputs, raw tool arguments, raw connector payloads, raw
approval or policy rationale, identity-provider claims, names, email
addresses, IP addresses, hostnames, filesystem paths, local account material,
or PII.

## Backlog Shape

Phase 2E should remain ordered around architecture artefacts before executable
spikes:

| Item | Future artefact | Promotion trigger |
|---|---|---|
| `2E-01` | Production identity and IAM mapping architecture | Required before production SSO, workload identity enforcement, or tenant/RBAC implementation. |
| `2E-02` | Secrets and credential handling architecture | Required before credential entry, secret-manager integration, provider credentials, connector credentials, or signing keys. |
| `2E-03` | Deployment topology architecture | Required before IaC, cloud resources, Kubernetes/ECS/EKS/Lambda deployment work, DNS, certificates, or environment promotion. |
| `2E-04` | Backup, restore, and DR architecture | Required before backup automation, restore drills, replication, PITR policy, or production runbook claims. |
| `2E-05` | Retention and audit storage architecture | Required before long-retention stores, archive/export jobs, Scylla or append-store work, or retention mutation. |
| `2E-06` | Incident and on-call integration architecture | Required before alert routing, pager integration, incident workflows, change freezes, or post-incident policy-change automation. |
| `2E-07` | Managed observability architecture | Required before hosted telemetry exporters, managed Grafana/Tempo/Loki/Prometheus mapping, CloudWatch or equivalent mapping, or sidecar export code. |
| `2E-08` | Production provider and connector hardening architecture | Required before real provider calls, production connector providers, production connector writes, credential-backed adapters, or provider/connector promotion. |

Each future item must state its scope, non-goals, safe field set, required
artefacts, gates, and skipped runtime gates. Executable spikes require their
own later ledger item and must include focused tests plus evidence-map and
runbook updates before they are called complete.

## Non-Goals

This ADR does not add:

- AWS, production SSO, production identity-provider integration, or production
  IAM enforcement;
- production cloud deployment, IaC, DNS, certificates, managed databases, or
  network resources;
- credential entry, credential mutation, secret-manager integration, provider
  credentials, connector credentials, or signing keys;
- production provider calls or production connector writes;
- hosted observability exporters, managed observability dependencies, or LLM
  sidecar export code;
- backup automation, restore automation, DR infrastructure, long-retention
  audit stores, or archival jobs;
- incident tooling, pager routing, alert routing, or on-call integrations;
- reviewer decision UI, mutating admin UI, policy mutation UI, or policy apply
  paths;
- ticket status execution, generic workflow DSL work, or a top-level agent
  framework replacing Temporal.

## Consequences

- Phase 2E has an explicit production-readiness boundary before code.
- Production readiness is decomposed into inspectable architecture artefacts
  instead of one broad hardening epic.
- Phase 1 Lighthouse and Phase 2D Support Desk Triage remain local evidence
  baselines while production topics are scoped.
- Future executable spikes must show their authority, data, and evidence gates
  before they add runtime behaviour.
- The project can discuss production deployment, IAM, secrets, retention, DR,
  incidents, managed observability, and provider/connector hardening without
  implying that any of those capabilities are implemented.

## Alternatives Considered

### Start With AWS or Production Deployment

Rejected. It would force credentials, cloud resources, IAM, network, and
operational decisions before Chorus has a scoped production architecture pack.

### Add Production Provider or Connector Calls First

Rejected. Real providers and connectors require secret handling, incident
response, rate limits, approval, policy promotion, eval gates, and rollback
before they are credible production work.

### Treat Production Readiness as One Implementation Epic

Rejected. The categories have different evidence owners and risk profiles.
Combining them would make it hard to tell which production claim is supported
by architecture, local evidence, or executable code.

### Leave Production Readiness as Generic Deferrals

Rejected. Phase 1 and earlier Phase 2 work already name production deferrals.
Phase 2E must now shape those deferrals into an ordered architecture backlog
without pretending they are implemented.
