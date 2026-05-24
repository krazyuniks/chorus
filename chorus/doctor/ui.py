"""Live readiness probes for the projection-port-consuming UI surfaces.

BFF and the Vite dev server are not ports; they sit on top of the projection
port read surface. They probe here so the doctor surface reports them
alongside the live substrate they depend on.
"""

from __future__ import annotations

from chorus.doctor._net import env_int, http_get, tcp_reachable
from chorus.doctor._reporting import fail, ok, section, skip


def check_bff() -> int:
    section("bff (projection-port consumer)")
    port = env_int("BFF_PORT", 8000)
    if not tcp_reachable("localhost", port):
        skip(f"bff not reachable on localhost:{port} (workstream E pending)")
        return 0
    status, _ = http_get(f"http://localhost:{port}/health")
    if status == 200:
        ok(f"bff /health responding on localhost:{port}")
        return 0
    fail(f"bff on localhost:{port} /health returned status {status}")
    return 1


def check_frontend_dev() -> int:
    section("frontend dev server (projection-port consumer)")
    port = env_int("FRONTEND_PORT", 5173)
    if not tcp_reachable("localhost", port):
        skip(f"frontend dev server not reachable on localhost:{port} (run 'npm run dev')")
        return 0
    ok(f"frontend dev server reachable on localhost:{port}")
    return 0
