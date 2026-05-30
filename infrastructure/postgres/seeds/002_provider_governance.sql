-- Provider catalogue and route-version seed data.
--
-- Mirrors the contract samples and the model_routing_policies seeded in
-- 001_demo_tenants.sql. The local recorded-replay route stays the runnable
-- structured boundary for UC1 and R5 P1 UC2 route-resolution evidence. The
-- DeepSeek and OpenAI rows are verified but disabled until live-provider
-- gates and the tiered replay comparator are complete.

INSERT INTO provider_catalogues (
    catalogue_id,
    schema_version,
    effective_from
)
VALUES (
    'provider-catalogue.local.seed',
    '1.0.0',
    '2026-05-03T00:00:00Z'
)
ON CONFLICT (catalogue_id) DO NOTHING;

-- Remove the previous disabled commercial placeholder so the local
-- governance snapshot exposes only verified provider/model credential refs.
DELETE FROM model_route_versions
WHERE provider_catalogue_id = 'provider-catalogue.local.seed'
  AND provider_id = 'commercial.example';

DELETE FROM provider_catalogue_models
WHERE catalogue_id = 'provider-catalogue.local.seed'
  AND provider_id = 'commercial.example';

DELETE FROM provider_catalogue_providers
WHERE catalogue_id = 'provider-catalogue.local.seed'
  AND provider_id = 'commercial.example';

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
        'provider-catalogue.local.seed',
        'local',
        'Local structured boundary',
        'local',
        'approved',
        false,
        ARRAY[]::text[],
        'allow',
        '{"mode": "local_only", "allowed_regions": [], "stores_customer_content": false}'::jsonb,
        '{"default_timeout_ms": 1000, "max_retries": 0, "rate_limit_policy": "local-process-boundary"}'::jsonb,
        '{"owner": "agent-runtime", "declared_in": "infrastructure/postgres/seeds/002_provider_governance.sql", "notes": "Default runnable path for UC1 evidence and R5 P1 UC2 route-resolution evidence."}'::jsonb
    ),
    (
        'provider-catalogue.local.seed',
        'deepseek',
        'DeepSeek API',
        'commercial',
        'disabled',
        true,
        ARRAY['DEEPSEEK_API_KEY']::text[],
        'disable_provider',
        '{"mode": "external_api", "allowed_regions": ["vendor-managed"], "stores_customer_content": true}'::jsonb,
        '{"default_timeout_ms": 30000, "max_retries": 2, "rate_limit_policy": "provider-documented-quota"}'::jsonb,
        '{"owner": "agent-runtime", "declared_in": "infrastructure/postgres/seeds/002_provider_governance.sql", "notes": "Verified from official DeepSeek API docs on 2026-05-24: https://api-docs.deepseek.com/, https://api-docs.deepseek.com/api/list-models, and https://api-docs.deepseek.com/updates/. Disabled until P3 route-governance and live-provider gates are complete."}'::jsonb
    ),
    (
        'provider-catalogue.local.seed',
        'openai',
        'OpenAI API',
        'commercial',
        'disabled',
        true,
        ARRAY['OPENAI_API_KEY']::text[],
        'disable_provider',
        '{"mode": "external_api", "allowed_regions": ["vendor-managed"], "stores_customer_content": true}'::jsonb,
        '{"default_timeout_ms": 30000, "max_retries": 2, "rate_limit_policy": "provider-documented-quota"}'::jsonb,
        '{"owner": "agent-runtime", "declared_in": "infrastructure/postgres/seeds/002_provider_governance.sql", "notes": "Verified from official OpenAI API docs on 2026-05-24: https://developers.openai.com/api/docs/models/gpt-5.4-mini and https://developers.openai.com/api/reference/overview. Disabled until P3 route-governance and live-provider gates are complete."}'::jsonb
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
        'provider-catalogue.local.seed',
        'local',
        'uc1-happy-path-v1',
        'Local recorded-replay structured model',
        'approved',
        ARRAY[
            'enquiry_classification',
            'context_gathering',
            'enquiry_qualification',
            'missing_data_request_draft',
            'missing_data_request_validation',
            'uc2_matter_classification',
            'uc2_party_extraction',
            'uc2_conflict_determination',
            'uc2_engagement_decision'
        ]::text[],
        true,
        8192,
        '{"currency": "USD", "input_usd_per_1m_tokens": 0, "output_usd_per_1m_tokens": 0}'::jsonb
    ),
    (
        'provider-catalogue.local.seed',
        'deepseek',
        'deepseek-v4-flash',
        'DeepSeek V4 Flash',
        'disabled',
        ARRAY[
            'enquiry_classification',
            'context_gathering',
            'enquiry_qualification',
            'missing_data_request_draft',
            'missing_data_request_validation',
            'uc2_matter_classification',
            'uc2_party_extraction',
            'uc2_conflict_determination',
            'uc2_engagement_decision'
        ]::text[],
        true,
        1000000,
        '{"currency": "USD", "input_usd_per_1m_tokens": 0.14, "output_usd_per_1m_tokens": 0.28}'::jsonb
    ),
    (
        'provider-catalogue.local.seed',
        'openai',
        'gpt-5.4-mini-2026-03-17',
        'GPT-5.4 mini pinned snapshot',
        'disabled',
        ARRAY[
            'enquiry_classification',
            'context_gathering',
            'enquiry_qualification',
            'missing_data_request_draft',
            'missing_data_request_validation',
            'uc2_matter_classification',
            'uc2_party_extraction',
            'uc2_conflict_determination',
            'uc2_engagement_decision'
        ]::text[],
        true,
        400000,
        '{"currency": "USD", "input_usd_per_1m_tokens": 0.75, "output_usd_per_1m_tokens": 4.5}'::jsonb
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
    runtime_route_id,
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
    runtime_route_id,
    'provider-catalogue.local.seed',
    provider,
    model,
    parameters,
    budget_cap_usd,
    5000,
    '{"mode": "escalate", "fallback_reasons": ["provider_error", "timeout", "rate_limited", "budget_exceeded"]}'::jsonb,
    true,
    CASE
        WHEN task_kind LIKE 'uc2_%'
        THEN ARRAY[
            'chorus/eval/fixtures/uc2/uc2_synthetic_acceptance_conduct.json'
        ]::text[]
        ELSE ARRAY[
            'chorus/eval/fixtures/uc1_happy_path.json',
            'chorus/eval/fixtures/uc1_validator_redraft.json',
            'chorus/eval/fixtures/uc1_accepted_routing.json',
            'chorus/eval/fixtures/uc1_referred_routing.json',
            'chorus/eval/fixtures/uc1_declined_routing.json'
        ]::text[]
    END,
    CASE
        WHEN task_kind LIKE 'uc2_%'
        THEN '{
            "approved_by": "architecture-docs",
            "future_live_route": {
                "status": "deferred_until_R5_P3",
                "runtime_route_id": "demo-eval-canonical",
                "provider_id": "openai",
                "model_id": "gpt-5.4-mini-2026-03-17",
                "credential_ref": "OPENAI_API_KEY"
            }
        }'::jsonb
        ELSE '{"approved_by": "architecture-docs"}'::jsonb
    END
FROM model_routing_policies
WHERE provider = 'local'
  AND model = 'uc1-happy-path-v1'
  AND agent_role IN (
      'classifier',
      'context_gatherer',
      'qualifier',
      'request_drafter',
      'validator',
      'legal_matter_classifier',
      'legal_party_extractor',
      'conflict_analyst',
      'engagement_decider'
  )
ON CONFLICT (route_id, route_version) DO NOTHING;
