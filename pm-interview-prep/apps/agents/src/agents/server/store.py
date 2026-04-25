"""In-memory session store.

Backed by a process-local dict for v1. Replace with Postgres for M4.
"""

from __future__ import annotations

import threading
from collections import OrderedDict

from ..contracts import SessionState


class SessionStore:
    def __init__(self, max_sessions: int = 200) -> None:
        self._sessions: OrderedDict[str, SessionState] = OrderedDict()
        self._lock = threading.Lock()
        self._max = max_sessions

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            state = self._sessions.get(session_id)
            if state is not None:
                self._sessions.move_to_end(session_id)
            return state

    def put(self, state: SessionState) -> None:
        with self._lock:
            self._sessions[state.session_id] = state
            self._sessions.move_to_end(state.session_id)
            while len(self._sessions) > self._max:
                self._sessions.popitem(last=False)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
