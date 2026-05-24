"""Shared eval result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EvalStatus = Literal["pass", "fail", "skip"]


@dataclass(frozen=True)
class EvalCheck:
    name: str
    status: EvalStatus
    detail: str


__all__ = [
    "EvalCheck",
    "EvalStatus",
]
