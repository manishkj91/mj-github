"""HTTP server for the agents service."""

from .app import create_app

__all__ = ["create_app"]
