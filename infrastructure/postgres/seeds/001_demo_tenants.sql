-- Demo tenant seed data for local R4 governance and connector authority.
--
-- Two tenants are intentionally present so RLS and fail-closed tests can prove
-- tenant-owned tables do not leak rows across the runtime boundary.

INSERT INTO tenants (tenant_id, display_name, tenant_tier, status, metadata)
VALUES
    (
        'tenant_demo',
        'Chorus UC1 Demo Tenant',
        'demo',
        'active',
        '{"purpose": "primary UC1 enquiry-qualification demo path"}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'Chorus UC1 Isolation Tenant',
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
        'uc1.classifier',
        'classifier',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/classifier/v1.md',
        'sha256:6e25aca95c76a38b089fedbcac94316a47e18a9d2575089363f5c35f1cbcd67e',
        ARRAY['uc1', 'classification']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo',
        'uc1.context_gatherer',
        'context_gatherer',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/context-gatherer/v1.md',
        'sha256:ebbbcc8091838ce2962642f3436b1188bef35fe0dc8ab67ededd475aaa683e20',
        ARRAY['uc1', 'context']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo',
        'uc1.qualifier',
        'qualifier',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/qualifier/v1.md',
        'sha256:2877d857fba0d2dc974e73968977dfd5072568b03aca9ed8adb73fab01d17f5f',
        ARRAY['uc1', 'qualification']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo',
        'uc1.request_drafter',
        'request_drafter',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/request-drafter/v1.md',
        'sha256:e25a62fe7137f6f88a0987cb9897417532a7a5dc807eb954a48c3b770923bcbd',
        ARRAY['uc1', 'missing_data_request']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo',
        'uc1.validator',
        'validator',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/validator/v1.md',
        'sha256:157b1c9e3b0916bed7814bd01e912c62d38b87d4ceee9af25807f7b062fc0743',
        ARRAY['uc1', 'validation']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'uc1.classifier',
        'classifier',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/classifier/v1.md',
        'sha256:6e25aca95c76a38b089fedbcac94316a47e18a9d2575089363f5c35f1cbcd67e',
        ARRAY['uc1', 'classification']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'uc1.context_gatherer',
        'context_gatherer',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/context-gatherer/v1.md',
        'sha256:ebbbcc8091838ce2962642f3436b1188bef35fe0dc8ab67ededd475aaa683e20',
        ARRAY['uc1', 'context']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'uc1.qualifier',
        'qualifier',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/qualifier/v1.md',
        'sha256:2877d857fba0d2dc974e73968977dfd5072568b03aca9ed8adb73fab01d17f5f',
        ARRAY['uc1', 'qualification']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'uc1.request_drafter',
        'request_drafter',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/request-drafter/v1.md',
        'sha256:e25a62fe7137f6f88a0987cb9897417532a7a5dc807eb954a48c3b770923bcbd',
        ARRAY['uc1', 'missing_data_request']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'uc1.validator',
        'validator',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc1/validator/v1.md',
        'sha256:157b1c9e3b0916bed7814bd01e912c62d38b87d4ceee9af25807f7b062fc0743',
        ARRAY['uc1', 'validation']::text[],
        '{"seed": true}'::jsonb
    ),
    (
        'tenant_demo',
        'uc2.conflict_analyst',
        'conflict_analyst',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc2/conflict-analyst/v1.md',
        'sha256:dbcaf349e3a5184d036c07560706207c6c0e8ef5630e1ead1a7cc77152290bec',
        ARRAY['uc2', 'conflict_check', 'tool_gateway_grant_owner']::text[],
        '{"seed": true, "evidence": "UC2 Tool Gateway grant owner; provider route pending"}'::jsonb
    ),
    (
        'tenant_demo',
        'uc2.aml_assessor',
        'aml_assessor',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc2/aml-assessor/v1.md',
        'sha256:64d3092ca8f9d7c6431318799c3532f877dc74b47c72ccfb238dcb8f5d0af1ef',
        ARRAY['uc2', 'kyc_bo', 'aml_record_store', 'tool_gateway_grant_owner']::text[],
        '{"seed": true, "evidence": "UC2 Tool Gateway grant owner; provider route pending"}'::jsonb
    ),
    (
        'tenant_demo',
        'uc2.engagement_decider',
        'engagement_decider',
        'v1',
        'approved',
        'agent-runtime',
        'prompts/uc2/engagement-decider/v1.md',
        'sha256:8f793f9105211157a8f2faead42229753d9b7574efc491515816cda7aecf58e2',
        ARRAY['uc2', 'engagement_letter', 'tool_gateway_grant_owner']::text[],
        '{"seed": true, "evidence": "UC2 Tool Gateway grant owner; provider route pending"}'::jsonb
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
    runtime_route_id,
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
        'classifier',
        'enquiry_classification',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0.2}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000002',
        'tenant_demo',
        'context_gatherer',
        'context_gathering',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0.2}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000003',
        'tenant_demo',
        'qualifier',
        'enquiry_qualification',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0.1}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000004',
        'tenant_demo',
        'request_drafter',
        'missing_data_request_draft',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0.3}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000005',
        'tenant_demo',
        'validator',
        'missing_data_request_validation',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000006',
        'tenant_demo_alt',
        'classifier',
        'enquiry_classification',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0.2}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000007',
        'tenant_demo_alt',
        'qualifier',
        'enquiry_qualification',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0.1}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000008',
        'tenant_demo_alt',
        'request_drafter',
        'missing_data_request_draft',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0.3}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    ),
    (
        '11000000-0000-4000-8000-000000000009',
        'tenant_demo_alt',
        'validator',
        'missing_data_request_validation',
        'demo',
        'recorded-replay',
        'local',
        'uc1-happy-path-v1',
        '{"temperature": 0}'::jsonb,
        0.0100,
        '{"on_provider_error": "escalate"}'::jsonb,
        'approved'
    )
