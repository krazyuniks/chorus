-- R3 checkpoint E: retire Support Triage and rebase the workflow tables on the
-- UC1 enquiry-qualification workflow running on the shared spine.
--
-- Drops the Phase 2D Support Triage runtime artefacts entirely, retires the
-- Lighthouse-shaped column names on the workflow projection tables, and
-- relaxes the previously Lighthouse-locked CHECK constraints so the step
-- taxonomy lives in the workflow definition rather than the DB schema. UC2
-- and UC3 join in R4 by adding new role / tool grants and new workflow_type
-- values; no further migration of the projection tables is required.

-- 1. Drop the local Support Triage / ticket sandbox tables.

DROP TABLE IF EXISTS local_ticket_case_update_proposals;
DROP TABLE IF EXISTS local_ticket_cases;

-- 2. Drop the seeded Support Triage agents and ticket-tool grants. The seed
--    file no longer reseeds them, but applied tenants need their rows removed.

DELETE FROM tool_grants
WHERE tool_name IN (
    'ticket.lookup_case',
    'ticket.lookup_duplicates',
    'ticket.propose_case_update',
    'ticket.update_status',
    'company_research.lookup',
    'crm.lookup_company',
    'crm.create_lead',
    'email.propose_response',
    'email.send_response'
);

DELETE FROM model_routing_policies
WHERE agent_role IN (
    'support_classifier',
    'support_context_researcher',
    'support_resolution_planner',
    'support_drafter',
    'support_validator',
    'researcher',
    'qualifier',
    'drafter',
    'validator',
    'intake'
);

DELETE FROM agent_registry
WHERE agent_id IN (
    'lighthouse.researcher',
    'lighthouse.qualifier',
    'lighthouse.drafter',
    'lighthouse.validator',
    'support.classifier',
    'support.context_researcher',
    'support.resolution_planner',
    'support.validator'
);

-- 3. Replace the Lighthouse-locked role / tool-name CHECK constraints with the
--    UC1-shaped allowlists. UC2 / UC3 widen these in R4.

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
        'product_catalogue.lookup'
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
        'product_catalogue.lookup'
    )
);

-- 4. Rename the Lighthouse-shaped subject columns and add a workflow_type
--    column so the projection tables carry the workflow's identity directly.

ALTER TABLE workflow_read_models RENAME COLUMN lead_id TO subject_id;
ALTER TABLE workflow_read_models RENAME COLUMN lead_summary TO subject_summary;
ALTER TABLE workflow_read_models ADD COLUMN IF NOT EXISTS subject_ref text;
ALTER TABLE workflow_read_models
    ADD COLUMN IF NOT EXISTS workflow_type text NOT NULL DEFAULT 'uc1_enquiry_qualification';
ALTER TABLE workflow_read_models ALTER COLUMN workflow_type DROP DEFAULT;
ALTER TABLE workflow_read_models DROP CONSTRAINT IF EXISTS workflow_read_models_step_check;
ALTER TABLE workflow_read_models ADD CONSTRAINT workflow_read_models_workflow_type_check CHECK (
    workflow_type IN ('uc1_enquiry_qualification')
);
ALTER TABLE workflow_read_models ADD CONSTRAINT workflow_read_models_subject_ref_shape CHECK (
    subject_ref IS NULL OR subject_ref ~ '^enq_[A-Za-z0-9_-]+$'
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

ALTER TABLE outbox_events RENAME COLUMN lead_id TO subject_id;
ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS subject_ref text;
ALTER TABLE outbox_events
    ADD COLUMN IF NOT EXISTS workflow_type text NOT NULL DEFAULT 'uc1_enquiry_qualification';
ALTER TABLE outbox_events ALTER COLUMN workflow_type DROP DEFAULT;
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
ALTER TABLE outbox_events ADD CONSTRAINT outbox_workflow_type_check CHECK (
    workflow_type IN ('uc1_enquiry_qualification')
);
ALTER TABLE outbox_events ADD CONSTRAINT outbox_subject_ref_shape CHECK (
    subject_ref IS NULL OR subject_ref ~ '^enq_[A-Za-z0-9_-]+$'
);

-- 5. Stamp comments to reflect the new role of these tables.

COMMENT ON TABLE workflow_read_models IS
    'Projection consumed by the BFF/UI for refresh-safe UC1 enquiry-qualification status.';
COMMENT ON TABLE workflow_history_events IS
    'Append-only UC1 enquiry-qualification workflow event history.';
COMMENT ON TABLE outbox_events IS
    'Transactional outbox aligned with workflow_event contract for Redpanda publication.';
