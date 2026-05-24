# Intake Poller

Temporal cron-style activity that reads new messages from Mailpit's HTTP API,
deduplicates by `Message-ID`, parses the email payload against the UC1 email
intake JSON Schema, and starts a UC1 enquiry-qualification workflow per new
enquiry.

Sending an email addressed to `enquiries@broker-firm.local` through Mailpit's
local SMTP port `1025` initiates a local workflow run.

Mailpit serves dual duty: SMTP receive + HTTP API for inbound (this service); SMTP capture for outbound (the email-send connector). One operational footprint covers both intake and outbound surfaces.

The intake path is implemented in [`../../chorus/workflows/mailpit.py`](../../chorus/workflows/mailpit.py)
and exposed through the `just intake-once` CLI. Dedupe is by stable
Message-ID-derived Temporal workflow ID, so repeat polls do not start duplicate
runs.
