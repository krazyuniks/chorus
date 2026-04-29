# Intake Poller

Temporal cron-style activity that reads new messages from Mailpit's HTTP API, deduplicates by `Message-ID`, parses the email payload against the lead-intake JSON Schema, and starts a Lighthouse workflow per new lead.

This is the **Phase 1A demo trigger** — sending a real email to `leads@chorus.local:1025` initiates a real workflow run. See [ADR 0008 — Email intake via Mailpit](../../adrs/0008-email-intake-via-mailpit.md).

Mailpit serves dual duty: SMTP receive + HTTP API for inbound (this service); SMTP capture for outbound (the email-send connector). One operational footprint covers both intake and outbound surfaces.

Phase 1A workstream **B** (Temporal workflows + activities — sub-component).
