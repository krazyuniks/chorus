---
type: project-doc
status: planning
date: 2026-05-19
---

# Production Identity and IAM Mapping Architecture

## Purpose

This document is the Phase 2E-01 docs-first architecture artefact promised by
[ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md). It
extends the Phase 2B identity and authority models without implementing
production SSO, AWS, cloud deployment, identity-provider integration,
credential handling, or runtime enforcement.

The goal is to show how Chorus principals would map to production trust
domains, tenant and RBAC boundaries, AWS IAM roles or equivalent workload
identity, STS session names and tags, IAM Roles Anywhere, SPIFFE/SPIRE, and
external identity-provider references while preserving Chorus business
authority in the existing application control planes.

This is architecture-only. No migration, contract, service, seed, credential,
cloud resource, hosted exporter, admin UI, reviewer decision path, policy apply
path, production connector, provider call, or runtime behaviour change is
added by this item.

## Source Boundaries

This artefact composes existing docs-first models:

| Source | Provides |
|---|---|
| [ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md) | Principal vocabulary and the authentication versus business-authority split. |
| [ADR 0016](../adrs/0016-production-readiness-architecture-pack-scope.md) | Phase 2E production-readiness scope, non-goals, safe-data rules, and backlog order. |
| [workload-principal-model.md](workload-principal-model.md) | Local workload principals, workload sessions, trust domains, and future IAM mapping fields. |
| [invocation-authority-context.md](invocation-authority-context.md) | Invocation and tool-authority context fields owned by Agent Runtime and Tool Gateway. |
| [human-approval-audit-lifecycle.md](human-approval-audit-lifecycle.md) | Approval package identity, reviewer actor refs, approval state, and audit lifecycle. |
| [policy-change-governance-workflow.md](policy-change-governance-workflow.md) | Policy actor refs, policy-change package state, eval evidence refs, apply and rollback refs. |
| [observability-user-journey-model.md](observability-user-journey-model.md) | Field-placement rules for OTel attributes, baggage, projections, and audit records. |

## Scope

2E-01 defines:

- production trust-domain categories and safe refs;
- how human, workload, agent, invocation, approval, and policy principals map
  to production authentication and authorisation surfaces;
- tenant and application RBAC boundaries;
- workload role and session mapping to AWS IAM roles or equivalent workload
  identity;
- safe STS session-name and session-tag rules;
- IAM Roles Anywhere, SPIFFE/SPIRE, and external identity-provider reference
  placement;
- required future artefacts before production SSO, workload identity
  enforcement, or tenant/RBAC implementation;
- evidence expectations, safe field rules, promotion criteria, and backlog
  implications.

## Non-Goals

This item does not add:

- AWS accounts, IAM roles, policies, STS calls, IAM Roles Anywhere resources,
  SPIFFE/SPIRE services, cloud resources, IaC, DNS, certificates, or deployment
  automation;
- production SSO, OIDC/SAML integration, identity-provider claim ingestion,
  tenant-admin UI, actor-session persistence, or RBAC enforcement;
- credential entry, credential mutation, secret-manager integration, provider
  credentials, connector credentials, signing keys, access keys, session
  tokens, or certificate material;
- runtime enforcement changes in Agent Runtime, Tool Gateway, BFF, Temporal,
  approval, policy-change, provider, connector, persistence, eval, or UI code;
- production provider calls, production connector writes, hosted
  observability exporters, reviewer decision paths, policy apply paths, or
  ticket status execution.

## Authority Split

Production identity must not move Chorus business authority into IAM.

| Plane | Purpose | Production mapping | Chorus boundary that remains authoritative |
|---|---|---|---|
| Human authentication | Proves a person or automation subject has authenticated. | External IdP, OIDC/SAML, IAM Identity Center, or equivalent subject ref. | BFF and future approval/policy workflows decide application role use from opaque actor refs. |
| Workload authentication | Proves a service, worker, connector, or automation workload is the caller. | IAM role, EKS pod identity, ECS task role, Lambda execution role, EC2 instance profile, IAM Roles Anywhere, SPIFFE/SPIRE, or equivalent. | Agent Runtime and Tool Gateway still enforce business policy after caller identity is known. |
| Cloud/resource authorisation | Limits infrastructure and cloud-resource access. | IAM policies, permission sets, network policy, service account policy, or equivalent. | Does not decide whether an agent may call a tool, change a route, approve a package, or write a connector. |
| Chorus business authority | Decides whether a tenant, agent version, invocation, route, budget, tool mode, approval state, and policy version allow the action. | May be reflected into safe session tags or audit refs. | Agent Runtime, Tool Gateway, approval audit, policy-change audit, and eval/replay gates. |
| Evidence and accountability | Proves what was authorised and why. | May join to safe identity refs and trace IDs. | Postgres decision trail, Tool Gateway audit, approval audit, policy-change audit, projections, replay, and eval. |

