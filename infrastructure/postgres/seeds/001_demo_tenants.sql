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
        'tenant_demo',
        'lighthouse.qualifier',
        'qualifier',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/lighthouse/qualifier/v1.md',
        'sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
        ARRAY['lighthouse', 'qualification']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo',
        'lighthouse.drafter',
        'drafter',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/lighthouse/drafter/v1.md',
        'sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
        ARRAY['lighthouse', 'drafting']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo',
        'lighthouse.validator',
        'validator',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/lighthouse/validator/v1.md',
        'sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
        ARRAY['lighthouse', 'validation']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo',
        'support.classifier',
        'support_classifier',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/support/classifier/v1.md',
        'sha256:6666666666666666666666666666666666666666666666666666666666666666',
        ARRAY['support', 'ticket_triage']::text[],
        '{"seed": true, "evidence": "2D-03 support workflow runtime"}'::jsonb
    ),
    (
        'tenant_demo',
        'support.context_researcher',
        'support_context_researcher',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/support/context-researcher/v1.md',
        'sha256:4444444444444444444444444444444444444444444444444444444444444444',
        ARRAY['support', 'ticket_context']::text[],
        '{"seed": true, "evidence": "2D-02 local ticket lookup"}'::jsonb
    ),
    (
        'tenant_demo',
        'support.resolution_planner',
        'support_resolution_planner',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/support/resolution-planner/v1.md',
        'sha256:5555555555555555555555555555555555555555555555555555555555555555',
        ARRAY['support', 'ticket_proposal']::text[],
        '{"seed": true, "evidence": "2D-02 local ticket proposal"}'::jsonb
    ),
    (
        'tenant_demo',
        'support.validator',
        'support_validator',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/support/validator/v1.md',
        'sha256:7777777777777777777777777777777777777777777777777777777777777777',
        ARRAY['support', 'ticket_validation']::text[],
        '{"seed": true, "evidence": "2D-03 support workflow runtime"}'::jsonb
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
    ),
    (
        'tenant_demo_alt',
        'lighthouse.qualifier',
        'qualifier',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/lighthouse/qualifier/v1.md',
        'sha256:1111111111111111111111111111111111111111111111111111111111111111',
        ARRAY['lighthouse', 'qualification']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'lighthouse.drafter',
        'drafter',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/lighthouse/drafter/v1.md',
        'sha256:2222222222222222222222222222222222222222222222222222222222222222',
        ARRAY['lighthouse', 'drafting']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'lighthouse.validator',
        'validator',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/lighthouse/validator/v1.md',
        'sha256:3333333333333333333333333333333333333333333333333333333333333333',
        ARRAY['lighthouse', 'validation']::text[],
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
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0.2}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000003',
        'tenant_demo',
        'qualifier',
        'lead_qualification',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0.1}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000004',
        'tenant_demo',
        'drafter',
        'response_draft',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0.3}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000005',
        'tenant_demo',
        'validator',
        'response_validation',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000009',
        'tenant_demo',
        'support_classifier',
        'support_classification',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000010',
        'tenant_demo',
        'support_context_researcher',
        'support_context_lookup',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000011',
        'tenant_demo',
        'support_resolution_planner',
        'support_resolution_plan',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0.1}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000012',
        'tenant_demo',
        'support_validator',
        'support_validation',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000002',
        'tenant_demo_alt',
        'researcher',
        'company_research',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0.2}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000006',
        'tenant_demo_alt',
        'qualifier',
        'lead_qualification',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0.1}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000007',
        'tenant_demo_alt',
        'drafter',
        'response_draft',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0.3}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000008',
        'tenant_demo_alt',
        'validator',
        'response_validation',
        'demo',
        'local',
        'lighthouse-happy-path-v1',
        '{"temperature": 0}'::jsonb,
        0.0100,
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
    ),
    (
        '12000000-0000-4000-8000-000000000003',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'email.propose_response',
        'propose',
        true,
        false,
        '{"redact_fields": ["body_text"]}'::jsonb,
        '{"seed": true, "evidence": "happy path outbound proposal captured by Mailpit"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000004',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'email.send_response',
        'propose',
        true,
        false,
        '{"redact_fields": ["body_text"]}'::jsonb,
        '{"seed": true, "evidence": "write downgrade target"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000005',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'crm.create_lead',
        'propose',
        true,
        false,
        '{"redact_fields": ["lead_summary"]}'::jsonb,
        '{"seed": true}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000006',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'crm.lookup_company',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000007',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'crm.create_lead',
        'write',
        true,
        true,
        '{"redact_fields": ["lead_summary"]}'::jsonb,
        '{"seed": true, "evidence": "approval hook"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000008',
        'tenant_demo_alt',
        'lighthouse.drafter',
        'v1',
        'email.send_response',
        'write',
        false,
        false,
        '{"redact_fields": ["body_text"]}'::jsonb,
        '{"seed": true, "evidence": "G-03 forbidden write block"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000009',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'calendar.lookup_availability',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "2C-02 local CalDAV availability lookup"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000010',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'calendar.propose_hold',
        'propose',
        true,
        false,
        '{"redact_fields": ["participant_refs", "proposal_note_ref"]}'::jsonb,
        '{"seed": true, "evidence": "2C-02 local CalDAV hold proposal without event creation"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000011',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'calendar.create_hold',
        'write',
        true,
        true,
        '{"redact_fields": ["participant_refs"]}'::jsonb,
        '{"seed": true, "evidence": "2C-02 calendar write remains approval-required"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000012',
        'tenant_demo',
        'lighthouse.drafter',
        'v1',
        'calendar.cancel_hold',
        'write',
        true,
        true,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "2C-02 calendar cancellation remains approval-required"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000013',
        'tenant_demo',
        'support.context_researcher',
        'v1',
        'ticket.lookup_case',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "2D-02 local ticket case lookup"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000014',
        'tenant_demo',
        'support.context_researcher',
        'v1',
        'ticket.lookup_duplicates',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "2D-02 local duplicate ticket lookup"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000015',
        'tenant_demo',
        'support.resolution_planner',
        'v1',
        'ticket.propose_case_update',
        'propose',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "2D-02 proposed ticket case update"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000016',
        'tenant_demo',
        'support.resolution_planner',
        'v1',
        'ticket.update_status',
        'write',
        true,
        true,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "2D-02 ticket status write remains approval-required"}'::jsonb
    )
