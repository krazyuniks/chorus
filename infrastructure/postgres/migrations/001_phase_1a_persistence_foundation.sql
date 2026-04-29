-- Phase 1A persistence foundation for Chorus.
--
-- This migration establishes the Postgres-owned governance, audit,
-- projection, and outbox tables used by the Lighthouse slice. Temporal remains
-- the workflow state authority; these tables are read models, policy
-- materialisation, audit evidence, and event-publication state.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'chorus_app') THEN
        CREATE ROLE chorus_app NOLOGIN;
    END IF;
END
$$;

CREATE OR REPLACE FUNCTION chorus_current_tenant_id()
RETURNS text
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(current_setting('app.tenant_id', true), '')
$$;

CREATE TABLE IF NOT EXISTS tenants (
    tenant_id text PRIMARY KEY,
    display_name text NOT NULL,
    tenant_tier text NOT NULL DEFAULT 'demo',
    status text NOT NULL DEFAULT 'active',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tenants_tenant_id_shape CHECK (tenant_id ~ '^tenant_[a-z0-9_]+$'),
    CONSTRAINT tenants_tier_check CHECK (tenant_tier IN ('demo', 'standard', 'regulated')),
    CONSTRAINT tenants_status_check CHECK (status IN ('active', 'suspended', 'disabled'))
);

CREATE TABLE IF NOT EXISTS agent_registry (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    agent_id text NOT NULL,
    role text NOT NULL,
    version text NOT NULL,
    lifecycle_state text NOT NULL,
    owner text NOT NULL,
    prompt_reference text NOT NULL,
    prompt_hash text NOT NULL,
    capability_tags text[] NOT NULL DEFAULT ARRAY[]::text[],
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, agent_id, version),
    CONSTRAINT agent_registry_role_check CHECK (
        role IN ('intake', 'researcher', 'qualifier', 'drafter', 'validator')
    ),
    CONSTRAINT agent_registry_version_shape CHECK (version ~ '^v[0-9]+$'),
    CONSTRAINT agent_registry_lifecycle_check CHECK (
        lifecycle_state IN ('draft', 'approved', 'deprecated', 'disabled')
    ),
    CONSTRAINT agent_registry_prompt_hash_shape CHECK (prompt_hash ~ '^sha256:[a-f0-9]{64}$')
);

CREATE TABLE IF NOT EXISTS model_routing_policies (
    policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    agent_role text NOT NULL,
    task_kind text NOT NULL,
    tenant_tier text NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    budget_cap_usd numeric(12, 4) NOT NULL,
    fallback_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    lifecycle_state text NOT NULL DEFAULT 'approved',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_routing_agent_role_check CHECK (
        agent_role IN ('intake', 'researcher', 'qualifier', 'drafter', 'validator')
    ),
    CONSTRAINT model_routing_tier_check CHECK (tenant_tier IN ('demo', 'standard', 'regulated')),
    CONSTRAINT model_routing_lifecycle_check CHECK (
        lifecycle_state IN ('draft', 'approved', 'deprecated', 'disabled')
    ),
    CONSTRAINT model_routing_budget_non_negative CHECK (budget_cap_usd >= 0),
    UNIQUE (tenant_id, agent_role, task_kind, tenant_tier)
);

CREATE TABLE IF NOT EXISTS tool_grants (
    grant_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    agent_id text NOT NULL,
    agent_version text NOT NULL,
    tool_name text NOT NULL,
    mode text NOT NULL,
    allowed boolean NOT NULL DEFAULT true,
    approval_required boolean NOT NULL DEFAULT false,
    redaction_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (tenant_id, agent_id, agent_version)
        REFERENCES agent_registry (tenant_id, agent_id, version)
        ON DELETE RESTRICT,
    CONSTRAINT tool_grants_tool_name_check CHECK (
        tool_name IN (
            'company_research.lookup',
            'crm.lookup_company',
            'crm.create_lead',
            'email.propose_response',
            'email.send_response'
        )
    ),
    CONSTRAINT tool_grants_mode_check CHECK (mode IN ('read', 'propose', 'write')),
    UNIQUE (tenant_id, agent_id, agent_version, tool_name, mode)
);

