-- Immutable local UC1 policy snapshot rows.
--
-- The deterministic recorded-replay qualifier emits
-- policy_snapshot:uc1:default:v1. This seed materialises the tenant-scoped
-- local policy bundle behind that ref using safe refs only: agent/prompt
-- refs, model route refs, Tool Gateway grant refs, connector policy refs,
-- target-market refs, and bounded conduct-hook refs.

WITH snapshots AS (
    SELECT
        'tenant_demo'::text AS tenant_id,
        'policy_snapshot:uc1:default:v1'::text AS policy_snapshot_ref,
        'uc1_enquiry_qualification'::text AS workflow_type,
        'v1'::text AS snapshot_version,
        '2026-05-24T00:00:00Z'::timestamptz AS effective_from,
        '{
          "schema_version": "1.0.0",
          "policy_snapshot_ref": "policy_snapshot:uc1:default:v1",
          "workflow_type": "uc1_enquiry_qualification",
          "scope": "local_uc1_enquiry_qualification",
          "agents": [
            {
              "agent_id": "uc1.classifier",
              "role": "classifier",
              "version": "v1",
              "prompt_reference": "prompts/uc1/classifier/v1.md",
              "prompt_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            },
            {
              "agent_id": "uc1.context_gatherer",
              "role": "context_gatherer",
              "version": "v1",
              "prompt_reference": "prompts/uc1/context-gatherer/v1.md",
              "prompt_hash": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            },
            {
              "agent_id": "uc1.qualifier",
              "role": "qualifier",
              "version": "v1",
              "prompt_reference": "prompts/uc1/qualifier/v1.md",
              "prompt_hash": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
            },
            {
              "agent_id": "uc1.request_drafter",
              "role": "request_drafter",
              "version": "v1",
              "prompt_reference": "prompts/uc1/request-drafter/v1.md",
              "prompt_hash": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
            },
            {
              "agent_id": "uc1.validator",
              "role": "validator",
              "version": "v1",
              "prompt_reference": "prompts/uc1/validator/v1.md",
              "prompt_hash": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
            }
          ],
          "model_routes": [
            {
              "route_id": "11000000-0000-4000-8000-000000000001",
              "route_version": 1,
              "agent_role": "classifier",
              "task_kind": "enquiry_classification",
              "provider_catalogue_id": "provider-catalogue.local.seed",
              "provider_id": "local",
              "model_id": "uc1-happy-path-v1",
              "budget_cap_usd": "0.0100"
            },
            {
              "route_id": "11000000-0000-4000-8000-000000000002",
              "route_version": 1,
              "agent_role": "context_gatherer",
              "task_kind": "context_gathering",
              "provider_catalogue_id": "provider-catalogue.local.seed",
              "provider_id": "local",
              "model_id": "uc1-happy-path-v1",
              "budget_cap_usd": "0.0100"
            },
            {
              "route_id": "11000000-0000-4000-8000-000000000003",
              "route_version": 1,
              "agent_role": "qualifier",
              "task_kind": "enquiry_qualification",
              "provider_catalogue_id": "provider-catalogue.local.seed",
              "provider_id": "local",
              "model_id": "uc1-happy-path-v1",
              "budget_cap_usd": "0.0100"
            },
            {
              "route_id": "11000000-0000-4000-8000-000000000004",
              "route_version": 1,
              "agent_role": "request_drafter",
              "task_kind": "missing_data_request_draft",
              "provider_catalogue_id": "provider-catalogue.local.seed",
              "provider_id": "local",
              "model_id": "uc1-happy-path-v1",
              "budget_cap_usd": "0.0100"
            },
            {
              "route_id": "11000000-0000-4000-8000-000000000005",
              "route_version": 1,
              "agent_role": "validator",
              "task_kind": "missing_data_request_validation",
              "provider_catalogue_id": "provider-catalogue.local.seed",
              "provider_id": "local",
              "model_id": "uc1-happy-path-v1",
              "budget_cap_usd": "0.0100"
            }
          ],
          "tool_grants": [
            {
              "grant_ref": "tool_grant:12000000-0000-4000-8000-000000000001",
              "agent_id": "uc1.context_gatherer",
              "tool_name": "customer_profile.lookup",
              "mode": "read",
              "approval_required": false
            },
            {
              "grant_ref": "tool_grant:12000000-0000-4000-8000-000000000002",
              "agent_id": "uc1.context_gatherer",
              "tool_name": "product_catalogue.lookup",
              "mode": "read",
              "approval_required": false
            },
            {
              "grant_ref": "tool_grant:12000000-0000-4000-8000-000000000003",
              "agent_id": "uc1.qualifier",
              "tool_name": "crm.route_to_quoting_queue",
              "mode": "write",
              "approval_required": false
            },
            {
              "grant_ref": "tool_grant:12000000-0000-4000-8000-000000000004",
              "agent_id": "uc1.qualifier",
              "tool_name": "referral_inbox.route",
              "mode": "write",
              "approval_required": false
            },
            {
              "grant_ref": "tool_grant:12000000-0000-4000-8000-000000000005",
              "agent_id": "uc1.qualifier",
              "tool_name": "decline_ledger.route",
              "mode": "write",
              "approval_required": false
            },
            {
              "grant_ref": "tool_grant:12000000-0000-4000-8000-000000000006",
              "agent_id": "uc1.request_drafter",
              "tool_name": "outbound_comms.message",
              "mode": "propose",
              "approval_required": false,
              "redacted_field_refs": ["body_text"]
            },
            {
              "grant_ref": "tool_grant:12000000-0000-4000-8000-000000000007",
              "agent_id": "uc1.request_drafter",
              "tool_name": "outbound_comms.message",
              "mode": "write",
              "approval_required": true,
              "redacted_field_refs": ["body_text"]
            }
          ],
          "connector_policy_refs": {
            "customer_profile_lookup_policy_ref": "policy_uc1_customer_profile_lookup_v1",
            "product_catalogue_lookup_policy_ref": "policy_uc1_product_catalogue_lookup_v1",
            "routing_policy_ref": "policy_uc1_routing_v1",
            "outbound_comms_policy_ref": "policy_uc1_outbound_comms_local_v1"
          },
          "approval_policy_refs": {
            "outbound_comms_write": "approval_policy.outbound_comms_message_write.local.v1"
          },
          "target_market_rule_refs": [
            "local_product_catalogue_entries:tenant_demo:active",
            "fva_motor_private_2026_q1",
            "fva_home_buildings_2026_q1"
          ],
          "conduct_hook_refs": [
            {
              "hook": "best_interests_check",
              "regulatory_ref": "ICOBS 2.5.-1R"
            },
            {
              "hook": "demands_and_needs_statement",
              "regulatory_ref": "ICOBS 5"
            },
            {
              "hook": "target_market_check",
              "regulatory_ref": "PROD 4"
            },
            {
              "hook": "foreseeable_harm_check",
              "regulatory_ref": "Consumer Duty PRIN 12"
            }
          ]
        }'::jsonb AS policy_bundle,
        '{
          "agent_registry_refs": [
            "agent_registry:tenant_demo:uc1.classifier:v1",
            "agent_registry:tenant_demo:uc1.context_gatherer:v1",
            "agent_registry:tenant_demo:uc1.qualifier:v1",
            "agent_registry:tenant_demo:uc1.request_drafter:v1",
            "agent_registry:tenant_demo:uc1.validator:v1"
          ],
          "model_routing_policy_refs": [
            "model_routing_policies:11000000-0000-4000-8000-000000000001",
            "model_routing_policies:11000000-0000-4000-8000-000000000002",
            "model_routing_policies:11000000-0000-4000-8000-000000000003",
            "model_routing_policies:11000000-0000-4000-8000-000000000004",
            "model_routing_policies:11000000-0000-4000-8000-000000000005"
          ],
          "model_route_version_refs": [
            "model_route_versions:11000000-0000-4000-8000-000000000001:1",
            "model_route_versions:11000000-0000-4000-8000-000000000002:1",
            "model_route_versions:11000000-0000-4000-8000-000000000003:1",
            "model_route_versions:11000000-0000-4000-8000-000000000004:1",
            "model_route_versions:11000000-0000-4000-8000-000000000005:1"
          ],
          "tool_grant_refs": [
            "tool_grant:12000000-0000-4000-8000-000000000001",
            "tool_grant:12000000-0000-4000-8000-000000000002",
            "tool_grant:12000000-0000-4000-8000-000000000003",
            "tool_grant:12000000-0000-4000-8000-000000000004",
            "tool_grant:12000000-0000-4000-8000-000000000005",
            "tool_grant:12000000-0000-4000-8000-000000000006",
            "tool_grant:12000000-0000-4000-8000-000000000007"
          ],
          "connector_policy_refs": [
            "policy_uc1_customer_profile_lookup_v1",
            "policy_uc1_product_catalogue_lookup_v1",
            "policy_uc1_routing_v1",
            "policy_uc1_outbound_comms_local_v1"
          ]
        }'::jsonb AS source_refs,
        '{"seed": true, "source": "uc1_policy_snapshots"}'::jsonb AS metadata
)
INSERT INTO policy_snapshots (
    tenant_id,
    policy_snapshot_ref,
    workflow_type,
    snapshot_version,
    lifecycle_state,
    effective_from,
    policy_bundle,
    source_refs,
    content_hash,
    metadata
)
SELECT
    tenant_id,
    policy_snapshot_ref,
    workflow_type,
    snapshot_version,
    'active',
    effective_from,
    policy_bundle,
    source_refs,
    'sha256:' || encode(digest(policy_bundle::text, 'sha256'), 'hex'),
    metadata
FROM snapshots
ON CONFLICT (tenant_id, policy_snapshot_ref) DO NOTHING;
