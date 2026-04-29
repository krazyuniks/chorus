-- Phase 1A demo tenant seed data.
--
-- Two tenants are intentionally present so RLS and fail-closed tests can prove
-- tenant-owned tables do not leak rows across the runtime boundary.

INSERT INTO tenants (tenant_id, display_name, tenant_tier, status, metadata)
VALUES
    (
        'tenant_demo',
        'Lighthouse Demo Tenant',
        'demo',
        'active',
        '{"purpose": "primary Lighthouse demo path"}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'Lighthouse Isolation Tenant',
        'demo',
        'active',
        '{"purpose": "tenant isolation evidence"}'::jsonb
    )
ON CONFLICT (tenant_id) DO UPDATE
SET
    display_name = EXCLUDED.display_name,
    tenant_tier = EXCLUDED.tenant_tier,
    status = EXCLUDED.status,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO agent_registry (
    tenant_id,
    agent_id,
    role,
    version,
    lifecycle_state,
    owner,
    prompt_reference,
    prompt_hash,
    capability_tags,
    metadata
)
VALUES
    (
        'tenant_demo',
        'lighthouse.researcher',
        'researcher',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/lighthouse/researcher/v1.md',
        'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        ARRAY['lighthouse', 'research']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'lighthouse.researcher',
        'researcher',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/lighthouse/researcher/v1.md',
        'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        ARRAY['lighthouse', 'research']::text[],
        '{"seed": true}'::jsonb
    )
ON CONFLICT (tenant_id, agent_id, version) DO UPDATE
SET
    role = EXCLUDED.role,
    lifecycle_state = EXCLUDED.lifecycle_state,
    owner = EXCLUDED.owner,
    prompt_reference = EXCLUDED.prompt_reference,
    prompt_hash = EXCLUDED.prompt_hash,
    capability_tags = EXCLUDED.capability_tags,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO model_routing_policies (
    policy_id,
    tenant_id,
    agent_role,
    task_kind,
    tenant_tier,
    provider,
    model,
    parameters,
    budget_cap_usd,
    fallback_policy,
    lifecycle_state
)
VALUES
    (
        '11000000-0000-4000-8000-000000000001',
        'tenant_demo',
        'researcher',
        'company_research',
        'demo',
        'anthropic',
        'claude-sonnet-latest',
        '{"temperature": 0.2}'::jsonb,
        0.2500,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000002',
        'tenant_demo_alt',
        'researcher',
        'company_research',
        'demo',
        'anthropic',
        'claude-sonnet-latest',
        '{"temperature": 0.2}'::jsonb,
        0.2500,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    )
ON CONFLICT (tenant_id, agent_role, task_kind, tenant_tier) DO UPDATE
SET
    provider = EXCLUDED.provider,
    model = EXCLUDED.model,
    parameters = EXCLUDED.parameters,
    budget_cap_usd = EXCLUDED.budget_cap_usd,
    fallback_policy = EXCLUDED.fallback_policy,
    lifecycle_state = EXCLUDED.lifecycle_state,
    updated_at = now();

INSERT INTO tool_grants (
    grant_id,
    tenant_id,
    agent_id,
    agent_version,
    tool_name,
    mode,
    allowed,
    approval_required,
    redaction_policy,
    metadata
)
VALUES
    (
        '12000000-0000-4000-8000-000000000001',
        'tenant_demo',
        'lighthouse.researcher',
        'v1',
        'company_research.lookup',
        'read',
        true,
        false,
        '{"persist": "summary_only"}'::jsonb,
        '{"seed": true}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000002',
        'tenant_demo_alt',
        'lighthouse.researcher',
        'v1',
        'company_research.lookup',
        'read',
        true,
        false,
        '{"persist": "summary_only"}'::jsonb,
        '{"seed": true}'::jsonb
    )
ON CONFLICT (tenant_id, agent_id, agent_version, tool_name, mode) DO UPDATE
SET
    allowed = EXCLUDED.allowed,
    approval_required = EXCLUDED.approval_required,
    redaction_policy = EXCLUDED.redaction_policy,
    metadata = EXCLUDED.metadata,
    updated_at = now();
