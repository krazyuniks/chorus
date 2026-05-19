-- Phase 2D support workflow runtime baseline.
--
-- This migration keeps the existing generic workflow event/read-model tables
-- but allows the support_triage workflow's bounded step and role categories.
-- It does not add support BFF routes, UI routes, eval persistence, production
-- ticketing providers, credential storage, or ticket write execution.

ALTER TABLE model_routing_policies DROP CONSTRAINT IF EXISTS model_routing_agent_role_check;
ALTER TABLE model_routing_policies ADD CONSTRAINT model_routing_agent_role_check CHECK (
    agent_role IN (
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

ALTER TABLE workflow_read_models DROP CONSTRAINT IF EXISTS workflow_read_models_step_check;
ALTER TABLE workflow_read_models ADD CONSTRAINT workflow_read_models_step_check CHECK (
    current_step IS NULL
    OR current_step IN (
        'intake',
        'research_qualification',
        'draft',
        'validation',
        'propose_send',
        'complete',
        'escalate',
        'support_intake',
        'support_classification',
        'support_context_lookup',
        'support_resolution_plan',
        'support_draft',
        'support_validation',
        'support_propose',
        'support_complete',
        'support_escalate'
    )
);

ALTER TABLE workflow_history_events DROP CONSTRAINT IF EXISTS workflow_history_step_check;
ALTER TABLE workflow_history_events ADD CONSTRAINT workflow_history_step_check CHECK (
    step IS NULL
    OR step IN (
        'intake',
        'research_qualification',
        'draft',
        'validation',
        'propose_send',
        'complete',
        'escalate',
        'support_intake',
        'support_classification',
        'support_context_lookup',
        'support_resolution_plan',
        'support_draft',
        'support_validation',
        'support_propose',
        'support_complete',
        'support_escalate'
    )
);

ALTER TABLE outbox_events DROP CONSTRAINT IF EXISTS outbox_step_check;
ALTER TABLE outbox_events ADD CONSTRAINT outbox_step_check CHECK (
    step IS NULL
    OR step IN (
        'intake',
        'research_qualification',
        'draft',
        'validation',
        'propose_send',
        'complete',
        'escalate',
        'support_intake',
        'support_classification',
        'support_context_lookup',
        'support_resolution_plan',
        'support_draft',
        'support_validation',
        'support_propose',
        'support_complete',
        'support_escalate'
    )
);
