"""Live readiness probes for the connector port substrate.

Currently covers Mailpit (the local outbound-comms backing for the UC1
`sandbox-outbound-comms` adapter). Other connector backings (Radicale for
the calendar adapter, future UC2/UC3 sandboxes) probe alongside as they
join the live stack.
"""

from __future__ import annotations

from chorus.doctor._net import env_int, http_get, tcp_reachable
from chorus.doctor._reporting import fail, ok, section, skip


def check_mailpit() -> int:
    section("mailpit (UC1 sandbox-outbound-comms backing)")
    port = env_int("MAILPIT_HTTP_PORT", 8025)
    if not tcp_reachable("localhost", port):
        skip(f"mailpit not reachable on localhost:{port} (run 'just up')")
        return 0
    status, _ = http_get(f"http://localhost:{port}/api/v1/info")
    if status == 200:
        ok(f"mailpit HTTP API responding on localhost:{port}")
        return 0
    fail(f"mailpit on localhost:{port} returned status {status}")
    return 1
