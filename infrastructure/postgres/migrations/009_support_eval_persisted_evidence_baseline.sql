-- Phase 2D support eval and persisted evidence baseline.
--
-- Support Agent Runtime decisions already route through the local support
-- contract and seeded support roles. This migration aligns the decision-trail
-- persistence constraint with those governed roles so support_triage evidence
-- can persist and be joined by safe tenant/correlation/workflow refs.
-- It does not add production providers, credential storage, Support BFF/UI
-- routes, ticket status execution, or connector writes beyond proposal mode.

ALTER TABLE decision_trail_entries DROP CONSTRAINT IF EXISTS decision_trail_agent_role_check;
ALTER TABLE decision_trail_entries ADD CONSTRAINT decision_trail_agent_role_check CHECK (
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
