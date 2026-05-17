---
type: project-doc
status: planning
date: 2026-05-14
---

# Workload Principal and Future AWS IAM Mapping

## Purpose

This document is the Phase 2B-02 docs-first schema sketch for workload
identity. It extends [ADR 0013](../adrs/0013-identity-authority-observability-boundaries.md)
and the [observability and user-journey model](observability-user-journey-model.md)
without adding AWS, production SSO, cloud deployment, credentials, or a new
runtime dependency. The companion invocation-authority context sketch in
[`invocation-authority-context.md`](invocation-authority-context.md) defines how
these workload-principal and workload-session references can later bind to an
Agent Runtime invocation or Tool Gateway request.

The model names local Chorus services and workers as workload principals,
separates a long-lived workload identity from a short-lived workload session,
records tenant scope as application metadata, and reserves future mapping
fields for AWS IAM roles, STS session names and tags, IAM Roles Anywhere, and
external identity-provider references.

No Postgres migration or contract is added yet. The current Lighthouse path
does not write workload sessions or enforce workload authentication at a
service boundary, so a table would be seed-only evidence. Promote this sketch
to Postgres when a service starts writing workload-session evidence or when
Agent Runtime, Tool Gateway, BFF, or the worker starts enforcing workload
authentication.

## Design Rules

- Workload identity proves which service or worker is running; it does not
  grant business authority by itself.
- Chorus business authority remains application-level policy owned by Agent
  Runtime, Tool Gateway, approval audit, policy mutation audit, and eval gates.
- Agents are logical principals. They never receive cloud credentials or
  connector credentials.
- Future AWS fields are nullable mapping metadata, not local dependencies.
- Telemetry receives only low-cardinality safe identifiers. Full mapping
  metadata belongs in Postgres audit or identity records, not span attributes
  or baggage.
- Seeds and examples must not include secrets, API keys, access tokens,
  temporary credentials, raw sensitive content, email addresses, personal
  names, IP addresses, hostnames, or local filesystem paths.

## Local Trust Domains

| Trust domain | Meaning | Local use | Future mapping |
|---|---|---|---|
| `local.chorus` | Compose-based Chorus local runtime. | Default for all local workload principals and workload sessions. | Can map to a future AWS account, EKS cluster, ECS service boundary, or non-AWS workload identity domain. |
| `fixture.chorus` | Local eval, replay, and scripted fixture runs. | Use when a CLI or eval harness creates session evidence outside Compose. | Can map to CI workload identity or signed release-gate automation. |
| `external.<provider>` | Future federated or hybrid trust domain. | Not used in the local runtime. | External OIDC/SAML provider, SPIFFE/SPIRE trust domain, or IAM Roles Anywhere certificate trust anchor. |

`trust_domain` is a join and isolation field. It is not a secret and should be
bounded to a configured allow-list.

## Principal Sketch

`workload_principals` represents the stable service or worker identity. It is
safe to seed once the runtime has an enforcing or writing consumer.

```text
workload_principals
  workload_principal_id        -- stable ID, for example chorus-bff
  service_name                 -- OTel service.name / Compose service name
  service_namespace            -- chorus
  workload_kind                -- application | platform | data | observability | init
  trust_domain                 -- local.chorus initially
  deployment_environment       -- local initially
  status                       -- active | disabled | planned
  tenant_scope_kind            -- none | all_tenants | tenant_allow_list
  tenant_ids                   -- nullable allow-list of tenant IDs
  authority_boundary           -- read_projection | workflow_worker | audit_writer | telemetry_only | substrate
  description                  -- bounded operational description
  metadata                     -- safe bounded metadata only
  created_at
  updated_at
```

Field rules:

