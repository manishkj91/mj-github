"""`pm-server` — boot the FastAPI service."""

from __future__ import annotations

import os

import uvicorn

from .app import create_app


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload_flag = os.getenv("RELOAD", "0") == "1"

    if reload_flag:
        # uvicorn needs an import string to reload.
        uvicorn.run("agents.server.factory:app", host=host, port=port, reload=True)
    else:
        uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
