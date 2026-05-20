---
type: project-doc
status: planning
date: 2026-05-19
---

# Secrets and Credential Handling Architecture

## Purpose

This document is the Phase 2E-02 docs-first architecture artefact promised by
[ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md). It
defines how future Chorus work should name, store, inject, rotate, revoke,
audit, and break-glass provider, connector, database, signing,
identity-provider, observability, and workload identity credentials using
secret refs and bounded categories only.

This is architecture-only. It does not add a secret manager, credential entry,
credential mutation, actual credentials, provider keys, connector credentials,
signing keys, identity-provider client secrets, cloud resources, production
SSO, production identity-provider integration, IAM enforcement, production
connectors, hosted observability exporters, production provider calls,
migrations, services, runtime enforcement changes, or runtime behaviour
changes.

## Source Boundaries

This artefact composes existing Phase 2 identity, authority, approval, policy,
observability, and production-readiness models:

| Source | Provides |
|---|---|
| [ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md) | Principal vocabulary, authentication versus business authority, and context hygiene. |
| [ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md) | Phase 2E scope, non-goals, safe-data rules, and ordered production-readiness backlog. |
| [observability-user-journey-model.md](observability-user-journey-model.md) | Field placement rules for telemetry, baggage, projections, and audit. |
| [workload-principal-model.md](workload-principal-model.md) | Workload principal, workload session, trust-domain, and future workload identity refs. |
| [invocation-authority-context.md](invocation-authority-context.md) | Invocation and tool-authority context fields that may later reference signing or workload identity refs. |
| [human-approval-audit-lifecycle.md](human-approval-audit-lifecycle.md) | Approval package refs, reviewer actor refs, and Tool Gateway apply re-check expectations. |
| [policy-change-governance-workflow.md](policy-change-governance-workflow.md) | Governed policy-change refs, eval evidence refs, apply and rollback refs. |
| [llm-observability-sidecar-evaluation.md](llm-observability-sidecar-evaluation.md) | Optional sidecar export constraints and forbidden data rules. |
| [production-identity-iam-mapping.md](production-identity-iam-mapping.md) | Production trust domains, workload role refs, identity-provider refs, STS tag rules, and promotion boundaries. |

## Scope

2E-02 defines:

- credential categories and ownership boundaries;
- secret-ref naming rules and catalogue shape;
- local-to-production configuration boundary;
- runtime injection boundaries for Agent Runtime, Tool Gateway, connector
  adapters, persistence, observability exporters, signing, identity providers,
  and workload identity material;
- rotation, revocation, expiry, and replacement lifecycle;
- break-glass controls and audit refs;
- audit/evidence refs and safe field rules;
- forbidden data checklist;
- required future artefacts before executable secret handling;
- evidence expectations, promotion criteria, and backlog implications.

## Non-Goals

This item does not add:

- secret-manager integration, credential entry, credential mutation, or
  credential storage;
- provider keys, connector credentials, database credentials, signing keys,
  identity-provider client secrets, access tokens, session tokens,
  certificate material, or workload identity material;
- AWS, production cloud resources, IAM enforcement, production SSO,
  identity-provider integration, production connectors, hosted observability
  exporters, or production provider calls;
- new migrations, services, contracts, runtime enforcement, BFF/UI routes,
  admin mutation paths, reviewer decision paths, policy apply paths, ticket
  status execution, eval fixtures, replay histories, or workflow behaviour.

## Design Rules

- Secret values never appear in Git, docs, contracts, samples, fixtures,
  telemetry, projections, eval output, audit examples, sidecar exports, or
  handoff records.
- Agents never receive credentials, secret refs that imply direct connector
  access, signing material, cloud credentials, or workload identity material.
- Secret refs are opaque identifiers. They may be stored or audited as refs;
  secret values, token payloads, certificate material, and credential state
  are excluded.
- Chorus business authority remains in Agent Runtime, Tool Gateway, approval
  audit, policy-change audit, and eval gates. Possession of a secret value or
  workload credential does not authorise a business action.
- Runtime injection is component-scoped. A workload receives only the secret
  refs and injected values required for its boundary.
- Rotation and revocation are authority-sensitive operations. Future
  executable work must require proposal, approval where appropriate,
  idempotent apply, rollback or replacement evidence, and append-only audit.
