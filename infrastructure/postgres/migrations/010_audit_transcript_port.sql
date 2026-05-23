-- R3 checkpoint C: audit transcript port (ADR 0019).
--
-- The single audit store splits into two ports. The structured decision-trail
-- port stays on `decision_trail_entries`; this migration adds the
-- full-fidelity transcript port. Both ports record every governed agent
-- invocation, anchored on the same invocation_id.
--
-- The transcript carries enough route, model, parameter, and message-history
-- metadata to make the invocation replayable against an alternate provider
-- through the LLM provider port. The eval reshape (checkpoint G) introduces
-- the replay subcommand on top of this surface.

CREATE TABLE IF NOT EXISTS agent_invocation_transcripts (
    tenant_id text NOT NULL REFERENCES tenants (tenant_id) ON DELETE RESTRICT,
    transcript_id uuid NOT NULL,
    invocation_id uuid NOT NULL,
    correlation_id text NOT NULL,
    workflow_id text NOT NULL,
    route_id text NOT NULL,
    provider_id text NOT NULL,
    model_id text NOT NULL,
    adapter_version text NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
    messages jsonb NOT NULL,
    tool_calls jsonb NOT NULL DEFAULT '[]'::jsonb,
    response_body jsonb,
    token_usage jsonb NOT NULL DEFAULT '{}'::jsonb,
    provider_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    raw_record jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, transcript_id),
    CONSTRAINT transcript_correlation_shape CHECK (correlation_id ~ '^cor_[A-Za-z0-9_-]+$'),
    CONSTRAINT transcript_messages_is_array CHECK (jsonb_typeof(messages) = 'array'),
    CONSTRAINT transcript_tool_calls_is_array CHECK (jsonb_typeof(tool_calls) = 'array')
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_invocation_transcripts_invocation_idx
    ON agent_invocation_transcripts (tenant_id, invocation_id);

CREATE INDEX IF NOT EXISTS agent_invocation_transcripts_workflow_idx
    ON agent_invocation_transcripts (tenant_id, workflow_id, started_at);

CREATE INDEX IF NOT EXISTS agent_invocation_transcripts_route_idx
    ON agent_invocation_transcripts (tenant_id, route_id, completed_at);

ALTER TABLE agent_invocation_transcripts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_invocation_transcripts_tenant_isolation
    ON agent_invocation_transcripts;
CREATE POLICY agent_invocation_transcripts_tenant_isolation
    ON agent_invocation_transcripts
    USING (tenant_id = current_setting('app.tenant_id', true));

GRANT SELECT, INSERT ON agent_invocation_transcripts TO chorus_app;
