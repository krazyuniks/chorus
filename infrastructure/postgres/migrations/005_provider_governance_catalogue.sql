-- Phase 2A provider governance catalogue and immutable model route versions.
--
-- These tables make provider/model governance inspectable in Postgres without
-- changing the Phase 1 Agent Runtime lookup path, which continues to read
-- model_routing_policies until later 2A ledger items move runtime execution.

CREATE TABLE IF NOT EXISTS provider_catalogues (
    catalogue_id text PRIMARY KEY,
    schema_version text NOT NULL,
    effective_from timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT provider_catalogues_id_shape CHECK (
        catalogue_id ~ '^provider-catalogue\.[A-Za-z0-9_.-]+$'
    ),
    CONSTRAINT provider_catalogues_schema_version_check CHECK (schema_version = '1.0.0')
);

CREATE TABLE IF NOT EXISTS provider_catalogue_providers (
    catalogue_id text NOT NULL REFERENCES provider_catalogues (catalogue_id) ON DELETE RESTRICT,
    provider_id text NOT NULL,
    display_name text NOT NULL,
    provider_kind text NOT NULL,
    lifecycle_state text NOT NULL,
    credential_required boolean NOT NULL,
    secret_ref_names text[] NOT NULL DEFAULT ARRAY[]::text[],
    missing_credentials_behaviour text NOT NULL,
    data_boundary jsonb NOT NULL,
    operational_limits jsonb NOT NULL,
    audit jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (catalogue_id, provider_id),
    CONSTRAINT provider_catalogue_providers_id_shape CHECK (provider_id ~ '^[a-z][a-z0-9_.-]*$'),
    CONSTRAINT provider_catalogue_providers_kind_check CHECK (
        provider_kind IN ('local', 'commercial', 'sandbox')
    ),
    CONSTRAINT provider_catalogue_providers_lifecycle_check CHECK (
        lifecycle_state IN ('draft', 'approved', 'deprecated', 'disabled')
    ),
    CONSTRAINT provider_catalogue_providers_missing_credentials_check CHECK (
        missing_credentials_behaviour IN ('allow', 'disable_provider', 'fallback_only')
    )
);

CREATE TABLE IF NOT EXISTS provider_catalogue_models (
    catalogue_id text NOT NULL,
    provider_id text NOT NULL,
    model_id text NOT NULL,
    display_name text NOT NULL,
    lifecycle_state text NOT NULL,
    supported_task_kinds text[] NOT NULL,
    supports_structured_output boolean NOT NULL,
    context_window_tokens integer,
    cost_policy jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (catalogue_id, provider_id, model_id),
    FOREIGN KEY (catalogue_id, provider_id)
        REFERENCES provider_catalogue_providers (catalogue_id, provider_id)
        ON DELETE RESTRICT,
    CONSTRAINT provider_catalogue_models_lifecycle_check CHECK (
        lifecycle_state IN ('draft', 'approved', 'deprecated', 'disabled')
    ),
    CONSTRAINT provider_catalogue_models_task_kinds_present CHECK (
        array_length(supported_task_kinds, 1) >= 1
    ),
    CONSTRAINT provider_catalogue_models_context_window_positive CHECK (
        context_window_tokens IS NULL OR context_window_tokens >= 1
    )
);

CREATE TABLE IF NOT EXISTS model_route_versions (
    route_id uuid NOT NULL,
    route_version integer NOT NULL,
    lifecycle_state text NOT NULL,
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    agent_role text NOT NULL,
    task_kind text NOT NULL,
    tenant_tier text NOT NULL,
    provider_catalogue_id text NOT NULL,
    provider_id text NOT NULL,
    model_id text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    budget_cap_usd numeric(12, 4) NOT NULL,
    max_latency_ms integer NOT NULL,
    fallback_policy jsonb NOT NULL,
    eval_required boolean NOT NULL,
    eval_fixture_refs text[] NOT NULL DEFAULT ARRAY[]::text[],
    promotion jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (route_id, route_version),
    FOREIGN KEY (provider_catalogue_id, provider_id, model_id)
        REFERENCES provider_catalogue_models (catalogue_id, provider_id, model_id)
        ON DELETE RESTRICT,
    CONSTRAINT model_route_versions_version_positive CHECK (route_version >= 1),
    CONSTRAINT model_route_versions_lifecycle_check CHECK (
        lifecycle_state IN ('draft', 'approved', 'deprecated', 'disabled', 'rolled_back')
    ),
    CONSTRAINT model_route_versions_agent_role_check CHECK (
        agent_role IN ('intake', 'researcher', 'qualifier', 'drafter', 'validator')
    ),
    CONSTRAINT model_route_versions_tier_check CHECK (
        tenant_tier IN ('demo', 'standard', 'regulated')
    ),
    CONSTRAINT model_route_versions_budget_non_negative CHECK (budget_cap_usd >= 0),
    CONSTRAINT model_route_versions_latency_positive CHECK (max_latency_ms >= 1),
    UNIQUE (tenant_id, agent_role, task_kind, tenant_tier, route_version)
);

CREATE INDEX IF NOT EXISTS provider_catalogue_providers_state_idx
    ON provider_catalogue_providers (catalogue_id, lifecycle_state, provider_kind);

CREATE INDEX IF NOT EXISTS provider_catalogue_models_state_idx
    ON provider_catalogue_models (catalogue_id, provider_id, lifecycle_state);

CREATE INDEX IF NOT EXISTS model_route_versions_lookup_idx
    ON model_route_versions (tenant_id, agent_role, task_kind, tenant_tier, route_version);

CREATE UNIQUE INDEX IF NOT EXISTS model_route_versions_approved_route_idx
    ON model_route_versions (tenant_id, agent_role, task_kind, tenant_tier)
    WHERE lifecycle_state = 'approved';

CREATE OR REPLACE FUNCTION prevent_model_route_version_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'model_route_versions are immutable; insert a new version instead';
END;
$$;

DROP TRIGGER IF EXISTS model_route_versions_immutable ON model_route_versions;
CREATE TRIGGER model_route_versions_immutable
    BEFORE UPDATE OR DELETE ON model_route_versions
    FOR EACH ROW
    EXECUTE FUNCTION prevent_model_route_version_mutation();

ALTER TABLE model_route_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS model_route_versions_tenant_isolation ON model_route_versions;
CREATE POLICY model_route_versions_tenant_isolation ON model_route_versions
    FOR SELECT TO chorus_app
    USING (tenant_id = chorus_current_tenant_id());

GRANT SELECT ON
    provider_catalogues,
    provider_catalogue_providers,
    provider_catalogue_models,
    model_route_versions
TO chorus_app;

COMMENT ON TABLE provider_catalogues IS 'Global provider catalogue metadata for Phase 2 provider/model governance inspection.';
COMMENT ON TABLE provider_catalogue_providers IS 'Provider lifecycle, credential, data-boundary, operational-limit, and audit metadata.';
COMMENT ON TABLE provider_catalogue_models IS 'Models declared by each provider catalogue entry, including task support and cost policy.';
COMMENT ON TABLE model_route_versions IS 'Tenant-scoped immutable model-route versions; Phase 1 runtime still reads model_routing_policies.';
