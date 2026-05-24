-- Chorus Postgres current-state baseline for the R4 local POC.
--
-- The baseline creates the current tenant-scoped policy, audit, transcript,
-- projection, approval, provider-governance, and outbox substrate. It is
-- deliberately idempotent so a local database that has already applied the
-- previous migration chain can record this baseline without a destructive
-- reset.

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
        role IN (
            'aml_assessor',
            'capacity_assessor',
            'classifier',
            'conflict_analyst',
            'context_gatherer',
            'engagement_decider',
            'qualifier',
            'request_drafter',
            'research_analyst',
            'risk_analyst',
            'suitability_decider',
            'validator'
        )
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
    runtime_route_id text NOT NULL DEFAULT 'recorded-replay',
    provider text NOT NULL,
    model text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    budget_cap_usd numeric(12, 4) NOT NULL,
    fallback_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    lifecycle_state text NOT NULL DEFAULT 'approved',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT model_routing_agent_role_check CHECK (
        agent_role IN (
            'classifier',
            'context_gatherer',
            'qualifier',
            'request_drafter',
            'validator'
        )
    ),
    CONSTRAINT model_routing_tier_check CHECK (tenant_tier IN ('demo', 'standard', 'regulated')),
    CONSTRAINT model_routing_lifecycle_check CHECK (
        lifecycle_state IN ('draft', 'approved', 'deprecated', 'disabled')
    ),
    CONSTRAINT model_routing_runtime_route_id_shape CHECK (
        runtime_route_id ~ '^[a-z][a-z0-9_.-]*$'
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
            'calendar.lookup_availability',
            'calendar.propose_hold',
            'calendar.create_hold',
            'calendar.cancel_hold',
            'crm.route_to_quoting_queue',
            'referral_inbox.route',
            'decline_ledger.route',
            'outbound_comms.message',
            'customer_profile.lookup',
            'product_catalogue.lookup',
            'conflict_check.search',
            'kyc_bo.lookup',
            'aml_record_store.record_assessment',
            'engagement_letter.draft',
            'engagement_letter.send',
            'engagement_letter.record_decline',
            'engagement_letter.route_manual_review',
            'attitude_to_risk.profile',
            'capacity_for_loss.assess',
            'platform_research.run',
            'suitability_report.draft',
            'suitability_report.issue',
            'suitability_report.record_decline',
            'suitability_report.route_manual_review'
        )
    ),
    CONSTRAINT tool_grants_mode_check CHECK (mode IN ('read', 'propose', 'write')),
    UNIQUE (tenant_id, agent_id, agent_version, tool_name, mode)
);

CREATE TABLE IF NOT EXISTS workflow_read_models (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    workflow_id text NOT NULL,
    correlation_id text NOT NULL,
    workflow_type text NOT NULL,
    subject_id uuid NOT NULL,
    subject_ref text,
    status text NOT NULL,
    current_step text,
    subject_summary text NOT NULL DEFAULT '',
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
    CONSTRAINT workflow_read_models_sequence_non_negative CHECK (last_event_sequence >= 0),
    CONSTRAINT workflow_read_models_workflow_type_check CHECK (
        workflow_type IN (
            'uc1_enquiry_qualification',
            'uc2_legal_services_intake_conflict_check',
            'uc3_ifa_suitability_intake'
        )
    ),
    CONSTRAINT workflow_read_models_subject_ref_shape CHECK (
        subject_ref IS NULL
        OR subject_ref ~ '^(enq|legal_intake|advice_enquiry)_[A-Za-z0-9_-]+$'
    ),
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
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, invocation_id),
    CONSTRAINT decision_trail_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT decision_trail_agent_role_check CHECK (
        agent_role IN (
            'classifier',
            'context_gatherer',
            'qualifier',
            'request_drafter',
            'validator'
        )
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
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
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
            'calendar.lookup_availability',
            'calendar.propose_hold',
            'calendar.create_hold',
            'calendar.cancel_hold',
            'crm.route_to_quoting_queue',
            'referral_inbox.route',
            'decline_ledger.route',
            'outbound_comms.message',
            'customer_profile.lookup',
            'product_catalogue.lookup',
            'conflict_check.search',
            'kyc_bo.lookup',
            'aml_record_store.record_assessment',
            'engagement_letter.draft',
            'engagement_letter.send',
            'engagement_letter.record_decline',
            'engagement_letter.route_manual_review',
            'attitude_to_risk.profile',
            'capacity_for_loss.assess',
            'platform_research.run',
            'suitability_report.draft',
            'suitability_report.issue',
            'suitability_report.record_decline',
            'suitability_report.route_manual_review'
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

CREATE TABLE IF NOT EXISTS local_customer_profiles (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    customer_ref text NOT NULL,
    display_name_category text NOT NULL,
    vulnerability_markers text[] NOT NULL DEFAULT ARRAY[]::text[],
    consent_state_category text NOT NULL,
    profile_status text NOT NULL DEFAULT 'active',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, customer_ref),
    CONSTRAINT local_customer_profiles_ref_shape CHECK (
        customer_ref ~ '^cust_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_customer_profiles_display_name_check CHECK (
        display_name_category IN (
            'individual_personal_lines',
            'household_personal_lines'
        )
    ),
    CONSTRAINT local_customer_profiles_vulnerability_markers_check CHECK (
        vulnerability_markers <@ ARRAY[
            'bereavement_declared',
            'communication_adjustment_requested',
            'financial_difficulty_declared',
            'health_condition_declared'
        ]::text[]
    ),
    CONSTRAINT local_customer_profiles_consent_state_check CHECK (
        consent_state_category IN (
            'marketing_opt_in',
            'marketing_opt_out',
            'service_contact_only'
        )
    ),
    CONSTRAINT local_customer_profiles_status_check CHECK (
        profile_status IN ('active', 'archived')
    )
);

