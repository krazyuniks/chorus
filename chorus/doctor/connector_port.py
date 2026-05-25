"""Live readiness probes for the connector port substrate.

Currently covers Mailpit (the local outbound-comms backing for the UC1
`sandbox-outbound-comms` adapter). Other connector backings (Radicale for
the calendar adapter, future UC2/UC3 sandboxes) probe alongside as they
join the live stack.
"""

from __future__ import annotations

import os

from chorus.doctor._net import env_int, http_get, tcp_reachable, url_host_port
from chorus.doctor._reporting import fail, ok, section


def check_mailpit() -> int:
    section("mailpit (UC1 sandbox-outbound-comms backing)")
    failures = 0
    smtp_port = env_int("MAILPIT_SMTP_PORT", 1025)
    port = env_int("MAILPIT_HTTP_PORT", 8025)
    if tcp_reachable("localhost", smtp_port):
        ok(f"mailpit SMTP reachable on localhost:{smtp_port}")
    else:
        fail(f"mailpit SMTP not reachable on localhost:{smtp_port} (run 'just up')")
        failures += 1
    if not tcp_reachable("localhost", port):
        fail(f"mailpit HTTP API not reachable on localhost:{port} (run 'just up')")
        return failures + 1
    status, _ = http_get(f"http://localhost:{port}/api/v1/info")
    if status == 200:
        ok(f"mailpit HTTP API responding on localhost:{port}")
        return failures
    fail(f"mailpit on localhost:{port} returned status {status}")
    return failures + 1


def check_radicale() -> int:
    section("radicale (CalDAV sandbox backing)")
    default_port = env_int("CALDAV_SANDBOX_PORT", 5232)
    base_url = os.environ.get("CHORUS_CALDAV_BASE_URL", f"http://localhost:{default_port}")
    host_port = url_host_port(base_url, default_port=default_port)
    if host_port is None:
        fail(f"CHORUS_CALDAV_BASE_URL is not a valid URL: {base_url}")
        return 1
    host, port = host_port
    if not tcp_reachable(host, port):
        fail(f"radicale not reachable at {host}:{port} from CHORUS_CALDAV_BASE_URL")
        return 1
    status, _ = http_get(f"{base_url.rstrip('/')}/")
    if status is not None and 200 <= status < 500:
        ok(f"radicale HTTP endpoint responding at {base_url.rstrip('/')}/")
        return 0
    fail(f"radicale at {base_url.rstrip('/')}/ returned status {status}")
    return 1
