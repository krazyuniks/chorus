-- Phase 2C minimal approval package persistence for local calendar write approvals.
--
-- This table records the package created when calendar writes stop at the
-- Tool Gateway approval_required verdict. It deliberately contains only safe
-- refs, bounded categories, state, policy refs, workload refs, and trace joins.
-- It does not record reviewer decisions, raw tool arguments, connector payloads,
-- raw rationale, identity-provider claims, credentials, or PII.

CREATE TABLE IF NOT EXISTS approval_packages (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    approval_id uuid NOT NULL,
    approval_package_version integer NOT NULL DEFAULT 1,
    approval_state text NOT NULL DEFAULT 'requested',
    decision text,
    reason_category text NOT NULL DEFAULT 'tool_write_risk',
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    workflow_type text NOT NULL DEFAULT 'lighthouse',
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
    CONSTRAINT approval_packages_workflow_type_check CHECK (workflow_type = 'lighthouse'),
    CONSTRAINT approval_packages_tool_name_check CHECK (
        tool_name IN ('calendar.create_hold', 'calendar.cancel_hold')
    ),
    CONSTRAINT approval_packages_mode_check CHECK (
        requested_mode = 'write' AND enforced_mode = 'write'
    ),
    CONSTRAINT approval_packages_requested_action_check CHECK (
        requested_action IN ('calendar.create_hold.write', 'calendar.cancel_hold.write')
    ),
    CONSTRAINT approval_packages_idempotency_ref_shape CHECK (
        idempotency_key_ref ~ '^sha256:[a-f0-9]{64}$'
    ),
    CONSTRAINT approval_packages_expiry_order_check CHECK (decision_due_at <= expires_at)
);

CREATE UNIQUE INDEX IF NOT EXISTS approval_packages_idempotency_idx
    ON approval_packages (tenant_id, tool_name, idempotency_key_ref);

CREATE INDEX IF NOT EXISTS approval_packages_workflow_idx
    ON approval_packages (tenant_id, workflow_id, requested_at DESC);

CREATE INDEX IF NOT EXISTS approval_packages_state_idx
    ON approval_packages (tenant_id, approval_state, decision_due_at);

ALTER TABLE approval_packages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS approval_packages_tenant_isolation ON approval_packages;
CREATE POLICY approval_packages_tenant_isolation ON approval_packages
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

GRANT SELECT, INSERT, UPDATE ON approval_packages TO chorus_app;

COMMENT ON TABLE approval_packages IS 'Minimal local approval package evidence for Tool Gateway approval-required calendar writes.';