CREATE TABLE IF NOT EXISTS local_product_catalogue_entries (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    product_family_category text NOT NULL,
    target_market_summary_category text NOT NULL,
    min_age_category text,
    construction_categories text[] NOT NULL DEFAULT ARRAY[]::text[],
    excluded_postcode_categories text[] NOT NULL DEFAULT ARRAY[]::text[],
    fair_value_assessment_ref text NOT NULL,
    catalogue_status text NOT NULL DEFAULT 'active',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, product_family_category),
    CONSTRAINT local_product_catalogue_family_check CHECK (
        product_family_category IN (
            'motor_private_car',
            'motor_commercial_vehicle',
            'home_buildings',
            'home_contents',
            'home_combined',
            'travel_single_trip',
            'travel_annual_multi_trip',
            'pet'
        )
    ),
    CONSTRAINT local_product_catalogue_target_market_check CHECK (
        target_market_summary_category IN (
            'uk_resident_private_motor_standard',
            'uk_resident_homeowner_buildings'
        )
    ),
    CONSTRAINT local_product_catalogue_min_age_check CHECK (
        min_age_category IS NULL
        OR min_age_category IN ('age_25_plus')
    ),
    CONSTRAINT local_product_catalogue_construction_check CHECK (
        construction_categories <@ ARRAY[
            'standard_brick',
            'standard_stone'
        ]::text[]
    ),
    CONSTRAINT local_product_catalogue_postcode_exclusion_check CHECK (
        excluded_postcode_categories <@ ARRAY[
            'flood_zone_3',
            'high_theft_metropolitan'
        ]::text[]
    ),
    CONSTRAINT local_product_catalogue_fva_ref_shape CHECK (
        fair_value_assessment_ref ~ '^fva_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_product_catalogue_status_check CHECK (
        catalogue_status IN ('active', 'archived')
    )
);