CREATE TABLE IF NOT EXISTS workflow_read_models (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    workflow_id text NOT NULL,
    correlation_id text NOT NULL,
    lead_id uuid NOT NULL,
    status text NOT NULL,
    current_step text,
    lead_summary text NOT NULL DEFAULT '',
    last_event_id uuid,
    last_event_sequence integer NOT NULL DEFAULT 0,
    started_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (tenant_id, workflow_id),
    CONSTRAINT workflow_read_models_correlation_shape CHECK (
        correlation_id ~ '^cor_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT workflow_read_models_status_check CHECK (
        status IN ('received', 'running', 'completed', 'escalated', 'failed')
    ),
    CONSTRAINT workflow_read_models_step_check CHECK (
        current_step IS NULL
        OR current_step IN (
            'intake',
            'research_qualification',
            'draft',
            'validation',
            'propose_send',
            'complete',
            'escalate'
        )
    ),
    CONSTRAINT workflow_read_models_sequence_non_negative CHECK (last_event_sequence >= 0),
    UNIQUE (tenant_id, correlation_id)
);

CREATE TABLE IF NOT EXISTS decision_trail_entries (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    invocation_id uuid NOT NULL,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    agent_id text NOT NULL,
    agent_role text NOT NULL,
    agent_version text NOT NULL,
    lifecycle_state text NOT NULL,
    prompt_reference text NOT NULL,
    prompt_hash text NOT NULL,
    provider text NOT NULL,
    model text NOT NULL,
    task_kind text NOT NULL,
    budget_cap_usd numeric(12, 4) NOT NULL,
    input_summary text NOT NULL,
    output_summary text NOT NULL,
    justification text NOT NULL,
    outcome text NOT NULL,
    tool_call_ids uuid[] NOT NULL DEFAULT ARRAY[]::uuid[],
    cost_amount numeric(12, 6) NOT NULL,
    cost_currency text NOT NULL DEFAULT 'USD',
    duration_ms integer NOT NULL,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    contract_refs text[] NOT NULL,
    raw_record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, invocation_id),
    CONSTRAINT decision_trail_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT decision_trail_agent_role_check CHECK (
        agent_role IN ('intake', 'researcher', 'qualifier', 'drafter', 'validator')
    ),
    CONSTRAINT decision_trail_lifecycle_check CHECK (
        lifecycle_state IN ('draft', 'approved', 'deprecated', 'disabled')
    ),
    CONSTRAINT decision_trail_prompt_hash_shape CHECK (prompt_hash ~ '^sha256:[a-f0-9]{64}$'),
    CONSTRAINT decision_trail_outcome_check CHECK (outcome IN ('succeeded', 'failed', 'escalated')),
    CONSTRAINT decision_trail_cost_currency_check CHECK (cost_currency = 'USD'),
    CONSTRAINT decision_trail_budget_non_negative CHECK (budget_cap_usd >= 0),
    CONSTRAINT decision_trail_cost_non_negative CHECK (cost_amount >= 0),
    CONSTRAINT decision_trail_duration_non_negative CHECK (duration_ms >= 0),
    CONSTRAINT decision_trail_contract_refs_present CHECK (array_length(contract_refs, 1) >= 1)
);