ON CONFLICT (tenant_id, agent_id, agent_version, tool_name, mode) DO UPDATE
SET
    allowed = EXCLUDED.allowed,
    approval_required = EXCLUDED.approval_required,
    redaction_policy = EXCLUDED.redaction_policy,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO local_ticket_cases (
    tenant_id,
    case_ref,
    request_ref,
    account_ref,
    product_ref,
    severity_category,
    status_category,
    duplicate_group_ref,
    recent_status_refs,
    metadata
)
VALUES
    (
        'tenant_demo',
        'case_existing_001',
        'req_support_001',
        'acct_demo_001',
        'prod_core_platform',
        'sev_high',
        'open',
        'dupe_support_001',
        ARRAY['status_open_001', 'status_triaged_001']::text[],
        '{"seed": true, "evidence": "2D-02 primary local ticket case"}'::jsonb
    ),
    (
        'tenant_demo',
        'case_duplicate_001',
        'req_support_002',
        'acct_demo_001',
        'prod_core_platform',
        'sev_high',
        'pending_internal',
        'dupe_support_001',
        ARRAY['status_open_002', 'status_pending_internal_001']::text[],
        '{"seed": true, "evidence": "2D-02 duplicate local ticket case"}'::jsonb
    )
ON CONFLICT (tenant_id, case_ref) DO UPDATE
SET
    request_ref = EXCLUDED.request_ref,
    account_ref = EXCLUDED.account_ref,
    product_ref = EXCLUDED.product_ref,
    severity_category = EXCLUDED.severity_category,
    status_category = EXCLUDED.status_category,
    duplicate_group_ref = EXCLUDED.duplicate_group_ref,
    recent_status_refs = EXCLUDED.recent_status_refs,
    metadata = EXCLUDED.metadata,
    updated_at = now();