CREATE TABLE IF NOT EXISTS local_quoting_queue_routes (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    queued_route_ref text NOT NULL,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    connector_invocation_id uuid NOT NULL,
    mode text NOT NULL,
    enquiry_ref text NOT NULL,
    customer_ref text NOT NULL,
    verdict_ref text NOT NULL,
    product_family_category text NOT NULL,
    qualification_summary_ref text NOT NULL,
    routing_policy_ref text NOT NULL,
    route_status text NOT NULL DEFAULT 'queued',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, queued_route_ref),
    CONSTRAINT local_quoting_queue_ref_shape CHECK (
        queued_route_ref ~ '^qroute_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_quoting_queue_correlation_shape CHECK (
        correlation_id ~ '^cor_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_quoting_queue_mode_check CHECK (mode IN ('read', 'propose', 'write')),
    CONSTRAINT local_quoting_queue_enquiry_ref_shape CHECK (
        enquiry_ref ~ '^enq_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_quoting_queue_customer_ref_shape CHECK (
        customer_ref ~ '^cust_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_quoting_queue_verdict_ref_shape CHECK (
        verdict_ref ~ '^verdict_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_quoting_queue_product_family_check CHECK (
        product_family_category IN (
            'motor_private_car',
            'motor_commercial_vehicle',
            'home_buildings',
            'home_contents',
            'home_combined',
            'travel_single_trip',
            'travel_annual_multi_trip',
            'pet'
        )
    ),
    CONSTRAINT local_quoting_queue_summary_ref_shape CHECK (
        qualification_summary_ref ~ '^qsum_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_quoting_queue_policy_ref_shape CHECK (
        routing_policy_ref ~ '^policy_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_quoting_queue_status_check CHECK (route_status IN ('queued')),
    UNIQUE (tenant_id, verdict_ref)
);

CREATE TABLE IF NOT EXISTS local_referral_inbox_routes (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    referral_route_ref text NOT NULL,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    connector_invocation_id uuid NOT NULL,
    mode text NOT NULL,
    enquiry_ref text NOT NULL,
    customer_ref text NOT NULL,
    verdict_ref text NOT NULL,
    referral_destination_category text NOT NULL,
    referral_reason_category text NOT NULL,
    routing_policy_ref text NOT NULL,
    route_status text NOT NULL DEFAULT 'routed',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, referral_route_ref),
    CONSTRAINT local_referral_inbox_ref_shape CHECK (
        referral_route_ref ~ '^rroute_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_referral_inbox_correlation_shape CHECK (
        correlation_id ~ '^cor_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_referral_inbox_mode_check CHECK (mode IN ('read', 'propose', 'write')),
    CONSTRAINT local_referral_inbox_enquiry_ref_shape CHECK (
        enquiry_ref ~ '^enq_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_referral_inbox_customer_ref_shape CHECK (
        customer_ref ~ '^cust_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_referral_inbox_verdict_ref_shape CHECK (
        verdict_ref ~ '^verdict_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_referral_inbox_destination_check CHECK (
        referral_destination_category IN (
            'specialist_broker_panel',
            'managing_general_agent',
            'subscription_market',
            'partner_intermediary',
            'internal_complex_risk_desk'
        )
    ),
    CONSTRAINT local_referral_inbox_reason_check CHECK (
        referral_reason_category IN (
            'customer_outside_target_market',
            'complex_risk_outside_appetite',
            'capacity_constraint',
            'regulatory_restriction',
            'customer_vulnerability_handoff',
            'partner_owns_relationship'
        )
    ),
    CONSTRAINT local_referral_inbox_policy_ref_shape CHECK (
        routing_policy_ref ~ '^policy_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_referral_inbox_status_check CHECK (route_status IN ('routed')),
    UNIQUE (tenant_id, verdict_ref)
);

CREATE TABLE IF NOT EXISTS local_decline_ledger_routes (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    decline_route_ref text NOT NULL,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    connector_invocation_id uuid NOT NULL,
    mode text NOT NULL,
    enquiry_ref text NOT NULL,
    customer_ref text NOT NULL,
    verdict_ref text NOT NULL,
    decline_reason_category text NOT NULL,
    routing_policy_ref text NOT NULL,
    route_status text NOT NULL DEFAULT 'recorded',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, decline_route_ref),
    CONSTRAINT local_decline_ledger_ref_shape CHECK (
        decline_route_ref ~ '^droute_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_decline_ledger_correlation_shape CHECK (
        correlation_id ~ '^cor_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_decline_ledger_mode_check CHECK (mode IN ('read', 'propose', 'write')),
    CONSTRAINT local_decline_ledger_enquiry_ref_shape CHECK (
        enquiry_ref ~ '^enq_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_decline_ledger_customer_ref_shape CHECK (
        customer_ref ~ '^cust_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_decline_ledger_verdict_ref_shape CHECK (
        verdict_ref ~ '^verdict_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_decline_ledger_reason_check CHECK (
        decline_reason_category IN (
            'no_appetite_for_risk',
            'sanctions_or_pep_hit',
            'fraud_marker_present',
            'kyc_failure',
            'duplicate_active_enquiry',
            'customer_unreachable_after_attempts',
            'outside_product_target_market'
        )
    ),
    CONSTRAINT local_decline_ledger_policy_ref_shape CHECK (
        routing_policy_ref ~ '^policy_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_decline_ledger_status_check CHECK (route_status IN ('recorded')),
    UNIQUE (tenant_id, verdict_ref)
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
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT workflow_history_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT workflow_history_event_type_check CHECK (
        event_type IN (
            'enquiry.received',
            'workflow.started',
            'workflow.step.started',
            'workflow.step.completed',
            'workflow.completed',
            'workflow.escalated',
            'workflow.failed'
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
    workflow_type text NOT NULL,
    subject_id uuid NOT NULL,
    subject_ref text,
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
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT outbox_schema_name_check CHECK (schema_name = 'workflow_event'),
    CONSTRAINT outbox_schema_version_check CHECK (schema_version = '1.0.0'),
    CONSTRAINT outbox_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT outbox_event_type_check CHECK (
        event_type IN (
            'enquiry.received',
            'workflow.started',
            'workflow.step.started',
            'workflow.step.completed',
            'workflow.completed',
            'workflow.escalated',
            'workflow.failed'
        )
    ),
    CONSTRAINT outbox_sequence_positive CHECK (sequence >= 1),
    CONSTRAINT outbox_status_check CHECK (status IN ('pending', 'publishing', 'sent', 'failed', 'dlq')),
    CONSTRAINT outbox_attempts_non_negative CHECK (attempts >= 0),
    CONSTRAINT outbox_workflow_type_check CHECK (
        workflow_type IN (
            'uc1_enquiry_qualification',
            'uc2_legal_services_intake_conflict_check',
            'uc3_ifa_suitability_intake'
        )
    ),
    CONSTRAINT outbox_subject_ref_shape CHECK (
        subject_ref IS NULL
        OR subject_ref ~ '^(enq|legal_intake|advice_enquiry)_[A-Za-z0-9_-]+$'
    ),
    UNIQUE (tenant_id, workflow_id, sequence)
);

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
    runtime_route_id text NOT NULL,
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
        agent_role IN (
            'classifier',
            'context_gatherer',
            'qualifier',
            'request_drafter',
            'validator'
        )
    ),
    CONSTRAINT model_route_versions_tier_check CHECK (
        tenant_tier IN ('demo', 'standard', 'regulated')
    ),
    CONSTRAINT model_route_versions_runtime_route_id_shape CHECK (
        runtime_route_id ~ '^[a-z][a-z0-9_.-]*$'
    ),
    CONSTRAINT model_route_versions_budget_non_negative CHECK (budget_cap_usd >= 0),
    CONSTRAINT model_route_versions_latency_positive CHECK (max_latency_ms >= 1),
    UNIQUE (tenant_id, agent_role, task_kind, tenant_tier, route_version)
);

CREATE TABLE IF NOT EXISTS policy_snapshots (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    policy_snapshot_ref text NOT NULL,
    workflow_type text NOT NULL,
    snapshot_version text NOT NULL,
    lifecycle_state text NOT NULL DEFAULT 'active',
    effective_from timestamptz NOT NULL,
    policy_bundle jsonb NOT NULL,
    source_refs jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_hash text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, policy_snapshot_ref),
    CONSTRAINT policy_snapshots_ref_shape CHECK (
        policy_snapshot_ref ~ '^policy_snapshot:[a-z0-9_:-]+$'
    ),
    CONSTRAINT policy_snapshots_workflow_type_check CHECK (
        workflow_type IN (
            'uc1_enquiry_qualification',
            'uc2_legal_services_intake_conflict_check',
            'uc3_ifa_suitability_intake'
        )
    ),
    CONSTRAINT policy_snapshots_version_shape CHECK (snapshot_version ~ '^v[0-9]+$'),
    CONSTRAINT policy_snapshots_lifecycle_check CHECK (
        lifecycle_state IN ('active', 'deprecated', 'disabled')
    ),
    CONSTRAINT policy_snapshots_bundle_object_check CHECK (
        jsonb_typeof(policy_bundle) = 'object'
    ),
    CONSTRAINT policy_snapshots_source_refs_object_check CHECK (
        jsonb_typeof(source_refs) = 'object'
    ),
    CONSTRAINT policy_snapshots_metadata_object_check CHECK (jsonb_typeof(metadata) = 'object'),
    CONSTRAINT policy_snapshots_content_hash_shape CHECK (
        content_hash ~ '^sha256:[a-f0-9]{64}$'
    )
);

CREATE TABLE IF NOT EXISTS approval_packages (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    approval_id uuid NOT NULL,
    approval_package_version integer NOT NULL DEFAULT 1,
    approval_state text NOT NULL DEFAULT 'requested',
    decision text,
    reason_category text NOT NULL DEFAULT 'tool_write_risk',
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    workflow_type text NOT NULL,
    invocation_id uuid NOT NULL,
    tool_call_id uuid NOT NULL,
    verdict_id uuid NOT NULL,
    source_audit_event_id uuid NOT NULL,
    authority_context_id text,
    tool_authority_context_id text,
    agent_id text NOT NULL,
    agent_version text NOT NULL,
    task_kind text,
    requested_action text NOT NULL,
    tool_name text NOT NULL,
    requested_mode text NOT NULL,
    enforced_mode text NOT NULL,
    idempotency_key_ref text NOT NULL,
    redaction_policy_ref text NOT NULL,
    redaction_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    requested_at timestamptz NOT NULL,
    decision_due_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    sla_policy_ref text NOT NULL,
    escalation_policy_ref text,
    reviewer_actor_subject_ref text,
    reviewer_actor_session_id text,
    reviewer_role text,
    reviewer_trust_domain text NOT NULL DEFAULT 'local.chorus',
    decision_at timestamptz,
    requested_by_workload_principal_id text,
    requested_by_workload_session_id text,
    decided_by_workload_principal_id text,
    decided_by_workload_session_id text,
    trust_domain text NOT NULL DEFAULT 'local.chorus',
    grant_id uuid REFERENCES tool_grants (grant_id) ON DELETE RESTRICT,
    policy_version_refs jsonb NOT NULL DEFAULT '{}'::jsonb,
    trace_join jsonb NOT NULL DEFAULT '{}'::jsonb,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, approval_id),
    FOREIGN KEY (tenant_id, source_audit_event_id)
        REFERENCES tool_action_audit (tenant_id, audit_event_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, agent_id, agent_version)
        REFERENCES agent_registry (tenant_id, agent_id, version)
        ON DELETE RESTRICT,
    CONSTRAINT approval_packages_version_positive CHECK (approval_package_version >= 1),
    CONSTRAINT approval_packages_state_check CHECK (
        approval_state IN ('requested', 'approved', 'denied', 'expired', 'cancelled', 'superseded')
    ),
    CONSTRAINT approval_packages_decision_check CHECK (
        decision IS NULL OR decision IN ('approved', 'denied', 'expired', 'cancelled')
    ),
    CONSTRAINT approval_packages_reason_category_check CHECK (
        reason_category IN (
            'tool_write_risk',
            'data_sensitivity',
            'customer_impact',
            'policy_exception',
            'mode_escalation',
            'connector_risk',
            'duplicate_or_superseded',
            'sla_expired',
            'cancelled_by_requester',
            'other_bounded'
        )
    ),
    CONSTRAINT approval_packages_correlation_shape CHECK (
        correlation_id ~ '^cor_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT approval_packages_workflow_type_check CHECK (
        workflow_type IN (
            'uc1_enquiry_qualification',
            'uc2_legal_services_intake_conflict_check',
            'uc3_ifa_suitability_intake'
        )
    ),
    CONSTRAINT approval_packages_tool_name_check CHECK (
        tool_name ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'
    ),
    CONSTRAINT approval_packages_mode_check CHECK (
        requested_mode = 'write' AND enforced_mode = 'write'
    ),
    CONSTRAINT approval_packages_requested_action_check CHECK (
        requested_action = tool_name || '.' || requested_mode
        AND requested_action ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+\.(read|propose|write)$'
    ),
    CONSTRAINT approval_packages_idempotency_ref_shape CHECK (
        idempotency_key_ref ~ '^sha256:[a-f0-9]{64}$'
    ),
    CONSTRAINT approval_packages_expiry_order_check CHECK (decision_due_at <= expires_at)
);

CREATE TABLE IF NOT EXISTS agent_invocation_transcripts (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    transcript_id uuid NOT NULL,
    invocation_id uuid NOT NULL,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    route_id text NOT NULL,
    provider_id text NOT NULL,
    model_id text NOT NULL,
    adapter_version text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    messages jsonb NOT NULL,
    tool_calls jsonb NOT NULL DEFAULT '[]'::jsonb,
    response_body jsonb,
    token_usage jsonb NOT NULL DEFAULT '{}'::jsonb,
    provider_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    raw_record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, transcript_id),
    CONSTRAINT transcript_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT transcript_messages_is_array CHECK (jsonb_typeof(messages) = 'array'),
    CONSTRAINT transcript_tool_calls_is_array CHECK (jsonb_typeof(tool_calls) = 'array')
);