- Break-glass access is exceptional, time-bounded, separately audited, and
  never an invisible bypass of Tool Gateway, Agent Runtime, approval,
  policy-change, or eval controls.

## Credential Categories

| Category | Future examples by boundary | Owner | Primary risk | Safe refs allowed |
|---|---|---|---|---|
| Provider credential | Model provider API credential used by a model adapter. | Agent Runtime provider boundary. | Production provider calls or provider data exposure. | `secret_ref`, `provider_ref`, `route_ref`, `credential_category`. |
| Connector credential | Calendar, ticket, email, CRM, or other connector credential. | Tool Gateway and connector adapter boundary. | Connector writes outside gateway authority. | `secret_ref`, `connector_ref`, `tool_ref`, `mode_category`. |
| Database credential | Application or migration database credential. | Persistence and platform workload boundary. | Store access beyond intended workload scope. | `secret_ref`, `store_ref`, `workload_principal_ref`, `environment_class`. |
| Signing credential | Future key used for authority envelopes, approval packages, policy packages, webhook verification, or release evidence. | Signing service or effectful activity boundary. | Forged authority or unverifiable provenance. | `secret_ref`, `key_ref`, `signing_purpose`, `key_state`. |
| Identity-provider credential | Future client secret, assertion credential, or token exchange credential. | Identity binding boundary. | Actor impersonation or claim ingestion leakage. | `secret_ref`, `identity_provider_ref`, `trust_domain_ref`, `credential_category`. |
| Observability credential | Future managed telemetry or optional sidecar exporter credential. | OTel collector or export workload boundary. | Export leakage or hosted dependency drift. | `secret_ref`, `exporter_ref`, `destination_category`, `retention_class`. |
| Workload identity material | Future workload certificate, token exchange material, or identity bootstrap credential. | Workload identity boundary. | Workload impersonation and cross-boundary access. | `secret_ref`, `workload_principal_ref`, `trust_domain_ref`, `identity_mechanism`. |

The current local implementation has provider and connector placeholders that
may carry secret-ref metadata for disabled or local-only evidence. Those refs
are not credentials and do not enable production calls.

## Secret-Ref Naming Rules

Secret refs are stable opaque identifiers. They identify where a future secret
value is stored, not the value itself.

Allowed ref pattern:

```text
sec_<category>_<purpose>_<environment-class>_<version-ref>
```

Example safe refs:

```text
sec_provider_primary_prod_v001
sec_connector_calendar_prod_v001
sec_database_app_prod_v001
sec_signing_authority_prod_v001
sec_idp_client_prod_v001
sec_observability_export_prod_v001
sec_workload_identity_prod_v001
```

Rules:

| Part | Rule |
|---|---|
| `category` | One of `provider`, `connector`, `database`, `signing`, `idp`, `observability`, or `workload_identity`. |
| `purpose` | Bounded purpose label such as `primary`, `calendar`, `app`, `authority`, `client`, or `export`. |
| `environment-class` | Bounded class such as `local`, `ci`, `dev`, `staging`, or `prod`. |
| `version-ref` | Opaque monotonic ref such as `v001`; not a timestamp derived from host, actor, or customer data. |

Do not encode provider account IDs, tenant names, actor names, hostnames, IP
addresses, filesystem paths, email addresses, raw route IDs containing
sensitive text, ticket or customer content, credential values, token prefixes,
certificate subjects, cloud account IDs, full ARNs, external IDs, or policy
rationale into secret refs.

## Secret-Ref Catalogue Shape

A future secret-ref catalogue should be metadata only. It should never store a
secret value or credential payload.

```text
secret_ref_catalogue
  schema_version
  secret_ref
  credential_category          -- provider | connector | database | signing | idp | observability | workload_identity
  purpose_category             -- bounded purpose label
  environment_class            -- local | ci | dev | staging | prod
  trust_domain_ref
  owner_boundary               -- agent_runtime | tool_gateway | connector_adapter | persistence | identity | observability | workload_identity | signing
  allowed_workload_principal_refs
  allowed_component_refs
  tenant_scope_kind            -- none | all_tenants | tenant_allow_list
  tenant_refs                  -- nullable safe refs only
  provider_ref                 -- nullable
  connector_ref                -- nullable
  store_ref                    -- nullable
  identity_provider_ref        -- nullable
  exporter_ref                 -- nullable
  signing_purpose              -- nullable bounded category
  rotation_state               -- planned | active | rotating | rotated | revoked | expired | break_glass_active | retired
  version_ref
  previous_secret_ref          -- nullable
  next_secret_ref              -- nullable
  rotation_policy_ref
  revocation_policy_ref
  break_glass_policy_ref
  evidence_refs
  created_at
  activated_at                 -- nullable
  expires_at                   -- nullable
  retired_at                   -- nullable
  metadata                     -- safe bounded labels only
```