## Production Trust Domains

Trust domains are bounded labels used to avoid mixing local, production,
external, and hybrid identities. They are not secrets and must come from an
allow-list.

| Trust-domain category | Safe ref example | Contains | Does not contain |
|---|---|---|---|
| Local runtime | `td_local_chorus` | Compose or host-local workload/session refs. | Hostnames, local usernames, filesystem paths, IP addresses. |
| Fixture and CI | `td_fixture_chorus` | Eval, replay, and CI automation refs. | CI secrets, repository tokens, raw command lines. |
| Production application | `td_prod_app` | BFF, Agent Runtime, Tool Gateway, worker, projection, connector workload refs. | Cloud account IDs, role ARNs as examples, credential values. |
| Production platform | `td_prod_platform` | Temporal, event, database, telemetry, and platform service refs. | Managed-service credentials or admin claims. |
| External identity provider | `td_external_idp` | Opaque IdP and actor subject refs. | Claim dumps, group names, email addresses, personal names. |
| Hybrid workload | `td_hybrid_workload` | IAM Roles Anywhere profile refs, certificate subject refs, or SPIFFE ID refs. | Certificate bodies, private keys, raw SPIFFE documents. |

Production records may later store concrete provider-specific identifiers in
secure configuration or identity tables. Public docs, samples, fixtures,
telemetry, and eval evidence should use the safe refs above or equivalent
opaque refs, not account IDs, hostnames, ARNs, certificates, or claims.

## Tenant and RBAC Boundary

`tenant_id` remains the application tenant boundary. IAM can help isolate
workloads and resources, but tenant authorisation is still a Chorus policy
decision.

Future production RBAC should use opaque actor refs and bounded roles:

| Role category | Safe role ref | Can do when implemented | Cannot do |
|---|---|---|---|
| Tenant reader | `role_tenant_reader` | Read safe BFF projections for authorised tenant refs. | Approve actions, mutate policy, call connectors directly. |
| Workflow reviewer | `role_workflow_reviewer` | Inspect workflow, decision, gateway, eval, and journey evidence. | Execute Tool Gateway writes or alter route/grant policy. |
| Approval reviewer | `role_approval_reviewer` | Record future approval decisions for scoped approval package refs. | Invoke connectors directly or bypass apply re-checks. |
| Policy reviewer | `role_policy_reviewer` | Review future policy-change packages and eval evidence refs. | Apply policy directly or edit tables out of band. |
| Policy applier workload | `role_policy_apply_workload` | Apply approved policy-change packages through a future controlled service. | Propose or review as a human actor; bypass eval evidence checks. |
| Platform operator | `role_platform_operator` | Operate platform workloads, migrations, and diagnostics within runbook limits. | Become a tenant approval reviewer by IAM alone. |

RBAC evidence must keep `actor_subject_ref`, `actor_session_id`, role refs,
tenant refs, approval refs, and policy-change refs as opaque safe values. It
must not store identity-provider claims, group claim payloads, display names,
email addresses, personal names, request headers, cookies, or access tokens.

## Principal Mapping