CREATE TABLE IF NOT EXISTS replay_run_records (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    replay_run_id uuid NOT NULL,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    original_invocation_id uuid NOT NULL,
    original_transcript_id uuid NOT NULL,
    original_runtime_route_id text NOT NULL,
    original_provider_id text NOT NULL,
    original_model_id text NOT NULL,
    original_adapter_version text NOT NULL,
    original_parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    alternate_runtime_route_id text NOT NULL,
    alternate_provider_id text NOT NULL,
    alternate_model_id text NOT NULL,
    alternate_adapter_version text NOT NULL,
    alternate_parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    agent_role text NOT NULL,
    task_kind text NOT NULL,
    policy_snapshot_ref text,
    prompt_reference text NOT NULL,
    prompt_hash text NOT NULL,
    response_schema_name text NOT NULL,
    response_schema_contract_ref text NOT NULL,
    response_schema_hash text NOT NULL,
    route_version_ref text,
    provider_catalogue_id text,
    eval_fixture_ref text,
    transcript_source_ref text,
    comparator_name text NOT NULL,
    comparator_version text NOT NULL,
    comparator_status text NOT NULL,
    comparator_result jsonb NOT NULL,
    safe_error_reason text,
    safe_skipped_reason text,
    original_cost_amount numeric(12, 6) NOT NULL,
    original_cost_currency text NOT NULL DEFAULT 'USD',
    original_latency_ms integer NOT NULL,
    original_token_usage jsonb NOT NULL DEFAULT '{}'::jsonb,
    alternate_cost_amount numeric(12, 6) NOT NULL,
    alternate_cost_currency text NOT NULL DEFAULT 'USD',
    alternate_latency_ms integer NOT NULL,
    alternate_token_usage jsonb NOT NULL DEFAULT '{}'::jsonb,
    metric_deltas jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    raw_record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, replay_run_id),
    FOREIGN KEY (tenant_id, original_invocation_id)
        REFERENCES decision_trail_entries (tenant_id, invocation_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, original_transcript_id)
        REFERENCES agent_invocation_transcripts (tenant_id, transcript_id)
        ON DELETE RESTRICT,
    CONSTRAINT replay_run_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT replay_run_original_route_shape CHECK (
        original_runtime_route_id ~ '^[a-z][a-z0-9_.-]*$'
    ),
    CONSTRAINT replay_run_alternate_route_shape CHECK (
        alternate_runtime_route_id ~ '^[a-z][a-z0-9_.-]*$'
    ),
    CONSTRAINT replay_run_agent_role_check CHECK (
        agent_role IN (
            'classifier',
            'context_gatherer',
            'qualifier',
            'request_drafter',
            'validator'
        )
    ),
    CONSTRAINT replay_run_prompt_hash_shape CHECK (prompt_hash ~ '^sha256:[a-f0-9]{64}$'),
    CONSTRAINT replay_run_response_schema_hash_shape CHECK (
        response_schema_hash ~ '^sha256:[a-f0-9]{64}$'
    ),
    CONSTRAINT replay_run_comparator_status_check CHECK (
        comparator_status IN ('pass', 'fail', 'skipped', 'error')
    ),
    CONSTRAINT replay_run_original_currency_check CHECK (original_cost_currency = 'USD'),
    CONSTRAINT replay_run_alternate_currency_check CHECK (alternate_cost_currency = 'USD'),
    CONSTRAINT replay_run_original_cost_non_negative CHECK (original_cost_amount >= 0),
    CONSTRAINT replay_run_alternate_cost_non_negative CHECK (alternate_cost_amount >= 0),
    CONSTRAINT replay_run_original_latency_non_negative CHECK (original_latency_ms >= 0),
    CONSTRAINT replay_run_alternate_latency_non_negative CHECK (alternate_latency_ms >= 0),
    CONSTRAINT replay_run_original_parameters_is_object CHECK (
        jsonb_typeof(original_parameters) = 'object'
    ),
    CONSTRAINT replay_run_alternate_parameters_is_object CHECK (
        jsonb_typeof(alternate_parameters) = 'object'
    ),
    CONSTRAINT replay_run_comparator_result_is_object CHECK (
        jsonb_typeof(comparator_result) = 'object'
    ),
    CONSTRAINT replay_run_metric_deltas_is_object CHECK (jsonb_typeof(metric_deltas) = 'object'),
    CONSTRAINT replay_run_original_token_usage_is_object CHECK (
        jsonb_typeof(original_token_usage) = 'object'
    ),
    CONSTRAINT replay_run_alternate_token_usage_is_object CHECK (
        jsonb_typeof(alternate_token_usage) = 'object'
    ),
    CONSTRAINT replay_run_raw_record_is_object CHECK (jsonb_typeof(raw_record) = 'object')
);