Field rules:

| Field family | Rule |
|---|---|
| Identity | `secret_ref` is opaque and generated from bounded labels. Do not derive it from a credential value or external account identifier. |
| Category and purpose | Use bounded categories. Free-text rationale and credential payload details are excluded. |
| Owner boundary | Names the component boundary allowed to request injection or lookup. It does not grant business authority. |
| Workload allow-list | Store workload principal refs and component refs. Do not store service tokens, cloud role policies, or credential material. |
| Tenant scope | Use `none`, `all_tenants`, or `tenant_allow_list`. Tenant refs must be stable application refs only. |
| External mapping refs | Provider, connector, store, IdP, exporter, signing, or workload identity refs may appear as opaque refs only. |
| Lifecycle | Store lifecycle categories, previous/next refs, and policy refs. Do not store old or new secret values. |
| Evidence refs | Link to approval, policy-change, runbook, gate, incident, rotation, revocation, and audit refs. |
| Metadata | Safe bounded labels only. No environment payloads, request headers, local paths, URLs, token hints, or free text. |

## Local-to-Production Configuration Boundary

Local configuration can continue to use local environment injection for the
current sandbox. That is an implementation convenience, not a production
credential architecture.

| Concern | Current local boundary | Future production boundary |
|---|---|---|
| Local sandbox credentials | Local development configuration may provide sandbox defaults or disabled-provider refs. | Managed secret store or equivalent injects component-scoped values at runtime. |
| Provider credentials | Disabled placeholder only; no production provider call path. | Provider adapters receive injected credential values only through Agent Runtime provider boundary. |
| Connector credentials | Local connectors use sandbox/local configuration. Production connector credentials are absent. | Tool Gateway or connector adapters receive injected values only after gateway-owned authority checks. |
| Database credentials | Local database settings support the Compose evidence path. | Workload-scoped database credentials or managed identity are injected into persistence workloads only. |
| Signing keys | No signing key path. | Signing boundary receives injected key material and exposes only key refs to callers and audit. |
| Identity-provider credentials | No production identity-provider path. | Identity binding boundary receives injected client or assertion credential and emits only actor/IdP refs. |
| Observability exporter credentials | No hosted exporter path. | Collector/export workload receives exporter credential through an opt-in allow-list with redaction tests. |
| Workload identity material | No executable workload identity material. | Workload identity bootstrap happens before Chorus business logic and emits workload refs only. |

Production promotion must not treat local environment values, local default
credentials, or disabled-provider metadata as evidence that secret handling is
implemented. The promotion boundary is crossed only when a later ledger item
adds a real secret-ref catalogue, injection mechanism, redaction tests,
rotation or revocation evidence, and runbook procedures.

## Runtime Injection Boundaries

Credential injection belongs at effectful service boundaries, not in workflows,
prompts, projections, or UI responses.

| Runtime boundary | May receive injected value in future | May persist or expose |
|---|---|---|
| Temporal workflow code | No. | Safe refs already in workflow state only. |
| Temporal activities | Only when the activity is the owning effectful boundary. | Secret refs and bounded evidence refs only. |
| Agent Runtime | Provider credentials for selected provider boundary. | Secret refs, provider refs, route refs, credential state category, failure category. |
| Model adapter | Provider credential value only for the call it owns. | No values; return bounded provider outcome and safe usage metadata. |
| Tool Gateway | Connector or signing credential refs needed to enforce authority and route to an adapter. | Secret refs, grant refs, approval refs, idempotency refs, verdict categories. |
| Connector adapter | Connector credential value only after gateway allow or approved apply. | No values; return connector invocation ref and bounded outcome. |
| Persistence workload | Database credential or managed identity for store access. | Workload refs, store refs, migration/run refs, bounded status. |
| BFF/UI | No secret values. | Safe projection refs only; no secret refs unless a read-only operator view is explicitly scoped later. |
| OTel collector or export workload | Export credential only for explicitly configured destination. | Exporter ref, destination category, retention class, failure category. |
| Signing boundary | Signing key material only inside signing operation. | Key ref, algorithm category, issued/expiry refs, signature refs where scoped. |
| Identity binding boundary | IdP credential only inside token exchange or claim filtering operation. | IdP ref, actor subject ref, trust-domain ref, auth method category. |