| Field | Rule |
|---|---|
| `workload_principal_id` | Stable, human-readable local ID. Prefer the Compose service name or `chorus-<role>` container name. |
| `tenant_scope_kind` | Represents application scope, not database credentials. Infrastructure workloads normally use `none`. |
| `tenant_ids` | Use only fixture tenant IDs such as `tenant_demo` and `tenant_demo_alt`; do not store customer names. |
| `authority_boundary` | Documents the local boundary the workload participates in. It does not replace Tool Gateway grants or Agent Runtime policy. |
| `metadata` | Allow only bounded operational labels, for example `runtime=compose`; never store environment variables or connection strings. |

## Workload Session Sketch

`workload_sessions` represents one running service instance or local CLI
execution. It is session evidence, not an authentication token.

```text
workload_sessions
  workload_session_id          -- opaque generated ID
  workload_principal_id
  trust_domain
  service_name
  deployment_environment
  runtime_kind                 -- compose | host-cli | ci
  runtime_instance_ref         -- opaque local instance ref, nullable
  started_at
  ended_at
  service_version
  session_status               -- active | ended | expired
  metadata                     -- safe bounded runtime metadata only
```

Field rules:

| Field | Rule |
|---|---|
| `workload_session_id` | Generate at process start or session registration. Do not derive it from host usernames, hostnames, IP addresses, container IDs, or credentials. |
| `runtime_instance_ref` | Optional opaque reference such as `compose:bff:1`. Do not store raw Docker container IDs in telemetry. |
| `service_version` | Build or repo version when available; `dev` is acceptable for local evidence. |
| `metadata` | Safe labels only. Do not store full command lines, environment payloads, URLs with credentials, request headers, or filesystem paths. |

Only `workload_principal_id`, `trust_domain`, `service.name`,
`service.namespace`, `deployment.environment`, and `service.version` are
candidates for resource attributes. `workload_session_id` can be a bounded
span attribute when a local diagnostic path needs it. Do not propagate workload
session fields through baggage.

## Future AWS Mapping Sketch

`workload_principal_aws_mappings` is optional future metadata. It should remain
nullable in local runs and should not require AWS SDKs, AWS accounts, Terraform,
Kubernetes, ECS, Lambda, or credentials.

```text
workload_principal_aws_mappings
  workload_principal_id
  trust_domain
  aws_mapping_status           -- planned | active | retired
  aws_partition                -- aws | aws-us-gov | aws-cn, nullable
  aws_region                   -- nullable
  aws_account_ref              -- opaque account reference, nullable
  iam_role_arn                 -- nullable role ARN
  sts_session_name_template    -- nullable bounded template
  sts_session_tag_keys         -- nullable allow-list of tag keys
  sts_session_tag_defaults     -- nullable safe defaults
  external_id_ref              -- opaque reference only, not the external ID value
  iam_roles_anywhere_profile_arn
  iam_roles_anywhere_trust_anchor_arn
  iam_roles_anywhere_certificate_subject_ref
  external_identity_provider_ref
  spiffe_id                    -- nullable non-AWS workload identity reference
  notes                        -- bounded non-sensitive note
  created_at
  updated_at
```

Safe STS session tag keys:

| Tag key | Meaning |
|---|---|
| `chorus:trust-domain` | Trust-domain label such as `local.chorus` or a future cloud domain. |
| `chorus:workload-principal-id` | Stable workload principal ID. |
| `chorus:service-name` | Service name, normally matching `service.name`. |
| `chorus:deployment-environment` | Environment label such as `local`, `dev`, or `prod`. |
| `chorus:tenant-scope-kind` | Scope category, not a tenant name. |
| `chorus:tenant-id` | Only when the workload is genuinely tenant-scoped and the value is a stable tenant ID. |

Do not put raw prompts, model outputs, lead content, email addresses, personal
names, provider credentials, access keys, session tokens, API keys, secret
values, certificate bodies, or unbounded policy rationale in role session
names or tags.

## Local Compose Principal Catalogue

The current local stack can be represented by the following docs-first
principal catalogue. This is not a seed file; it is the reference shape for a
future migration if workload-principal persistence becomes necessary.