| Chorus principal | Production identity mapping | IAM or equivalent mapping | Chorus authority owner | Evidence owner |
|---|---|---|---|---|
| Human principal | External IdP subject is normalised to `actor_subject_ref`; role membership becomes bounded app RBAC refs. | IAM Identity Center or equivalent may grant console or workload-operation permissions, but not direct business action rights. | BFF, approval workflow, policy-change workflow, and application RBAC. | Future actor-session records, approval audit, policy-change audit, journey projections. |
| Workload principal | Service or worker has `workload_principal_id`, trust domain, service name, workload kind, tenant-scope category, and workload session ref. | ECS task role, EKS pod identity, Lambda execution role, EC2 instance profile, IAM Roles Anywhere role session, SPIFFE/SPIRE SVID, or equivalent. | Agent Runtime and Tool Gateway verify business authority after workload authentication. | Workload identity records, audit write-time workload refs, safe OTel resource attributes. |
| Agent principal | Logical agent version from `agent_registry`; no cloud credentials and no connector credentials. | May appear as safe session tags or policy attributes, never as an IAM user or long-lived credential. | Agent Runtime resolves approved agent version, prompt ref/hash, route, graph, provider, and budget. | Decision trail and eval evidence. |
| Invocation principal | One authorised invocation with `invocation_id`, tenant, workflow, agent, task kind, route, budget, expiry, workload refs, and optional parent invocation. | May be represented by a signed local authority envelope or safe STS tags when a workload calls cloud resources on behalf of an invocation. | Agent Runtime creates the invocation authority; Tool Gateway consumes the tool-authority subset. | Decision trail, Tool Gateway audit, authority-context audit metadata, eval. |
| Approval actor | Reviewer or system subject is represented by opaque actor refs, reviewer role, trust domain, approval package ref, and decision state. | IdP or IAM can authenticate the actor or approval service workload; it does not execute connector writes. | Approval package lifecycle and Tool Gateway approved-apply re-checks. | Approval audit, Tool Gateway audit, safe approval projections. |
| Policy actor | Proposer, reviewer, and applier are opaque actor refs or workload refs bound to a policy-change package. | IdP/IAM authenticates proposer/reviewer sessions and the apply workload. | Policy-change workflow, eval gates, and apply/rollback boundary. | Policy-change audit, eval evidence refs, decision trail references after apply. |

## Workload Role Catalogue Shape

A future production workload catalogue should be explicit before any role or
identity enforcement is implemented.

| Workload principal ref | Workload kind | Tenant scope | Production identity option | Chorus authority boundary |
|---|---|---|---|---|
| `wp_bff` | application | `tenant_allow_list` | `iam_role_ref=bff_read_projection` or service account ref. | Read-only projections and future RBAC checks; no connector calls. |
| `wp_temporal_worker` | application | `all_tenants` | `iam_role_ref=temporal_worker` or pod identity ref. | Runs deterministic workflow activities; calls Agent Runtime and Tool Gateway boundaries. |
| `wp_agent_runtime` | application | `all_tenants` | `iam_role_ref=agent_runtime` or service account ref. | Resolves agent version, prompt, route, provider, budget, graph, and decision trail. |
| `wp_tool_gateway` | application | `all_tenants` | `iam_role_ref=tool_gateway` or service account ref. | Enforces grants, schemas, modes, approvals, idempotency, redaction, and connector invocation. |
| `wp_projection_worker` | data | `all_tenants` | `iam_role_ref=projection_worker` or service account ref. | Builds read models from event/projection inputs; does not own workflow state. |
| `wp_connector_adapter` | application | `tenant_allow_list` | `iam_role_ref=connector_adapter`, IAM Roles Anywhere ref, or SPIFFE ref. | Executes only gateway-authorised connector actions. |
| `wp_policy_apply` | application | `all_tenants` | `iam_role_ref=policy_apply` or service account ref. | Future apply boundary for approved policy-change packages only. |
| `wp_observability_export` | observability | `none` | `iam_role_ref=telemetry_export` or managed collector identity. | Exports filtered telemetry; not audit authority. |

These refs are illustrative labels, not deployed roles. A later deployment
topology artefact must decide whether the identities are ECS task roles, EKS
pod identities, Lambda execution roles, IAM Roles Anywhere sessions,
SPIFFE/SPIRE identities, or a non-AWS equivalent.

## STS Session Name and Tag Rules

STS session names and tags are visible in cloud logs and policy evaluation, so
they must carry only safe refs and bounded categories.

Allowed session-name patterns:

```text
chorus-<workload-principal-ref>-<workload-session-ref>
chorus-<workload-principal-ref>-<authority-context-ref>
chorus-<workload-principal-ref>-<approval-ref>
chorus-<workload-principal-ref>-<policy-change-ref>
```

Use opaque refs for the bracketed values. Do not include actor names, email
addresses, tenant names, hostnames, IP addresses, request refs, raw correlation
payloads, raw approval rationale, policy rationale, prompt refs containing text,
or credential refs containing values.

Allowed session tag keys:

| Tag key | Value rule |
|---|---|
| `chorus:trust-domain` | Bounded trust-domain category or safe ref. |
| `chorus:workload-principal-id` | Stable workload principal ref. |
| `chorus:workload-session-id` | Opaque session ref where needed. |
| `chorus:service-name` | Bounded service ref, not host or container ID. |
| `chorus:deployment-environment` | Bounded environment class such as `local`, `ci`, `dev`, `prod`. |
| `chorus:tenant-scope-kind` | `none`, `all_tenants`, or `tenant_allow_list`. |
| `chorus:tenant-id` | Stable tenant ID only when the session is genuinely tenant scoped. |
| `chorus:workflow-type` | Bounded workflow type such as `lighthouse` or `support_triage`. |
| `chorus:agent-id` | Stable logical agent ref when useful for audit joins. |
| `chorus:invocation-id` | Opaque invocation ref when a cloud action is directly tied to one invocation. |
| `chorus:authority-context-id` | Opaque authority-context ref when executable context exists. |
| `chorus:approval-id` | Opaque approval ref when an approved apply workload assumes the session. |
| `chorus:policy-change-id` | Opaque policy-change ref when an apply workload assumes the session. |

Session tags do not replace `tool_grants`, model-route policy, approval state,
policy-change state, or eval evidence. They help cloud-resource policy and
audit join to Chorus records.

## IAM Roles Anywhere, SPIFFE/SPIRE, and External IdP Refs

Hybrid and external identity fields are refs, not credential stores.

| Mechanism | Allowed Chorus fields | Forbidden fields |
|---|---|---|
| IAM Roles Anywhere | `iam_roles_anywhere_profile_ref`, `trust_anchor_ref`, `certificate_subject_ref`, `workload_principal_id`, `trust_domain`. | Certificate bodies, private keys, serialised credentials, raw subject DNs, hostnames. |
| SPIFFE/SPIRE | `spiffe_trust_domain_ref`, `spiffe_id_ref`, `workload_principal_id`, `workload_session_id`. | SVID material, private keys, raw workload attestation documents. |
| External IdP | `identity_provider_ref`, `actor_subject_ref`, `actor_session_id`, `group_ref`, `role_ref`, `trust_domain`. | Claim dumps, names, email addresses, profile data, access tokens, refresh tokens, cookies. |

External IdP refs may support future human authentication and RBAC binding.
They must not become prompt inputs, telemetry baggage, connector arguments, or
eval fixture payloads.

## Safe Field Rules

Allowed examples and docs may use:

- stable refs: tenant, workload, workload session, actor subject, actor
  session, workflow, correlation, invocation, authority context, approval,
  policy-change, route, grant, provider, connector, deployment, runbook, eval,
  fixture, role, trust-domain, identity-provider, IAM role, IAM profile,
  SPIFFE, and certificate-subject refs;
- bounded categories: environment class, trust-domain category, workload kind,
  tenant-scope kind, RBAC role category, workflow type, task kind, tool mode,
  approval state, policy-change state, decision state, failure class, and
  deployment class;
- safe STS tag keys and session-name templates that contain only refs.

Forbidden everywhere in docs, samples, telemetry, projections, eval fixtures,
audit examples, sidecar examples, and handoff records:

- secrets, credentials, API keys, access tokens, session tokens, signing keys,
  private keys, certificate material, provider keys, or credential state;
- raw sensitive content, customer content, raw prompts, raw model outputs, raw
  tool arguments, raw connector payloads, raw approval rationale, raw
  policy-change rationale, policy diff bodies, raw request/response bodies, or
  retrieval/file contents;
- identity-provider claims, names, email addresses, profile data, group claim
  dumps, IP addresses, hostnames, filesystem paths, cookies, request headers,
  full user-agent strings, or PII;
- full IAM policies, full ARNs, cloud account IDs, external IDs, certificate
  subjects, or SPIFFE IDs in public examples. Use refs unless a later private
  production artefact explicitly allows the concrete value.

## Required Future Artefacts

Before production SSO, workload identity enforcement, or tenant/RBAC
implementation, add:

| Artefact | Required content |
|---|---|
| Identity binding catalogue | Opaque actor subject refs, IdP refs, actor-session refs, trust domains, and forbidden claim fields. |
| Tenant/RBAC matrix | Tenant-scope rules, role refs, approval and policy-review roles, read-only BFF permissions, and break-glass category boundaries. |
| Workload role catalogue | Workload principal refs, workload kinds, tenant scope, IAM role refs or equivalent service identity refs, trust domains, and authority boundaries. |
| STS naming and tag standard | Session-name templates, allowed tag keys, value rules, denied fields, and audit join expectations. |
| IAM Roles Anywhere and SPIFFE mapping | Profile/trust-anchor refs, certificate-subject refs, SPIFFE refs, trust-domain refs, and credential-material exclusion rules. |
| External IdP mapping | Subject-ref derivation, group/role ref mapping, claim filtering, actor-session lifecycle, and audit retention expectations. |
| Invocation-authority binding plan | How future `authority_context_id` binds Agent Runtime invocations, Tool Gateway requests, workload sessions, approval refs, and policy-change refs. |
| Approval actor mapping | How approval packages bind reviewer actor refs, reviewer roles, workload refs, expiry, decision state, and Tool Gateway apply re-checks. |
| Policy actor mapping | How policy changes bind proposer, reviewer, applier workload refs, eval evidence refs, approval refs, apply refs, rollback refs, and expiry. |
| Evidence and gate checklist | Required tests, redaction checks, audit examples, projections, runbook commands, and skipped-gate rules for any executable promotion. |

