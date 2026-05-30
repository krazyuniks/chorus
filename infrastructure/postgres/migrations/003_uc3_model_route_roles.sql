-- Extend governed runtime role constraints for UC3 agent-runtime routes.
--
-- The R5 P2 UC3 route-policy slice adds workflow-only UC3 model agents plus
-- recorded-replay model routes for the five UC3 agent task kinds. Keep these
-- constraints forward-only so applied baseline checksums remain stable.

ALTER TABLE agent_registry DROP CONSTRAINT IF EXISTS agent_registry_role_check;
ALTER TABLE agent_registry ADD CONSTRAINT agent_registry_role_check CHECK (
    role IN (
        'advice_scope_classifier',
        'aml_assessor',
        'capacity_assessor',
        'classifier',
        'conflict_analyst',
        'consumer_duty_support_assessor',
        'context_gatherer',
        'engagement_decider',
        'fact_find_summariser',
        'legal_matter_classifier',
        'legal_party_extractor',
        'qualifier',
        'request_drafter',
        'research_analyst',
        'risk_analyst',
        'risk_profile_assessor',
        'suitability_decider',
        'validator'
    )
);

ALTER TABLE model_routing_policies DROP CONSTRAINT IF EXISTS model_routing_agent_role_check;
ALTER TABLE model_routing_policies ADD CONSTRAINT model_routing_agent_role_check CHECK (
    agent_role IN (
        'advice_scope_classifier',
        'classifier',
        'conflict_analyst',
        'consumer_duty_support_assessor',
        'context_gatherer',
        'engagement_decider',
        'fact_find_summariser',
        'legal_matter_classifier',
        'legal_party_extractor',
        'qualifier',
        'request_drafter',
        'risk_profile_assessor',
        'suitability_decider',
        'validator'
    )
);

ALTER TABLE decision_trail_entries DROP CONSTRAINT IF EXISTS decision_trail_agent_role_check;
ALTER TABLE decision_trail_entries ADD CONSTRAINT decision_trail_agent_role_check CHECK (
    agent_role IN (
        'advice_scope_classifier',
        'classifier',
        'conflict_analyst',
        'consumer_duty_support_assessor',
        'context_gatherer',
        'engagement_decider',
        'fact_find_summariser',
        'legal_matter_classifier',
        'legal_party_extractor',
        'qualifier',
        'request_drafter',
        'risk_profile_assessor',
        'suitability_decider',
        'validator'
    )
);

ALTER TABLE model_route_versions DROP CONSTRAINT IF EXISTS model_route_versions_agent_role_check;
ALTER TABLE model_route_versions ADD CONSTRAINT model_route_versions_agent_role_check CHECK (
    agent_role IN (
        'advice_scope_classifier',
        'classifier',
        'conflict_analyst',
        'consumer_duty_support_assessor',
        'context_gatherer',
        'engagement_decider',
        'fact_find_summariser',
        'legal_matter_classifier',
        'legal_party_extractor',
        'qualifier',
        'request_drafter',
        'risk_profile_assessor',
        'suitability_decider',
        'validator'
    )
);

ALTER TABLE replay_run_records DROP CONSTRAINT IF EXISTS replay_run_agent_role_check;
ALTER TABLE replay_run_records ADD CONSTRAINT replay_run_agent_role_check CHECK (
    agent_role IN (
        'advice_scope_classifier',
        'classifier',
        'conflict_analyst',
        'consumer_duty_support_assessor',
        'context_gatherer',
        'engagement_decider',
        'fact_find_summariser',
        'legal_matter_classifier',
        'legal_party_extractor',
        'qualifier',
        'request_drafter',
        'risk_profile_assessor',
        'suitability_decider',
        'validator'
    )
);