-- Bring already-created local databases forward to the current projection
-- column names without rewriting data.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'workflow_read_models'
          AND column_name = 'lead_id'
    )
    AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'workflow_read_models'
          AND column_name = 'subject_id'
    ) THEN
        ALTER TABLE workflow_read_models RENAME COLUMN lead_id TO subject_id;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'workflow_read_models'
          AND column_name = 'lead_summary'
    )
    AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'workflow_read_models'
          AND column_name = 'subject_summary'
    ) THEN
        ALTER TABLE workflow_read_models RENAME COLUMN lead_summary TO subject_summary;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'outbox_events'
          AND column_name = 'lead_id'
    )
    AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'outbox_events'
          AND column_name = 'subject_id'
    ) THEN
        ALTER TABLE outbox_events RENAME COLUMN lead_id TO subject_id;
    END IF;
END
$$;

ALTER TABLE workflow_read_models
    ADD COLUMN IF NOT EXISTS subject_ref text,
    ADD COLUMN IF NOT EXISTS workflow_type text NOT NULL DEFAULT 'uc1_enquiry_qualification',
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE workflow_read_models ALTER COLUMN workflow_type DROP DEFAULT;

ALTER TABLE workflow_history_events
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE decision_trail_entries
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE tool_action_audit
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE outbox_events
    ADD COLUMN IF NOT EXISTS subject_ref text,
    ADD COLUMN IF NOT EXISTS workflow_type text NOT NULL DEFAULT 'uc1_enquiry_qualification',
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE outbox_events ALTER COLUMN workflow_type DROP DEFAULT;

ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS agent_registry_role_check;
ALTER TABLE agent_registry ADD CONSTRAINT agent_registry_role_check CHECK (
    role IN (
        'classifier',
        'context_gatherer',
        'qualifier',
        'request_drafter',
        'validator'
    )
);

ALTER TABLE model_routing_policies DROP CONSTRAINT IF EXISTS model_routing_agent_role_check;
ALTER TABLE model_routing_policies ADD CONSTRAINT model_routing_agent_role_check CHECK (
    agent_role IN (
        'classifier',
        'context_gatherer',
        'qualifier',
        'request_drafter',
        'validator'
    )
);

ALTER TABLE model_routing_policies ADD COLUMN IF NOT EXISTS runtime_route_id text;
UPDATE model_routing_policies
SET runtime_route_id = CASE
    WHEN provider = 'deepseek' THEN 'dev'
    WHEN provider = 'openai' THEN 'demo-eval-canonical'
    ELSE 'recorded-replay'
END
WHERE runtime_route_id IS NULL;
ALTER TABLE model_routing_policies ALTER COLUMN runtime_route_id SET DEFAULT 'recorded-replay';
ALTER TABLE model_routing_policies ALTER COLUMN runtime_route_id SET NOT NULL;
ALTER TABLE model_routing_policies DROP CONSTRAINT IF EXISTS model_routing_runtime_route_id_shape;
ALTER TABLE model_routing_policies ADD CONSTRAINT model_routing_runtime_route_id_shape CHECK (
    runtime_route_id ~ '^[a-z][a-z0-9_.-]*$'
);

ALTER TABLE decision_trail_entries DROP CONSTRAINT IF EXISTS decision_trail_agent_role_check;
ALTER TABLE decision_trail_entries ADD CONSTRAINT decision_trail_agent_role_check CHECK (
    agent_role IN (
        'classifier',
        'context_gatherer',
        'qualifier',
        'request_drafter',
        'validator'
    )
);

ALTER TABLE model_route_versions DROP CONSTRAINT IF EXISTS model_route_versions_agent_role_check;
ALTER TABLE model_route_versions ADD CONSTRAINT model_route_versions_agent_role_check CHECK (
    agent_role IN (
        'classifier',
        'context_gatherer',
        'qualifier',
        'request_drafter',
        'validator'
    )
);