ON CONFLICT (tenant_id, agent_role, task_kind, tenant_tier) DO UPDATE
SET
    runtime_route_id = EXCLUDED.runtime_route_id,
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
        'uc1.context_gatherer',
        'v1',
        'customer_profile.lookup',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC1 customer profile read"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000002',
        'tenant_demo',
        'uc1.context_gatherer',
        'v1',
        'product_catalogue.lookup',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC1 product target-market read"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000003',
        'tenant_demo',
        'uc1.qualifier',
        'v1',
        'crm.route_to_quoting_queue',
        'write',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC1 accept verdict routes to quoting queue"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000004',
        'tenant_demo',
        'uc1.qualifier',
        'v1',
        'referral_inbox.route',
        'write',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC1 refer verdict routes to referral inbox"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000005',
        'tenant_demo',
        'uc1.qualifier',
        'v1',
        'decline_ledger.route',
        'write',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC1 decline verdict routes to decline ledger"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000006',
        'tenant_demo',
        'uc1.request_drafter',
        'v1',
        'outbound_comms.message',
        'propose',
        true,
        false,
        '{"redact_fields": ["body_text"]}'::jsonb,
        '{"seed": true, "evidence": "UC1 missing-data request draft captured before approval"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000007',
        'tenant_demo',
        'uc1.request_drafter',
        'v1',
        'outbound_comms.message',
        'write',
        true,
        true,
        '{"redact_fields": ["body_text"]}'::jsonb,
        '{"seed": true, "evidence": "UC1 send remains approval-required"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000008',
        'tenant_demo',
        'uc1.request_drafter',
        'v1',
        'calendar.lookup_availability',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "local CalDAV availability lookup"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000009',
        'tenant_demo',
        'uc1.request_drafter',
        'v1',
        'calendar.propose_hold',
        'propose',
        true,
        false,
        '{"redact_fields": ["participant_refs", "proposal_note_ref"]}'::jsonb,
        '{"seed": true, "evidence": "local CalDAV hold proposal without event creation"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000010',
        'tenant_demo',
        'uc1.request_drafter',
        'v1',
        'calendar.create_hold',
        'write',
        true,
        true,
        '{"redact_fields": ["participant_refs"]}'::jsonb,
        '{"seed": true, "evidence": "calendar write remains approval-required"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000011',
        'tenant_demo',
        'uc1.request_drafter',
        'v1',
        'calendar.cancel_hold',
        'write',
        true,
        true,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "calendar cancellation remains approval-required"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000013',
        'tenant_demo',
        'uc2.conflict_analyst',
        'v1',
        'conflict_check.search',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC2 conflict-check read through Tool Gateway"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000014',
        'tenant_demo',
        'uc2.aml_assessor',
        'v1',
        'kyc_bo.lookup',
        'read',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC2 KYC and beneficial-ownership read through Tool Gateway"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000015',
        'tenant_demo',
        'uc2.aml_assessor',
        'v1',
        'aml_record_store.record_assessment',
        'write',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC2 AML risk-assessment record write; EDD approval package remains pending workflow semantics"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000016',
        'tenant_demo',
        'uc2.engagement_decider',
        'v1',
        'engagement_letter.draft',
        'write',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC2 engagement-letter draft record write"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000017',
        'tenant_demo',
        'uc2.engagement_decider',
        'v1',
        'engagement_letter.send',
        'write',
        true,
        true,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC2 engagement-letter send is approval-required"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000018',
        'tenant_demo',
        'uc2.engagement_decider',
        'v1',
        'engagement_letter.record_decline',
        'write',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC2 decline-to-act routing record write"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000019',
        'tenant_demo',
        'uc2.engagement_decider',
        'v1',
        'engagement_letter.route_manual_review',
        'write',
        true,
        false,
        '{"redact_fields": []}'::jsonb,
        '{"seed": true, "evidence": "UC2 manual-review handoff routing record write"}'::jsonb
    ),
    (
        '12000000-0000-4000-8000-000000000012',
        'tenant_demo_alt',
        'uc1.request_drafter',
        'v1',
        'outbound_comms.message',
        'write',
        false,
        false,
        '{"redact_fields": ["body_text"]}'::jsonb,
        '{"seed": true, "evidence": "forbidden write block scenario"}'::jsonb
    )
ON CONFLICT (tenant_id, agent_id, agent_version, tool_name, mode) DO UPDATE
SET
    allowed = EXCLUDED.allowed,
    approval_required = EXCLUDED.approval_required,
    redaction_policy = EXCLUDED.redaction_policy,
    metadata = EXCLUDED.metadata,
    updated_at = now();