The secrets and credential handling artefact in
[`secrets-credential-handling.md`](secrets-credential-handling.md) defines the
`2E-02` secret-ref and credential lifecycle boundary required before any item
above stores or injects credential refs that lead to real secret-manager,
provider, connector, signing, or identity-provider integration.

## Evidence Expectations

For this docs-first item, evidence is the artefact itself plus phase-plan,
architecture, evidence-map, implementation-plan, runbook, and handoff
alignment. The expected gates are `just contracts-check`, `just doctor-quick`,
and `git diff --check`.

Future executable identity work must add evidence appropriate to the behaviour
it changes:

| Future change | Minimum evidence |
|---|---|
| Persist workload principals or sessions | Migration, safe seeds, focused persistence tests, OTel placement review, runbook inspection. |
| Enforce workload authentication at service boundary | Focused BFF/Agent Runtime/Tool Gateway tests, denial-path tests, audit joins, docs/runbook updates. |
| Add production SSO or external IdP binding | IdP claim filtering tests, actor-subject ref tests, RBAC denial tests, forbidden-field checks, no claim dumps in audit/projections. |
| Add tenant/RBAC enforcement | Tenant isolation tests, role-matrix tests, safe projection tests, no tenant-admin mutation unless explicitly scoped. |
| Add invocation authority envelopes | Contract or deterministic object tests, signature/key-ref tests if signing exists, Agent Runtime and Tool Gateway verification tests, replay/eval gate review. |
| Add approval actor decisions | Approval lifecycle tests, reviewer role tests, Tool Gateway approved-apply re-check tests, approval audit and projection checks. |
| Add policy actor apply path | Policy-change lifecycle tests, eval evidence requirement tests, apply/rollback/idempotency tests, audit and runbook checks. |

Runtime, replay, eval, persistence, BFF/UI, frontend, Tool Gateway, connector,
provider, and hosted observability gates remain skipped for 2E-01 because no
runtime behaviour changes.

## Promotion Criteria

Promote this architecture into executable implementation only when a later
ledger item explicitly opens one of these behaviours:

- production SSO or external identity-provider integration;
- tenant/RBAC enforcement in the BFF or approval/policy surfaces;
- workload-principal and workload-session persistence;
- service-boundary workload authentication between BFF, Temporal worker, Agent
  Runtime, Tool Gateway, projection worker, and connector adapters;
- IAM role, STS session, IAM Roles Anywhere, SPIFFE/SPIRE, or equivalent
  workload identity enforcement;
- signed invocation-authority or tool-authority context;
- approval actor decision path;
- policy actor propose/review/apply/rollback path.

Promotion must start from the narrowest local deterministic implementation that
proves the evidence. It must not bundle production SSO with secrets handling,
cloud deployment, provider calls, connector writes, hosted observability,
tenant-admin UI, reviewer decision UI, or policy apply unless those behaviours
have their own ledger item, evidence expectations, and gates.

## Backlog Implications

- `2E-02` secrets and credential handling is complete as a docs-first
  companion artefact. Production identity still cannot become executable
  without the future secret-ref catalogue, injection, rotation, revocation, and
  break-glass evidence it requires.
- `2E-03` deployment topology must decide where workload principals run before
  IAM roles, pod identities, IAM Roles Anywhere, or SPIFFE/SPIRE are
  implemented.
- `2E-07` managed observability must preserve the safe identity field rules
  before any telemetry exporter carries workload, actor, approval, or policy
  refs outside the local stack.
- `2E-08` production provider and connector hardening must require workload
  identity, credential refs, Tool Gateway authority, approval, idempotency,
  eval, and rollback evidence before real provider calls or connector writes.

Until those items land, Chorus remains a local reference implementation with
production identity mapped as architecture, not implemented behaviour.