DROP TRIGGER IF EXISTS model_route_versions_immutable ON model_route_versions;
ALTER TABLE model_route_versions ADD COLUMN IF NOT EXISTS runtime_route_id text;
UPDATE model_route_versions
SET runtime_route_id = CASE
    WHEN provider_id = 'deepseek' THEN 'dev'
    WHEN provider_id = 'openai' THEN 'demo-eval-canonical'
    ELSE 'recorded-replay'
END
WHERE runtime_route_id IS NULL;
ALTER TABLE model_route_versions ALTER COLUMN runtime_route_id SET NOT NULL;
ALTER TABLE model_route_versions DROP CONSTRAINT IF EXISTS model_route_versions_runtime_route_id_shape;
ALTER TABLE model_route_versions ADD CONSTRAINT model_route_versions_runtime_route_id_shape CHECK (
    runtime_route_id ~ '^[a-z][a-z0-9_.-]*$'
);
UPDATE model_route_versions
SET eval_fixture_refs = ARRAY[
    'chorus/eval/fixtures/uc1_happy_path.json',
    'chorus/eval/fixtures/uc1_validator_redraft.json',
    'chorus/eval/fixtures/uc1_accepted_routing.json',
    'chorus/eval/fixtures/uc1_referred_routing.json',
    'chorus/eval/fixtures/uc1_declined_routing.json'
]::text[]
WHERE provider_id = 'local'
  AND model_id = 'uc1-happy-path-v1'
  AND (
      eval_fixture_refs IS NULL
      OR array_length(eval_fixture_refs, 1) IS NULL
  );

ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS agent_registry_role_check;
ALTER TABLE agent_registry ADD CONSTRAINT agent_registry_role_check CHECK (
    role IN (
        'aml_assessor',
        'capacity_assessor',
        'classifier',
        'conflict_analyst',
        'context_gatherer',
        'engagement_decider',
        'qualifier',
        'request_drafter',
        'research_analyst',
        'risk_analyst',
        'suitability_decider',
        'validator'
    )
);

ALTER TABLE tool_grants DROP CONSTRAINT IF EXISTS tool_grants_tool_name_check;
ALTER TABLE tool_grants ADD CONSTRAINT tool_grants_tool_name_check CHECK (
    tool_name IN (
        'calendar.lookup_availability',
        'calendar.propose_hold',
        'calendar.create_hold',
        'calendar.cancel_hold',
        'crm.route_to_quoting_queue',
        'referral_inbox.route',
        'decline_ledger.route',
        'outbound_comms.message',
        'customer_profile.lookup',
        'product_catalogue.lookup',
        'conflict_check.search',
        'kyc_bo.lookup',
        'aml_record_store.record_assessment',
        'engagement_letter.draft',
        'engagement_letter.send',
        'engagement_letter.record_decline',
        'engagement_letter.route_manual_review',
        'attitude_to_risk.profile',
        'capacity_for_loss.assess',
        'platform_research.run',
        'suitability_report.draft',
        'suitability_report.issue',
        'suitability_report.record_decline',
        'suitability_report.route_manual_review'
    )
);

ALTER TABLE tool_action_audit DROP CONSTRAINT IF EXISTS tool_action_tool_name_check;
ALTER TABLE tool_action_audit ADD CONSTRAINT tool_action_tool_name_check CHECK (
    tool_name IS NULL
    OR tool_name IN (
        'calendar.lookup_availability',
        'calendar.propose_hold',
        'calendar.create_hold',
        'calendar.cancel_hold',
        'crm.route_to_quoting_queue',
        'referral_inbox.route',
        'decline_ledger.route',
        'outbound_comms.message',
        'customer_profile.lookup',
        'product_catalogue.lookup',
        'conflict_check.search',
        'kyc_bo.lookup',
        'aml_record_store.record_assessment',
        'engagement_letter.draft',
        'engagement_letter.send',
        'engagement_letter.record_decline',
        'engagement_letter.route_manual_review',
        'attitude_to_risk.profile',
        'capacity_for_loss.assess',
        'platform_research.run',
        'suitability_report.draft',
        'suitability_report.issue',
        'suitability_report.record_decline',
        'suitability_report.route_manual_review'
    )
);

ALTER TABLE workflow_read_models DROP CONSTRAINT IF EXISTS workflow_read_models_step_check;
ALTER TABLE workflow_read_models DROP CONSTRAINT IF EXISTS workflow_read_models_workflow_type_check;
ALTER TABLE workflow_read_models ADD CONSTRAINT workflow_read_models_workflow_type_check CHECK (
    workflow_type IN (
        'uc1_enquiry_qualification',
        'uc2_legal_services_intake_conflict_check',
        'uc3_ifa_suitability_intake'
    )
);
ALTER TABLE workflow_read_models DROP CONSTRAINT IF EXISTS workflow_read_models_subject_ref_shape;
ALTER TABLE workflow_read_models ADD CONSTRAINT workflow_read_models_subject_ref_shape CHECK (
    subject_ref IS NULL
    OR subject_ref ~ '^(enq|legal_intake|advice_enquiry)_[A-Za-z0-9_-]+$'
);

ALTER TABLE workflow_history_events DROP CONSTRAINT IF EXISTS workflow_history_step_check;
ALTER TABLE workflow_history_events DROP CONSTRAINT IF EXISTS workflow_history_event_type_check;
ALTER TABLE workflow_history_events ADD CONSTRAINT workflow_history_event_type_check CHECK (
    event_type IN (
        'enquiry.received',
        'workflow.started',
        'workflow.step.started',
        'workflow.step.completed',
        'workflow.completed',
        'workflow.escalated',
        'workflow.failed'
    )
);

