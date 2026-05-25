"""Shared reporting helpers used by every doctor probe module."""

from __future__ import annotations


def ok(message: str) -> None:
    print(f"ok    - {message}")


def fail(message: str) -> None:
    print(f"fail  - {message}")


def info(message: str) -> None:
    print(f"info  - {message}")


def skip(message: str) -> None:
    print(f"skip  - {message}")


def section(title: str) -> None:
    print(f"\n# {title}")
