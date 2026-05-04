-- Phase 2A provider catalogue and route-version seed data.
--
-- This mirrors the contract samples and the existing Phase 1 local route seeds.
-- It does not change model_routing_policies, so lighthouse-happy-path-v1 stays
-- the runnable local route until later runtime work moves to route versions.

INSERT INTO provider_catalogues (
    catalogue_id,
    schema_version,
    effective_from
)
VALUES (
    'provider-catalogue.phase2a.seed',
    '1.0.0',
    '2026-05-03T00:00:00Z'
)
ON CONFLICT (catalogue_id) DO NOTHING;

INSERT INTO provider_catalogue_providers (
    catalogue_id,
    provider_id,
    display_name,
    provider_kind,
    lifecycle_state,
    credential_required,
    secret_ref_names,
    missing_credentials_behaviour,
    data_boundary,
    operational_limits,
    audit
)
VALUES
    (
        'provider-catalogue.phase2a.seed',
        'local',
        'Local structured boundary',
        'local',
        'approved',
        false,
        ARRAY[]::text[],
        'allow',
        '{"mode": "local_only", "allowed_regions": [], "stores_customer_content": false}'::jsonb,
        '{"default_timeout_ms": 1000, "max_retries": 0, "rate_limit_policy": "local-process-boundary"}'::jsonb,
        '{"owner": "agent-runtime", "declared_in": "infrastructure/postgres/seeds/002_provider_governance.sql", "change_ref": "2A-02", "notes": "Default runnable path for Lighthouse Phase 1 evidence."}'::jsonb
    ),
    (
        'provider-catalogue.phase2a.seed',
        'commercial.example',
        'Commercial provider placeholder',
        'commercial',
        'disabled',
        true,
        ARRAY['CHORUS_COMMERCIAL_LLM_API_KEY']::text[],
        'disable_provider',
        '{"mode": "external_api", "allowed_regions": ["vendor-managed"], "stores_customer_content": true}'::jsonb,
        '{"default_timeout_ms": 30000, "max_retries": 2, "rate_limit_policy": "provider-documented-quota"}'::jsonb,
        '{"owner": "agent-runtime", "declared_in": "infrastructure/postgres/seeds/002_provider_governance.sql", "change_ref": "2A-02", "notes": "Disabled placeholder only; no provider adapter is enabled by this seed."}'::jsonb
    )
ON CONFLICT (catalogue_id, provider_id) DO UPDATE
SET
    display_name = EXCLUDED.display_name,
    provider_kind = EXCLUDED.provider_kind,
    lifecycle_state = EXCLUDED.lifecycle_state,
    credential_required = EXCLUDED.credential_required,
    secret_ref_names = EXCLUDED.secret_ref_names,
    missing_credentials_behaviour = EXCLUDED.missing_credentials_behaviour,
    data_boundary = EXCLUDED.data_boundary,
    operational_limits = EXCLUDED.operational_limits,
    audit = EXCLUDED.audit,
    updated_at = now();

INSERT INTO provider_catalogue_models (
    catalogue_id,
    provider_id,
    model_id,
    display_name,
    lifecycle_state,
    supported_task_kinds,
    supports_structured_output,
    context_window_tokens,
    cost_policy
)
VALUES
    (
        'provider-catalogue.phase2a.seed',
        'local',
        'lighthouse-happy-path-v1',
        'Lighthouse local structured model',
        'approved',
        ARRAY['company_research', 'lead_qualification', 'response_draft', 'response_validation']::text[],
        true,
        8192,
        '{"currency": "USD", "input_usd_per_1m_tokens": 0, "output_usd_per_1m_tokens": 0}'::jsonb
    ),
    (
        'provider-catalogue.phase2a.seed',
        'commercial.example',
        'commercial-reasoner-v1',
        'Commercial reasoning model placeholder',
        'disabled',
        ARRAY['lead_qualification', 'response_draft', 'response_validation']::text[],
        true,
        128000,
        '{"currency": "USD", "input_usd_per_1m_tokens": 3, "output_usd_per_1m_tokens": 15}'::jsonb
    )
ON CONFLICT (catalogue_id, provider_id, model_id) DO UPDATE
SET
    display_name = EXCLUDED.display_name,
    lifecycle_state = EXCLUDED.lifecycle_state,
    supported_task_kinds = EXCLUDED.supported_task_kinds,
    supports_structured_output = EXCLUDED.supports_structured_output,
    context_window_tokens = EXCLUDED.context_window_tokens,
    cost_policy = EXCLUDED.cost_policy,
    updated_at = now();

INSERT INTO model_route_versions (
    route_id,
    route_version,
    lifecycle_state,
    tenant_id,
    agent_role,
    task_kind,
    tenant_tier,
    provider_catalogue_id,
    provider_id,
    model_id,
    parameters,
    budget_cap_usd,
    max_latency_ms,
    fallback_policy,
    eval_required,
    eval_fixture_refs,
    promotion
)
SELECT
    policy_id,
    1,
    lifecycle_state,
    tenant_id,
    agent_role,
    task_kind,
    tenant_tier,
    'provider-catalogue.phase2a.seed',
    provider,
    model,
    parameters,
    budget_cap_usd,
    5000,
    '{"mode": "escalate", "fallback_reasons": ["provider_error", "timeout", "budget_exceeded"]}'::jsonb,
    true,
    ARRAY['chorus/eval/fixtures/lighthouse_happy_path.json']::text[],
    '{"change_ref": "2A-02", "approved_by": "architecture-docs"}'::jsonb
FROM model_routing_policies
WHERE provider = 'local'
  AND model = 'lighthouse-happy-path-v1'
ON CONFLICT (route_id, route_version) DO NOTHING;
