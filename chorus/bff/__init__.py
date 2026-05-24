"""FastAPI backend-for-frontend for the Chorus inspection UI."""

from __future__ import annotations

from chorus.bff.app import BffSettings, create_app

__all__ = ["BffSettings", "create_app"]
