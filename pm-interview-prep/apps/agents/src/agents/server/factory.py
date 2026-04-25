"""Module-level ASGI app for ``uvicorn --reload``."""

from .app import create_app

app = create_app()