ALTER TABLE outbox_events DROP CONSTRAINT IF EXISTS outbox_step_check;
ALTER TABLE outbox_events DROP CONSTRAINT IF EXISTS outbox_event_type_check;
ALTER TABLE outbox_events ADD CONSTRAINT outbox_event_type_check CHECK (
    event_type IN (
        'enquiry.received',
        'workflow.started',
        'workflow.step.started',
        'workflow.step.completed',
        'workflow.completed',
        'workflow.escalated',
        'workflow.failed'
    )
);
ALTER TABLE outbox_events DROP CONSTRAINT IF EXISTS outbox_status_check;
ALTER TABLE outbox_events ADD CONSTRAINT outbox_status_check CHECK (
    status IN ('pending', 'publishing', 'sent', 'failed', 'dlq')
);
ALTER TABLE outbox_events DROP CONSTRAINT IF EXISTS outbox_workflow_type_check;
ALTER TABLE outbox_events ADD CONSTRAINT outbox_workflow_type_check CHECK (
    workflow_type IN (
        'uc1_enquiry_qualification',
        'uc2_legal_services_intake_conflict_check',
        'uc3_ifa_suitability_intake'
    )
);
ALTER TABLE outbox_events DROP CONSTRAINT IF EXISTS outbox_subject_ref_shape;
ALTER TABLE outbox_events ADD CONSTRAINT outbox_subject_ref_shape CHECK (
    subject_ref IS NULL
    OR subject_ref ~ '^(enq|legal_intake|advice_enquiry)_[A-Za-z0-9_-]+$'
);

