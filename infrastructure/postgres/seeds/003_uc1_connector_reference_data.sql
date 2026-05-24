-- Deterministic synthetic UC1 read-connector records.
--
-- These rows back the sandbox-customer-profile and sandbox-product-catalogue
-- adapters. They intentionally contain no real customer personal data.

INSERT INTO local_customer_profiles (
    tenant_id,
    customer_ref,
    display_name_category,
    vulnerability_markers,
    consent_state_category,
    profile_status,
    metadata
)
VALUES
    (
        'tenant_demo',
        'cust_demo_001',
        'individual_personal_lines',
        ARRAY[]::text[],
        'marketing_opt_in',
        'active',
        '{"seed": true, "source": "uc1_connector_reference_data"}'::jsonb
    ),
    (
        'tenant_demo',
        'cust_demo_002',
        'individual_personal_lines',
        ARRAY['bereavement_declared']::text[],
        'marketing_opt_out',
        'active',
        '{"seed": true, "source": "uc1_connector_reference_data"}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'cust_demo_001',
        'individual_personal_lines',
        ARRAY[]::text[],
        'marketing_opt_in',
        'active',
        '{"seed": true, "source": "uc1_connector_reference_data"}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'cust_demo_002',
        'individual_personal_lines',
        ARRAY['bereavement_declared']::text[],
        'marketing_opt_out',
        'active',
        '{"seed": true, "source": "uc1_connector_reference_data"}'::jsonb
    )
ON CONFLICT (tenant_id, customer_ref) DO UPDATE
SET
    display_name_category = EXCLUDED.display_name_category,
    vulnerability_markers = EXCLUDED.vulnerability_markers,
    consent_state_category = EXCLUDED.consent_state_category,
    profile_status = EXCLUDED.profile_status,
    metadata = EXCLUDED.metadata,
    updated_at = now();

INSERT INTO local_product_catalogue_entries (
    tenant_id,
    product_family_category,
    target_market_summary_category,
    min_age_category,
    construction_categories,
    excluded_postcode_categories,
    fair_value_assessment_ref,
    catalogue_status,
    metadata
)
VALUES
    (
        'tenant_demo',
        'motor_private_car',
        'uk_resident_private_motor_standard',
        'age_25_plus',
        ARRAY[]::text[],
        ARRAY['high_theft_metropolitan']::text[],
        'fva_motor_private_2026_q1',
        'active',
        '{"seed": true, "source": "uc1_connector_reference_data"}'::jsonb
    ),
    (
        'tenant_demo',
        'home_buildings',
        'uk_resident_homeowner_buildings',
        NULL,
        ARRAY['standard_brick', 'standard_stone']::text[],
        ARRAY['flood_zone_3']::text[],
        'fva_home_buildings_2026_q1',
        'active',
        '{"seed": true, "source": "uc1_connector_reference_data"}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'motor_private_car',
        'uk_resident_private_motor_standard',
        'age_25_plus',
        ARRAY[]::text[],
        ARRAY['high_theft_metropolitan']::text[],
        'fva_motor_private_2026_q1',
        'active',
        '{"seed": true, "source": "uc1_connector_reference_data"}'::jsonb
    ),
    (
        'tenant_demo_alt',
        'home_buildings',
        'uk_resident_homeowner_buildings',
        NULL,
        ARRAY['standard_brick', 'standard_stone']::text[],
        ARRAY['flood_zone_3']::text[],
        'fva_home_buildings_2026_q1',
        'active',
        '{"seed": true, "source": "uc1_connector_reference_data"}'::jsonb
    )
ON CONFLICT (tenant_id, product_family_category) DO UPDATE
SET
    target_market_summary_category = EXCLUDED.target_market_summary_category,
    min_age_category = EXCLUDED.min_age_category,
    construction_categories = EXCLUDED.construction_categories,
    excluded_postcode_categories = EXCLUDED.excluded_postcode_categories,
    fair_value_assessment_ref = EXCLUDED.fair_value_assessment_ref,
    catalogue_status = EXCLUDED.catalogue_status,
    metadata = EXCLUDED.metadata,
    updated_at = now();