Injection rules:

1. Resolve the secret ref from approved configuration or future policy-change
   evidence before injection.
2. Verify the requesting workload principal, component boundary, tenant scope,
   environment class, secret category, and lifecycle state.
3. Inject the value only into the owning process or operation. Do not forward
   it through Temporal workflow state, OTel baggage, prompts, tool arguments,
   connector payload examples, BFF responses, eval fixtures, or logs.
4. Persist only secret refs, version refs, lifecycle categories, and evidence
   refs.
5. Classify missing, expired, revoked, denied, or rotated credentials with
   bounded failure categories.

## Rotation and Revocation Lifecycle

Secret rotation is a controlled replacement of one secret ref with another.
Secret revocation removes authority to use a secret ref.

```text
planned
  -> active
  -> rotating
  -> rotated
  -> retired

active
  -> revoked

active
  -> expired

active
  -> break_glass_active
  -> rotated | revoked | retired
```

Lifecycle rules:

| State | Meaning | Runtime behaviour expected in future |
|---|---|---|
| `planned` | Ref exists but is not valid for injection. | Runtime must not use it. |
| `active` | Ref is valid for the owning boundary. | Runtime may inject only for allowed workloads and categories. |
| `rotating` | Old and next refs overlap under a bounded window. | Runtime may use both only where the rotation policy allows. |
| `rotated` | New ref has replaced the old ref. | Runtime should use `next_secret_ref`; old ref moves toward retirement. |
| `revoked` | Ref must not be used. | Runtime denies injection and records bounded revocation evidence. |
| `expired` | Ref passed its validity window. | Runtime denies injection and records bounded expiry evidence. |
| `break_glass_active` | Exceptional temporary access is active. | Runtime may inject only under break-glass policy and audit refs. |
| `retired` | Ref is retained only as evidence. | Runtime denies injection. |

Future rotation evidence should include:

- `rotation_request_ref`;
- `policy_change_ref` when a policy mutation is required;
- `approval_ref` when human approval is required;
- `previous_secret_ref` and `next_secret_ref`;
- workload principal refs affected;
- category, environment class, and trust-domain refs;
- rotation window category;
- verification gate refs;
- rollback or replacement refs;
- bounded outcome and failure categories.

Future revocation evidence should include:

- `revocation_request_ref`;
- `secret_ref`;
- revocation reason category;
- affected boundary and workload refs;
- dependent route, connector, store, IdP, exporter, or signing refs;
- verification gate refs;
- incident or break-glass refs where applicable;
- bounded outcome and failure categories.

Do not store old values, new values, token prefixes, certificate bodies,
subject DNs, raw provider responses, raw connector responses, or unbounded
operator rationale in rotation or revocation records.

## Break-Glass Controls

Break-glass is exceptional temporary credential access for incident response or
urgent recovery. It must be explicit, narrow, and auditable.

Required controls before executable break-glass work:

| Control | Requirement |
|---|---|
| Break-glass request | Opaque `break_glass_ref`, tenant or environment scope, credential category, owner boundary, reason category, expiry, and requester actor/workload refs. |
| Approval | Approval ref or documented emergency policy ref before injection where the incident model requires it. |
| Time limit | Short expiry category and automatic denial after expiry. |
| Scope limit | One credential category, one owner boundary, and bounded tenant/environment scope. |
| Dual evidence | Append-only break-glass audit plus follow-up policy or incident evidence refs. |
| Rotation follow-up | Required rotation or revocation ref after use where the credential class is sensitive. |
| Projection | Safe operator status only: active, expired, revoked, rotated, or reviewed. |

Break-glass does not let an agent bypass the Tool Gateway, let a reviewer call
a connector directly, let a policy actor mutate active policy without an apply
path, or let a workload call a production provider outside Agent Runtime.

## Audit and Evidence Refs

Credential evidence belongs in audit/accountability records and runbook/gate
evidence, not telemetry baggage.

Allowed audit/evidence refs:

