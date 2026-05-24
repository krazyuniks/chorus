"""Live readiness probes for the observability port collectors and backends."""

from __future__ import annotations

from chorus.doctor._net import env_int, http_get, tcp_reachable
from chorus.doctor._reporting import fail, ok, section, skip


def check_otel() -> int:
    section("otel collector (observability port)")
    grpc_port = env_int("OTEL_GRPC_PORT", 4317)
    http_port = env_int("OTEL_HTTP_PORT", 4318)
    grpc_up = tcp_reachable("localhost", grpc_port)
    http_up = tcp_reachable("localhost", http_port)
    if not grpc_up and not http_up:
        skip(f"otel collector not reachable on localhost:{grpc_port}/{http_port} (run 'just up')")
        return 0
    if grpc_up:
        ok(f"otel collector gRPC reachable on localhost:{grpc_port}")
    else:
        fail(f"otel collector gRPC not reachable on localhost:{grpc_port}")
    if http_up:
        ok(f"otel collector HTTP reachable on localhost:{http_port}")
    else:
        fail(f"otel collector HTTP not reachable on localhost:{http_port}")
    return 0 if grpc_up and http_up else 1


def check_tempo() -> int:
    section("tempo (observability port - traces backend)")
    port = env_int("TEMPO_HTTP_PORT", 3200)
    if not tcp_reachable("localhost", port):
        skip(f"tempo not reachable on localhost:{port} (run 'just up')")
        return 0
    status, _ = http_get(f"http://localhost:{port}/ready")
    if status == 200:
        ok(f"tempo /ready responding on localhost:{port}")
        return 0
    fail(f"tempo on localhost:{port} /ready returned status {status}")
    return 1


def check_loki() -> int:
    section("loki (observability port - logs backend)")
    port = env_int("LOKI_HTTP_PORT", 3100)
    if not tcp_reachable("localhost", port):
        skip(f"loki not reachable on localhost:{port} (run 'just up')")
        return 0
    status, _ = http_get(f"http://localhost:{port}/ready")
    if status == 200:
        ok(f"loki /ready responding on localhost:{port}")
        return 0
    fail(f"loki on localhost:{port} /ready returned status {status}")
    return 1


def check_prometheus() -> int:
    section("prometheus (observability port - metrics backend)")
    port = env_int("PROMETHEUS_HTTP_PORT", 9090)
    if not tcp_reachable("localhost", port):
        skip(f"prometheus not reachable on localhost:{port} (run 'just up')")
        return 0
    status, _ = http_get(f"http://localhost:{port}/-/ready")
    if status == 200:
        ok(f"prometheus /-/ready responding on localhost:{port}")
        return 0
    fail(f"prometheus on localhost:{port} /-/ready returned status {status}")
    return 1
