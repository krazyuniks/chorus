# Intake Poller

Temporal cron-style activity that reads new messages from Mailpit's HTTP API, deduplicates by `Message-ID`, parses the email payload against the lead-intake JSON Schema, and starts a Lighthouse workflow per new lead.

This is the **Phase 1A demo trigger** — sending a real email addressed to `leads@chorus.local` through Mailpit's local SMTP port `1025` initiates a real workflow run. See [ADR 0008 — Email intake via Mailpit](../../adrs/0008-email-intake-via-mailpit.md).

Mailpit serves dual duty: SMTP receive + HTTP API for inbound (this service); SMTP capture for outbound (the email-send connector). One operational footprint covers both intake and outbound surfaces.

Phase 1A workstream **B** is implemented in [`../../chorus/workflows/mailpit.py`](../../chorus/workflows/mailpit.py) and exposed through the `lighthouse.poll_mailpit` Temporal activity plus the `just intake-once` CLI. Dedupe is by stable Message-ID-derived Temporal workflow ID, so repeat polls do not start duplicate Lighthouse runs.