- `secret_ref`;
- `secret_version_ref`;
- `credential_category`;
- `owner_boundary`;
- `workload_principal_ref`;
- `workload_session_ref`;
- `trust_domain_ref`;
- `provider_ref`;
- `connector_ref`;
- `store_ref`;
- `identity_provider_ref`;
- `exporter_ref`;
- `key_ref`;
- `rotation_request_ref`;
- `revocation_request_ref`;
- `break_glass_ref`;
- `approval_ref`;
- `policy_change_ref`;
- `incident_ref`;
- `runbook_ref`;
- `gate_result_ref`;
- `trace_join_ref`;
- bounded lifecycle, reason, status, and failure categories.

Placement:

| Plane | Allowed credential fields | Excluded fields |
|---|---|---|
| OTel resource attributes | No secret refs by default. Workload principal and trust-domain fields remain allowed under the 2B workload model. | Secret refs, values, credential state, provider keys, connector credentials, tokens, certificate material. |
| OTel span attributes | Bounded missing/expired/revoked category only when needed for operational diagnosis. | Secret refs by default, credential values, token hints, raw provider/connector errors. |
| OTel baggage | None beyond the existing tenant/correlation/workflow/actor-session/fixture allow-list. | Secret refs, credential categories, lifecycle state, authority refs, values. |
| Postgres projections and BFF/UI | Safe status refs only if a future read-only operator view is explicitly scoped. | Secret values, token hints, certificate material, raw external identifiers, full credential catalogue rows. |
| Audit/accountability | Secret refs, lifecycle events, owner boundary, affected workload refs, approval/policy/incident refs, gate refs, bounded reason and outcome categories. | Credential values, access tokens, private keys, certificate bodies, raw claims, raw payloads, free-text rationale. |
| Eval/replay artefacts | Gate refs and bounded assertions that values are absent. | Credential values, raw injected config, raw external calls, raw secrets. |

## Forbidden Data Checklist

The following must never appear in docs, contracts, samples, fixtures,
telemetry, projections, sidecar exports, audit examples, eval output,
runbook examples, or continuation records:

- secrets, credentials, API keys, access tokens, session tokens, provider keys,
  connector credentials, database passwords, signing keys, private keys,
  certificate material, refresh tokens, cookies, or token hints;
- raw sensitive content, customer content, raw prompts, raw model outputs, raw
  tool arguments, raw connector payloads, raw retrieval documents, file
  contents, raw request or response bodies, raw approval rationale, raw policy
  rationale, policy diff bodies, or unbounded exception text;
- identity-provider claim dumps, profile data, names, email addresses, group
  claim payloads, hostnames, IP addresses, filesystem paths, local account
  material, cloud account IDs, full ARNs, external IDs, raw certificate
  subjects, raw SPIFFE IDs, or PII;
- environment payloads, command lines, request headers, full user-agent
  strings, URL query strings, or configuration dumps that may carry secrets.

If a future executable change needs one of these fields for a private
production record, it must be scoped in a separate private artefact and kept
out of public docs, local fixtures, telemetry, projections, sidecar exports,
and handoff records.

## Required Future Artefacts

Before any executable secret-manager, credential, signing, identity-provider,
observability exporter, provider, connector, database, or workload identity
work, add:

| Artefact | Required content |
|---|---|
| Secret-ref catalogue schema | Metadata-only fields, category allow-list, lifecycle state, workload allow-list, forbidden fields, and redaction rules. |
| Secret-store selection ADR | Local-to-production store options, ownership, operational model, non-goals, and migration path. |
| Injection boundary matrix | Which workload receives which category, under which owner boundary and tenant/environment scope. |
| Rotation and revocation runbook | Request, approval, apply, rollback, expiry, verification, failure categories, and evidence refs. |
| Break-glass runbook | Emergency scope, approval/incident refs, expiry, follow-up rotation, audit events, and forbidden data rules. |
| Redaction and forbidden-field tests | Deterministic checks over docs examples, contracts, fixtures, telemetry/export samples, and audit examples. |
| Provider credential plan | Secret refs, route refs, adapter boundary, rate-limit and failure categories, and eval promotion gate before provider calls. |
| Connector credential plan | Secret refs, Tool Gateway grants, approval, idempotency, redaction, connector sandbox-to-production criteria, and rollback. |
| Signing key plan | Key refs, algorithm category, authority envelope scope, expiry, rotation, verification, and no key-material persistence. |
| Identity-provider credential plan | IdP refs, client credential refs, claim filtering, actor-subject refs, RBAC refs, audit retention, and no claim dumps. |
| Observability exporter credential plan | Exporter refs, destination category, redaction allow-list, retention, sampling, failure non-blocking proof, and no hosted dependency by default. |
| Workload identity material plan | Workload refs, trust-domain refs, identity mechanism, bootstrap boundary, rotation, revocation, and no direct agent access. |

