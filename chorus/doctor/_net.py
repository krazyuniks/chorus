"""TCP / HTTP / environment helpers shared by the live-probe modules."""

from __future__ import annotations

import os
import socket
import urllib.error
import urllib.request
from urllib.parse import urlsplit


def tcp_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        return False
    for family, socktype, proto, _canonname, sockaddr in addresses:
        try:
            with socket.socket(family, socktype, proto) as sock:
                sock.settimeout(timeout)
                sock.connect(sockaddr)
                return True
        except OSError:
            continue
    return False


def http_get(url: str, timeout: float = 1.5) -> tuple[int | None, str | None]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError, OSError, ValueError:
        return None, None


def env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def url_host_port(url: str, *, default_port: int | None = None) -> tuple[str, int] | None:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port or default_port
    except ValueError:
        return None
    if host is None or port is None:
        return None
    return host, port