CREATE TABLE IF NOT EXISTS tool_action_audit (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    audit_event_id uuid NOT NULL,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    invocation_id uuid,
    tool_call_id uuid,
    verdict_id uuid,
    actor_type text NOT NULL,
    actor_id text NOT NULL,
    category text NOT NULL,
    action text NOT NULL,
    tool_name text,
    requested_mode text,
    enforced_mode text,
    verdict text NOT NULL,
    idempotency_key text,
    arguments_redacted jsonb NOT NULL DEFAULT '{}'::jsonb,
    rewritten_arguments jsonb,
    reason text,
    connector_invocation_id uuid,
    occurred_at timestamptz NOT NULL,
    raw_event jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, audit_event_id),
    CONSTRAINT tool_action_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT tool_action_actor_type_check CHECK (actor_type IN ('agent', 'system', 'human')),
    CONSTRAINT tool_action_category_check CHECK (
        category IN ('runtime', 'workflow', 'tool_gateway', 'connector', 'policy')
    ),
    CONSTRAINT tool_action_tool_name_check CHECK (
        tool_name IS NULL
        OR tool_name IN (
            'company_research.lookup',
            'crm.lookup_company',
            'crm.create_lead',
            'email.propose_response',
            'email.send_response'
        )
    ),
    CONSTRAINT tool_action_requested_mode_check CHECK (
        requested_mode IS NULL OR requested_mode IN ('read', 'propose', 'write')
    ),
    CONSTRAINT tool_action_enforced_mode_check CHECK (
        enforced_mode IS NULL OR enforced_mode IN ('read', 'propose', 'write')
    ),
    CONSTRAINT tool_action_verdict_check CHECK (
        verdict IN ('allow', 'rewrite', 'propose', 'approval_required', 'block', 'recorded')
    )
);

CREATE TABLE IF NOT EXISTS workflow_history_events (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    history_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id text NOT NULL,
    correlation_id text NOT NULL,
    source_event_id uuid NOT NULL,
    event_type text NOT NULL,
    sequence integer NOT NULL,
    step text,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT workflow_history_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT workflow_history_event_type_check CHECK (
        event_type IN (
            'lead.received',
            'workflow.started',
            'workflow.step.started',
            'workflow.step.completed',
            'workflow.completed',
            'workflow.escalated',
            'workflow.failed'
        )
    ),
    CONSTRAINT workflow_history_step_check CHECK (
        step IS NULL
        OR step IN (
            'intake',
            'research_qualification',
            'draft',
            'validation',
            'propose_send',
            'complete',
            'escalate'
        )
    ),
    CONSTRAINT workflow_history_sequence_positive CHECK (sequence >= 1),
    UNIQUE (tenant_id, workflow_id, sequence),
    UNIQUE (tenant_id, source_event_id)
);

CREATE TABLE IF NOT EXISTS outbox_events (
    outbox_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_name text NOT NULL DEFAULT 'workflow_event',
    schema_version text NOT NULL DEFAULT '1.0.0',
    event_id uuid NOT NULL UNIQUE,
    event_type text NOT NULL,
    occurred_at timestamptz NOT NULL,
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    lead_id uuid NOT NULL,
    sequence integer NOT NULL,
    step text,
    payload jsonb NOT NULL,
    topic text NOT NULL DEFAULT 'chorus.workflow.events.v1',
    message_key text NOT NULL,
    headers jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'pending',
    attempts integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT outbox_schema_name_check CHECK (schema_name = 'workflow_event'),
    CONSTRAINT outbox_schema_version_check CHECK (schema_version = '1.0.0'),
    CONSTRAINT outbox_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT outbox_event_type_check CHECK (
        event_type IN (
            'lead.received',
            'workflow.started',
            'workflow.step.started',
            'workflow.step.completed',
            'workflow.completed',
            'workflow.escalated',
            'workflow.failed'
        )
    ),
    CONSTRAINT outbox_step_check CHECK (
        step IS NULL
        OR step IN (
            'intake',
            'research_qualification',
            'draft',
            'validation',
            'propose_send',
            'complete',
            'escalate'
        )
    ),
    CONSTRAINT outbox_sequence_positive CHECK (sequence >= 1),
    CONSTRAINT outbox_status_check CHECK (status IN ('pending', 'publishing', 'sent', 'failed')),
    CONSTRAINT outbox_attempts_non_negative CHECK (attempts >= 0),
    UNIQUE (tenant_id, workflow_id, sequence)
);