| Workload principal | Compose service | Kind | Tenant scope | Authority boundary | Future AWS mapping |
|---|---|---|---|---|---|
| `chown-init` | `chown-init` | init | none | substrate | None; local filesystem ownership helper only. |
| `postgres` | `postgres` | data | all_tenants | substrate | Managed database identity or security group boundary, not an application role. |
| `redpanda` | `redpanda` | platform | all_tenants | substrate | Managed Kafka/MSK identity mapping if a future deployment uses it. |
| `redpanda-console` | `redpanda-console` | platform | none | telemetry_only | Future console/operator identity, not business authority. |
| `temporal-postgres` | `temporal-postgres` | data | none | substrate | Managed Temporal persistence boundary if self-hosted. |
| `temporal` | `temporal` | platform | all_tenants | workflow_worker | ECS task role, EKS pod identity, Lambda execution role, or service identity for Temporal server. |
| `temporal-ui` | `temporal-ui` | platform | none | telemetry_only | Future console/operator identity, not approval authority. |
| `mailpit` | `mailpit` | platform | none | substrate | No production mapping; production email providers remain connector work. |
| `chorus-intake-poller` | `intake-poller` | application | all_tenants | workflow_worker | ECS task role, EKS pod identity, Lambda execution role, or IAM Roles Anywhere session for the intake worker. |
| `chorus-bff` | `bff` | application | tenant_allow_list: `tenant_demo` | read_projection | ECS task role, EKS pod identity, Lambda execution role, or IAM Roles Anywhere session for the BFF. |
| `grafana` | `grafana` | observability | none | telemetry_only | Future observability service role, not audit authority. |
| `tempo` | `tempo` | observability | none | telemetry_only | Future managed tracing service identity. |
| `loki` | `loki` | observability | none | telemetry_only | Future managed logging service identity. |
| `prometheus` | `prometheus` | observability | none | telemetry_only | Future managed metrics service identity. |
| `otel-collector` | `otel-collector` | observability | none | telemetry_only | ECS task role, EKS pod identity, or IAM Roles Anywhere session for telemetry export. |

When Agent Runtime, Tool Gateway, connectors, projection worker, or frontend are
split into separate Compose services, add explicit workload principals for
those services instead of overloading `chorus-intake-poller` or `chorus-bff`.

## Mapping To Telemetry, Projection, and Audit

| Plane | Workload fields allowed | Workload fields excluded |
|---|---|---|
| OTel resource attributes | `service.name`, `service.namespace`, `deployment.environment`, `service.version`, `chorus.workload.principal_id`, `chorus.workload.trust_domain`. | IAM role ARN, STS session tags, external ID refs, IAM Roles Anywhere refs, raw runtime metadata. |
| OTel span attributes | Optional operation-local `chorus.workload.session_id` only when needed for local diagnosis and bounded-cardinality test runs. | Credentials, full container IDs, hostnames, IP addresses, command lines, authority packages. |
| OTel baggage | No workload-principal fields beyond the existing tenant/correlation/workflow allow-list. | Workload session IDs, IAM mapping fields, service credentials, policy state. |
| Postgres projections | Safe principal/session references if reviewer journey views need them. | Full IAM mapping metadata and authority decisions. |
| Audit/accountability | Principal/session IDs at write time, and future mapping refs when accountability requires them. | Access keys, session tokens, certificate material, provider credentials, raw sensitive content. |

## Promotion Criteria

Keep this docs-first until one of these happens:

- a service registers a `workload_session_id` on startup;
- BFF/UI journey evidence joins reviewer activity to a workload session;
- Agent Runtime or Tool Gateway accepts a structured authority context that
  includes a calling workload principal;
- approval or policy mutation audit needs to distinguish human, automation,
  and workload actors;
- a production-readiness spike needs executable mapping tests for a future AWS
  deployment.

When promoted, add a migration, seed local workload principals for the current
Compose services, add focused persistence tests, and keep AWS fields nullable.
Do not add cloud dependencies, credentials, credential-entry UI, production
SSO, or production deployment as part of that promotion.
