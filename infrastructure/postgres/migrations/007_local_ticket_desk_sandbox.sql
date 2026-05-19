-- Phase 2D local ticket desk sandbox for Tool Gateway read/propose evidence.
--
-- This migration extends local policy constraints for the Phase 2D ticket tool
-- family and adds a Postgres-backed ticket desk sandbox. Tables store only
-- stable refs, bounded categories, policy refs, connector invocation refs, and
-- safe metadata. They do not store raw request content, raw tool arguments,
-- connector payloads, credentials, identity-provider claims, email addresses,
-- personal names, or PII.

ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS agent_registry_role_check;
ALTER TABLE agent_registry ADD CONSTRAINT agent_registry_role_check CHECK (
    role IN (
        'intake',
        'researcher',
        'qualifier',
        'drafter',
        'validator',
        'support_classifier',
        'support_context_researcher',
        'support_resolution_planner',
        'support_drafter',
        'support_validator'
    )
);

ALTER TABLE tool_grants DROP CONSTRAINT IF EXISTS tool_grants_tool_name_check;
ALTER TABLE tool_grants ADD CONSTRAINT tool_grants_tool_name_check CHECK (
    tool_name IN (
        'company_research.lookup',
        'crm.lookup_company',
        'crm.create_lead',
        'calendar.lookup_availability',
        'calendar.propose_hold',
        'calendar.create_hold',
        'calendar.cancel_hold',
        'ticket.lookup_case',
        'ticket.lookup_duplicates',
        'ticket.propose_case_update',
        'ticket.update_status',
        'email.propose_response',
        'email.send_response'
    )
);

ALTER TABLE tool_action_audit DROP CONSTRAINT IF EXISTS tool_action_tool_name_check;
ALTER TABLE tool_action_audit ADD CONSTRAINT tool_action_tool_name_check CHECK (
    tool_name IS NULL
    OR tool_name IN (
        'company_research.lookup',
        'crm.lookup_company',
        'crm.create_lead',
        'calendar.lookup_availability',
        'calendar.propose_hold',
        'calendar.create_hold',
        'calendar.cancel_hold',
        'ticket.lookup_case',
        'ticket.lookup_duplicates',
        'ticket.propose_case_update',
        'ticket.update_status',
        'email.propose_response',
        'email.send_response'
    )
);

CREATE TABLE IF NOT EXISTS local_ticket_cases (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    case_ref text NOT NULL,
    request_ref text,
    account_ref text NOT NULL,
    product_ref text NOT NULL,
    severity_category text NOT NULL,
    status_category text NOT NULL,
    duplicate_group_ref text,
    recent_status_refs text[] NOT NULL DEFAULT ARRAY[]::text[],
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, case_ref),
    CONSTRAINT local_ticket_cases_case_ref_shape CHECK (case_ref ~ '^case_[A-Za-z0-9_-]+$'),
    CONSTRAINT local_ticket_cases_request_ref_shape CHECK (
        request_ref IS NULL OR request_ref ~ '^req_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_cases_account_ref_shape CHECK (
        account_ref ~ '^acct_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_cases_product_ref_shape CHECK (
        product_ref ~ '^prod_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_cases_duplicate_group_ref_shape CHECK (
        duplicate_group_ref IS NULL OR duplicate_group_ref ~ '^dupe_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_cases_severity_check CHECK (
        severity_category IN ('sev_low', 'sev_medium', 'sev_high', 'sev_critical')
    ),
    CONSTRAINT local_ticket_cases_status_check CHECK (
        status_category IN (
            'new',
            'open',
            'pending_customer',
            'pending_internal',
            'resolved',
            'closed',
            'escalated'
        )
    ),
    CONSTRAINT local_ticket_cases_recent_refs_non_null CHECK (
        array_position(recent_status_refs, NULL) IS NULL
    )
);

CREATE TABLE IF NOT EXISTS local_ticket_case_update_proposals (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    case_update_ref text NOT NULL,
    connector_invocation_id uuid NOT NULL,
    request_ref text NOT NULL,
    case_ref text NOT NULL,
    account_ref text NOT NULL,
    product_ref text NOT NULL,
    severity_category text NOT NULL,
    target_status_category text NOT NULL,
    resolution_plan_ref text NOT NULL,
    response_draft_ref text NOT NULL,
    update_reason_category text NOT NULL,
    policy_ref text,
    proposal_status text NOT NULL DEFAULT 'proposed',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, case_update_ref),
    FOREIGN KEY (tenant_id, case_ref)
        REFERENCES local_ticket_cases (tenant_id, case_ref)
        ON DELETE RESTRICT,
    CONSTRAINT local_ticket_case_updates_case_update_ref_shape CHECK (
        case_update_ref ~ '^caseupd_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_case_updates_request_ref_shape CHECK (
        request_ref ~ '^req_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_case_updates_account_ref_shape CHECK (
        account_ref ~ '^acct_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_case_updates_product_ref_shape CHECK (
        product_ref ~ '^prod_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_case_updates_severity_check CHECK (
        severity_category IN ('sev_low', 'sev_medium', 'sev_high', 'sev_critical')
    ),
    CONSTRAINT local_ticket_case_updates_target_status_check CHECK (
        target_status_category IN (
            'open',
            'pending_customer',
            'pending_internal',
            'resolved',
            'escalated'
        )
    ),
    CONSTRAINT local_ticket_case_updates_resolution_plan_ref_shape CHECK (
        resolution_plan_ref ~ '^plan_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_case_updates_response_draft_ref_shape CHECK (
        response_draft_ref ~ '^response_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_case_updates_reason_check CHECK (
        update_reason_category IN (
            'triage_classification',
            'duplicate_case_found',
            'resolution_plan_ready',
            'needs_customer_response',
            'needs_internal_review',
            'escalation_required'
        )
    ),
    CONSTRAINT local_ticket_case_updates_policy_ref_shape CHECK (
        policy_ref IS NULL OR policy_ref ~ '^policy_[A-Za-z0-9_-]+$'
    ),
    CONSTRAINT local_ticket_case_updates_status_check CHECK (proposal_status = 'proposed')
);

CREATE INDEX IF NOT EXISTS local_ticket_cases_lookup_idx
    ON local_ticket_cases (tenant_id, account_ref, product_ref, status_category, updated_at DESC);

CREATE INDEX IF NOT EXISTS local_ticket_case_update_proposals_case_idx
    ON local_ticket_case_update_proposals (tenant_id, case_ref, updated_at DESC);

ALTER TABLE local_ticket_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE local_ticket_case_update_proposals ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS local_ticket_cases_tenant_isolation ON local_ticket_cases;
CREATE POLICY local_ticket_cases_tenant_isolation ON local_ticket_cases
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

DROP POLICY IF EXISTS local_ticket_case_update_proposals_tenant_isolation
    ON local_ticket_case_update_proposals;
CREATE POLICY local_ticket_case_update_proposals_tenant_isolation
    ON local_ticket_case_update_proposals
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

GRANT SELECT, INSERT, UPDATE ON
    local_ticket_cases,
    local_ticket_case_update_proposals
TO chorus_app;

COMMENT ON TABLE local_ticket_cases IS 'Local-only Phase 2D ticket desk cases using safe refs and bounded categories.';
COMMENT ON TABLE local_ticket_case_update_proposals IS 'Local-only Phase 2D ticket update proposals; proposing never mutates ticket status.';
