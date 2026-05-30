# Intake Poller

Temporal worker and UC1 Mailpit intake service. The worker registers the
local use-case workflows that run on the shared spine. The Mailpit intake
path reads new messages from Mailpit's HTTP API, deduplicates by
`Message-ID`, parses the email payload against the UC1 email intake JSON
Schema, and starts a UC1 enquiry-qualification workflow per new enquiry.

Sending an email addressed to `enquiries@broker-firm.local` through Mailpit's
local SMTP port `1025` initiates a local workflow run.

Mailpit serves dual duty: SMTP receive + HTTP API for inbound (this service); SMTP capture for outbound (the email-send connector). One operational footprint covers both intake and outbound surfaces.

The UC1 intake path is implemented in
[`../../chorus/workflows/mailpit.py`](../../chorus/workflows/mailpit.py) and
exposed through the `just intake-once` CLI. Dedupe is by stable
Message-ID-derived Temporal workflow ID, so repeat polls do not start
duplicate runs. UC2 synthetic email-intake fixture starts are implemented in
[`../../chorus/workflows/uc2_synthetic_intake.py`](../../chorus/workflows/uc2_synthetic_intake.py)
for R5 P1 test evidence; the operator-facing UC2 command remains a later
runbook slice.