ALTER TABLE approval_packages DROP CONSTRAINT IF EXISTS approval_packages_workflow_type_check;
ALTER TABLE approval_packages ADD CONSTRAINT approval_packages_workflow_type_check CHECK (
    workflow_type IN (
        'uc1_enquiry_qualification',
        'uc2_legal_services_intake_conflict_check',
        'uc3_ifa_suitability_intake'
    )
);
ALTER TABLE approval_packages DROP CONSTRAINT IF EXISTS approval_packages_tool_name_check;
ALTER TABLE approval_packages ADD CONSTRAINT approval_packages_tool_name_check CHECK (
    tool_name ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$'
);
ALTER TABLE approval_packages DROP CONSTRAINT IF EXISTS approval_packages_requested_action_check;
ALTER TABLE approval_packages ADD CONSTRAINT approval_packages_requested_action_check CHECK (
    requested_action = tool_name || '.' || requested_mode
    AND requested_action ~ '^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+\.(read|propose|write)$'
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

CREATE INDEX IF NOT EXISTS local_customer_profiles_status_idx
    ON local_customer_profiles (tenant_id, profile_status, customer_ref);

CREATE INDEX IF NOT EXISTS local_product_catalogue_status_idx
    ON local_product_catalogue_entries (tenant_id, catalogue_status, product_family_category);

CREATE INDEX IF NOT EXISTS local_quoting_queue_workflow_idx
    ON local_quoting_queue_routes (tenant_id, workflow_id, created_at DESC);

CREATE INDEX IF NOT EXISTS local_referral_inbox_workflow_idx
    ON local_referral_inbox_routes (tenant_id, workflow_id, created_at DESC);

CREATE INDEX IF NOT EXISTS local_decline_ledger_workflow_idx
    ON local_decline_ledger_routes (tenant_id, workflow_id, created_at DESC);

CREATE INDEX IF NOT EXISTS workflow_history_workflow_idx
    ON workflow_history_events (tenant_id, workflow_id, sequence);

CREATE INDEX IF NOT EXISTS outbox_pending_idx
    ON outbox_events (status, next_attempt_at, created_at)
    WHERE status IN ('pending', 'failed');

CREATE INDEX IF NOT EXISTS outbox_dlq_idx
    ON outbox_events (tenant_id, workflow_id, updated_at)
    WHERE status = 'dlq';

CREATE INDEX IF NOT EXISTS provider_catalogue_providers_state_idx
    ON provider_catalogue_providers (catalogue_id, lifecycle_state, provider_kind);

CREATE INDEX IF NOT EXISTS provider_catalogue_models_state_idx
    ON provider_catalogue_models (catalogue_id, provider_id, lifecycle_state);

CREATE INDEX IF NOT EXISTS model_route_versions_lookup_idx
    ON model_route_versions (tenant_id, agent_role, task_kind, tenant_tier, route_version);

CREATE UNIQUE INDEX IF NOT EXISTS model_route_versions_approved_route_idx
    ON model_route_versions (tenant_id, agent_role, task_kind, tenant_tier)
    WHERE lifecycle_state = 'approved';

CREATE INDEX IF NOT EXISTS policy_snapshots_lookup_idx
    ON policy_snapshots (tenant_id, workflow_type, lifecycle_state, effective_from DESC);

CREATE UNIQUE INDEX IF NOT EXISTS approval_packages_idempotency_idx
    ON approval_packages (tenant_id, tool_name, idempotency_key_ref);

CREATE INDEX IF NOT EXISTS approval_packages_workflow_idx
    ON approval_packages (tenant_id, workflow_id, requested_at DESC);

CREATE INDEX IF NOT EXISTS approval_packages_state_idx
    ON approval_packages (tenant_id, approval_state, decision_due_at);

CREATE UNIQUE INDEX IF NOT EXISTS agent_invocation_transcripts_invocation_idx
    ON agent_invocation_transcripts (tenant_id, invocation_id);

CREATE INDEX IF NOT EXISTS agent_invocation_transcripts_workflow_idx
    ON agent_invocation_transcripts (tenant_id, workflow_id, started_at);

CREATE INDEX IF NOT EXISTS agent_invocation_transcripts_route_idx
    ON agent_invocation_transcripts (tenant_id, route_id, completed_at);

CREATE INDEX IF NOT EXISTS replay_run_records_workflow_idx
    ON replay_run_records (tenant_id, workflow_id, completed_at DESC);

CREATE INDEX IF NOT EXISTS replay_run_records_original_invocation_idx
    ON replay_run_records (tenant_id, original_invocation_id, completed_at DESC);

CREATE INDEX IF NOT EXISTS replay_run_records_alternate_route_idx
    ON replay_run_records (tenant_id, alternate_runtime_route_id, comparator_status);

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

CREATE OR REPLACE FUNCTION prevent_policy_snapshot_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'policy_snapshots are immutable; insert a new snapshot ref instead';
END;
$$;

DROP TRIGGER IF EXISTS policy_snapshots_immutable ON policy_snapshots;
CREATE TRIGGER policy_snapshots_immutable
    BEFORE UPDATE OR DELETE ON policy_snapshots
    FOR EACH ROW
    EXECUTE FUNCTION prevent_policy_snapshot_mutation();

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_registry ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_routing_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_read_models ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_trail_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE tool_action_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE local_customer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE local_product_catalogue_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE local_quoting_queue_routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE local_referral_inbox_routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE local_decline_ledger_routes ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_history_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_route_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_packages ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_invocation_transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE replay_run_records ENABLE ROW LEVEL SECURITY;

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

DROP POLICY IF EXISTS local_customer_profiles_tenant_isolation
    ON local_customer_profiles;
CREATE POLICY local_customer_profiles_tenant_isolation ON local_customer_profiles
    FOR SELECT TO chorus_app
    USING (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS local_product_catalogue_entries_tenant_isolation
    ON local_product_catalogue_entries;
CREATE POLICY local_product_catalogue_entries_tenant_isolation
    ON local_product_catalogue_entries
    FOR SELECT TO chorus_app
    USING (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS local_quoting_queue_routes_tenant_isolation
    ON local_quoting_queue_routes;
CREATE POLICY local_quoting_queue_routes_tenant_isolation ON local_quoting_queue_routes
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS local_referral_inbox_routes_tenant_isolation
    ON local_referral_inbox_routes;
CREATE POLICY local_referral_inbox_routes_tenant_isolation ON local_referral_inbox_routes
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS local_decline_ledger_routes_tenant_isolation
    ON local_decline_ledger_routes;
CREATE POLICY local_decline_ledger_routes_tenant_isolation ON local_decline_ledger_routes
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

DROP POLICY IF EXISTS model_route_versions_tenant_isolation ON model_route_versions;
CREATE POLICY model_route_versions_tenant_isolation ON model_route_versions
    FOR SELECT TO chorus_app
    USING (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS policy_snapshots_tenant_isolation ON policy_snapshots;
CREATE POLICY policy_snapshots_tenant_isolation ON policy_snapshots
    FOR SELECT TO chorus_app
    USING (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS approval_packages_tenant_isolation ON approval_packages;
CREATE POLICY approval_packages_tenant_isolation ON approval_packages
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS agent_invocation_transcripts_tenant_isolation
    ON agent_invocation_transcripts;
CREATE POLICY agent_invocation_transcripts_tenant_isolation
    ON agent_invocation_transcripts
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS replay_run_records_tenant_isolation
    ON replay_run_records;
CREATE POLICY replay_run_records_tenant_isolation
    ON replay_run_records
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
    local_quoting_queue_routes,
    local_referral_inbox_routes,
    local_decline_ledger_routes,
    workflow_history_events,
    outbox_events
TO chorus_app;

GRANT SELECT ON
    local_customer_profiles,
    local_product_catalogue_entries
TO chorus_app;

GRANT SELECT ON
    provider_catalogues,
    provider_catalogue_providers,
    provider_catalogue_models,
    model_route_versions,
    policy_snapshots
TO chorus_app;

GRANT SELECT, INSERT, UPDATE ON approval_packages TO chorus_app;
GRANT SELECT, INSERT ON agent_invocation_transcripts TO chorus_app;
GRANT SELECT, INSERT, UPDATE ON replay_run_records TO chorus_app;

COMMENT ON TABLE tenants IS 'Seeded local tenant boundary for tenant-isolation evidence.';
COMMENT ON TABLE agent_registry IS 'Tenant-scoped governed agent registry materialised for runtime resolution.';
COMMENT ON TABLE model_routing_policies IS 'Tenant-scoped runtime-route and provider/model policy materialised for Agent Runtime lookup.';
COMMENT ON TABLE tool_grants IS 'Tenant-scoped Tool Gateway authority grants keyed by agent, tool, and mode.';
COMMENT ON TABLE workflow_read_models IS
    'Projection consumed by the BFF/UI for refresh-safe UC1 enquiry-qualification status.';
COMMENT ON TABLE decision_trail_entries IS
    'Durable Agent Runtime decision trail aligned with the agent_invocation_record contract.';
COMMENT ON TABLE tool_action_audit IS
    'Authority-sensitive Tool Gateway and connector audit trail aligned with audit/tool contracts.';
COMMENT ON TABLE local_customer_profiles IS
    'Tenant-scoped synthetic UC1 customer-of-record rows for sandbox profile lookups.';
COMMENT ON TABLE local_product_catalogue_entries IS
    'Tenant-scoped synthetic UC1 product target-market rows for sandbox catalogue lookups.';
COMMENT ON TABLE local_quoting_queue_routes IS
    'Local UC1 sandbox CRM records for accept verdicts routed to the quoting queue.';
COMMENT ON TABLE local_referral_inbox_routes IS
    'Local UC1 sandbox referral-inbox records for refer verdicts routed to specialist review.';
COMMENT ON TABLE local_decline_ledger_routes IS
    'Local UC1 sandbox decline-ledger records for declined enquiries.';
COMMENT ON TABLE workflow_history_events IS
    'Append-only UC1 enquiry-qualification workflow event history.';
COMMENT ON TABLE outbox_events IS
    'Transactional outbox aligned with the workflow_event contract for Redpanda publication.';
COMMENT ON TABLE provider_catalogues IS
    'Global provider catalogue metadata for provider/model governance inspection.';
COMMENT ON TABLE provider_catalogue_providers IS
    'Provider lifecycle, credential, data-boundary, operational-limit, and audit metadata.';
COMMENT ON TABLE provider_catalogue_models IS
    'Models declared by each provider catalogue entry, including task support and cost policy.';
COMMENT ON TABLE model_route_versions IS
    'Tenant-scoped immutable runtime-route/provider/model versions for governance inspection.';
COMMENT ON TABLE policy_snapshots IS
    'Tenant-scoped immutable local policy bundles behind policy_snapshot_ref values emitted by governed decisions.';
COMMENT ON TABLE approval_packages IS
    'Local approval package evidence for Tool Gateway approval-required connector writes.';
COMMENT ON TABLE agent_invocation_transcripts IS
    'Full-fidelity transcript port records for replayable governed agent invocations.';
COMMENT ON TABLE replay_run_records IS
    'Replay-eval evidence records linking captured invocations and transcripts to alternate route comparator outcomes and metrics.';