## Evidence Expectations

For this docs-first item, evidence is the artefact itself plus phase-plan,
architecture, evidence-map, implementation-plan, runbook, and handoff
alignment. The expected gates are:

```bash
just contracts-check
just doctor-quick
git diff --check
```

The smallest additional relevant gate is a docs alignment search that proves
the new artefact is linked from the Phase 2 ledger, architecture, evidence map,
implementation plan, runbook, and continuation records.

Future executable work must add focused tests for the behaviour it changes:

| Future change | Minimum evidence |
|---|---|
| Secret-ref catalogue persistence | Migration, safe seeds, forbidden-field tests, persistence tests, runbook inspection. |
| Secret-manager integration | Injection tests, denial tests, redaction tests, lifecycle tests, no value persistence tests. |
| Provider credential injection | Agent Runtime adapter tests, disabled/missing/revoked credential tests, eval gate review before production calls. |
| Connector credential injection | Tool Gateway and connector tests, grant and approval re-check tests, no direct connector access tests. |
| Database credential rotation | Persistence workload tests, migration/runbook evidence, rollback or replacement evidence. |
| Signing key use | Canonical payload tests, key-ref tests, signature verification tests, no key-material persistence tests. |
| Identity-provider credential use | Claim filtering tests, actor-subject ref tests, no token/claim dump tests, RBAC denial tests. |
| Observability exporter credential use | Export allow-list tests, forbidden-field tests, non-blocking exporter failure tests. |
| Workload identity material use | Workload authentication tests, boundary denial tests, audit join tests, no agent credential access tests. |
| Break-glass path | Expiry tests, scope tests, audit tests, mandatory follow-up rotation or revocation evidence. |

Runtime, replay, eval, persistence, BFF/UI, frontend, Tool Gateway, connector,
provider, identity-provider, hosted observability, and cloud gates remain
skipped for 2E-02 because no runtime behaviour changes.

## Promotion Criteria

Promote this architecture into executable implementation only when a later
ledger item explicitly opens one of these behaviours:

- secret-ref catalogue persistence;
- managed secret-store or equivalent integration;
- provider credential injection for a real provider adapter;
- connector credential injection for a real connector provider;
- database credential rotation or managed identity;
- signing key use for invocation, approval, policy, webhook, or release
  evidence;
- identity-provider client credential or assertion credential use;
- hosted observability exporter credential use;
- workload identity material bootstrap, rotation, or revocation;
- break-glass credential access.

Promotion must start with the narrowest local deterministic evidence path and
must update docs, tests, evidence map, runbook, and phase plan before it is
called complete. It must not bundle production SSO, cloud deployment, provider
calls, connector writes, hosted observability, tenant-admin UI, reviewer
decision UI, policy apply, or ticket status execution unless those behaviours
have their own ledger item, evidence expectations, and gates.

## Backlog Implications

- `2E-03` deployment topology must decide where secret injection boundaries
  live before any cloud resource, IaC, network, DNS, or certificate work.
- `2E-04` backup, restore, and DR must classify secret metadata separately
  from secret values and define restore order without restoring revoked
  credentials.
- `2E-05` retention and audit storage must define retention for secret-ref
  lifecycle audit, rotation evidence, revocation evidence, and break-glass
  evidence without retaining values.
- `2E-06` incident and on-call integration must bind incident refs to
  break-glass, rotation, and revocation evidence.
- `2E-07` managed observability must preserve the exporter credential boundary
  and forbidden-field tests before any hosted telemetry or sidecar export.
- `2E-08` production provider and connector hardening must require secret refs,
  injection boundaries, rotation/revocation expectations, Tool Gateway and
  Agent Runtime authority checks, approval/idempotency/redaction, eval gates,
  and rollback before real provider calls or connector writes.

Until those items land, Chorus remains a local reference implementation with
secrets and credential handling defined as architecture, not implemented
behaviour.