CREATE INDEX IF NOT EXISTS agent_registry_tenant_role_idx
    ON agent_registry (tenant_id, role, lifecycle_state);

CREATE INDEX IF NOT EXISTS model_routing_lookup_idx
    ON model_routing_policies (tenant_id, agent_role, task_kind, tenant_tier);

CREATE INDEX IF NOT EXISTS tool_grants_lookup_idx
    ON tool_grants (tenant_id, agent_id, tool_name, mode) WHERE allowed;

CREATE INDEX IF NOT EXISTS workflow_read_models_status_idx
    ON workflow_read_models (tenant_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS decision_trail_workflow_idx
    ON decision_trail_entries (tenant_id, workflow_id, started_at);

CREATE INDEX IF NOT EXISTS tool_action_audit_workflow_idx
    ON tool_action_audit (tenant_id, workflow_id, occurred_at);

CREATE INDEX IF NOT EXISTS workflow_history_workflow_idx
    ON workflow_history_events (tenant_id, workflow_id, sequence);

CREATE INDEX IF NOT EXISTS outbox_pending_idx
    ON outbox_events (status, next_attempt_at, created_at)
    WHERE status IN ('pending', 'failed');

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_routing_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_read_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_trail_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_action_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_history_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenants_tenant_isolation ON tenants;
CREATE POLICY tenants_tenant_isolation ON tenants
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS agent_registry_tenant_isolation ON agent_registry;
CREATE POLICY agent_registry_tenant_isolation ON agent_registry
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS model_routing_tenant_isolation ON model_routing_policies;
CREATE POLICY model_routing_tenant_isolation ON model_routing_policies
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS tool_grants_tenant_isolation ON tool_grants;
CREATE POLICY tool_grants_tenant_isolation ON tool_grants
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS workflow_read_models_tenant_isolation ON workflow_read_models;
CREATE POLICY workflow_read_models_tenant_isolation ON workflow_read_models
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS decision_trail_tenant_isolation ON decision_trail_entries;
CREATE POLICY decision_trail_tenant_isolation ON decision_trail_entries
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS tool_action_audit_tenant_isolation ON tool_action_audit;
CREATE POLICY tool_action_audit_tenant_isolation ON tool_action_audit
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS workflow_history_tenant_isolation ON workflow_history_events;
CREATE POLICY workflow_history_tenant_isolation ON workflow_history_events
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS outbox_tenant_isolation ON outbox_events;
CREATE POLICY outbox_tenant_isolation ON outbox_events
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

GRANT USAGE ON SCHEMA public TO chorus_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    tenants,
    agent_registry,
    model_routing_policies,
    tool_grants,
    workflow_read_models,
    decision_trail_entries,
    tool_action_audit,
    workflow_history_events,
    outbox_events
TO chorus_app;

COMMENT ON TABLE tenants IS 'Seeded tenant boundary for Phase 1 tenant-isolation evidence.';
COMMENT ON TABLE agent_registry IS 'Tenant-scoped governed agent registry materialised for runtime resolution.';
COMMENT ON TABLE model_routing_policies IS 'Tenant-scoped provider/model route policy materialised for Agent Runtime lookup.';
COMMENT ON TABLE tool_grants IS 'Tenant-scoped Tool Gateway authority grants keyed by agent, tool, and mode.';
COMMENT ON TABLE workflow_read_models IS 'Projection consumed by BFF/UI for refresh-safe Lighthouse workflow status.';
COMMENT ON TABLE decision_trail_entries IS 'Durable Agent Runtime decision trail aligned with agent_invocation_record contract.';
COMMENT ON TABLE tool_action_audit IS 'Authority-sensitive Tool Gateway and connector audit trail aligned with audit/tool contracts.';
COMMENT ON TABLE workflow_history_events IS 'Append-only episodic Lighthouse workflow event history derived from workflow events.';
COMMENT ON TABLE outbox_events IS 'Transactional outbox aligned with workflow_event contract for Redpanda publication.';
