-- Add a terminal DLQ state for outbox rows that are retained as failure
-- evidence and must not be reclaimed by the relay retry path.

ALTER TABLE outbox_events
    DROP CONSTRAINT IF EXISTS outbox_status_check;

ALTER TABLE outbox_events
    ADD CONSTRAINT outbox_status_check
    CHECK (status IN ('pending', 'publishing', 'sent', 'failed', 'dlq'));

CREATE INDEX IF NOT EXISTS outbox_dlq_idx
    ON outbox_events (tenant_id, workflow_id, updated_at)
    WHERE status = 'dlq';
