-- Postgres-backed local CRM connector state for Phase 1A Tool Gateway evidence.

CREATE TABLE IF NOT EXISTS local_crm_leads (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    crm_lead_id uuid NOT NULL,
    correlation_id text NOT NULL,
    company_name text NOT NULL,
    contact_email text NOT NULL,
    lead_summary text NOT NULL,
    status text NOT NULL DEFAULT 'proposed',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, crm_lead_id),
    CONSTRAINT local_crm_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT local_crm_contact_email_shape CHECK (contact_email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
    CONSTRAINT local_crm_status_check CHECK (status IN ('proposed', 'active', 'closed')),
    UNIQUE (tenant_id, correlation_id, contact_email)
);

CREATE INDEX IF NOT EXISTS local_crm_company_lookup_idx
    ON local_crm_leads (tenant_id, lower(company_name), created_at DESC);

ALTER TABLE local_crm_leads ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS local_crm_tenant_isolation ON local_crm_leads;
CREATE POLICY local_crm_tenant_isolation ON local_crm_leads
    FOR ALL TO chorus_app
    USING (tenant_id = chorus_current_tenant_id())
    WITH CHECK (tenant_id = chorus_current_tenant_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON local_crm_leads TO chorus_app;

COMMENT ON TABLE local_crm_leads IS 'Postgres-backed local CRM state invoked only through the Tool Gateway.';
