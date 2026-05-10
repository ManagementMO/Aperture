"""Per-MCP-connection session + turn tracking.

Plan-Agent 1 §5: TokenAttributionEvent.session_id and session_turn need a
source. None of the three options (per-connection, per-Composio-response,
synthesized) is perfect on its own. We use Option A (per-connection) as
the primary, optionally enriched with Composio's own session id when we
spot it in upstream responses.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass

from aperture.types import ExecutionContext


@dataclass
class _Sess:
    aperture_session_id: str
    user_id: str | None
    turn: int = 0
    composio_session_id: str | None = None


class SessionRegistry:
    """Thread-safe per-connection session state.

    The MCP `mcp.server.lowlevel.Server` exposes a stable per-connection
    `request_context.session_id` (protocol-level) — we use that as the
    `connection_id` key here, distinct from the app-level `session_id`
    we mint and emit in TokenAttributionEvents.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_connection: dict[str, _Sess] = {}

    def open(self, connection_id: str, user_id: str | None = None) -> str:
        """Mint or reuse a session id for this connection. Idempotent."""
        with self._lock:
            existing = self._by_connection.get(connection_id)
            if existing is not None:
                return existing.aperture_session_id
            sess = _Sess(
                aperture_session_id=str(uuid.uuid4()),
                user_id=user_id,
            )
            self._by_connection[connection_id] = sess
            return sess.aperture_session_id

    def close(self, connection_id: str) -> None:
        with self._lock:
            self._by_connection.pop(connection_id, None)

    def increment_turn(self, connection_id: str) -> int:
        """Bump the turn counter and return its new value (1-based after first call)."""
        with self._lock:
            sess = self._by_connection.get(connection_id)
            if sess is None:
                # Caller didn't open(); auto-open with no user_id.
                sess = _Sess(aperture_session_id=str(uuid.uuid4()), user_id=None)
                self._by_connection[connection_id] = sess
            sess.turn += 1
            return sess.turn

    def upgrade_with_composio_sid(self, connection_id: str, composio_session_id: str) -> None:
        """Option B enrichment: if the upstream response carries Composio's own
        session id, record it so future events can be joined to Composio's logs.
        Does NOT replace the aperture session id (that stays stable for telemetry)."""
        with self._lock:
            sess = self._by_connection.get(connection_id)
            if sess is not None and not sess.composio_session_id:
                sess.composio_session_id = composio_session_id

    def context_for(
        self,
        connection_id: str,
        *,
        toolkit_slug: str | None = None,
        tool_slug: str | None = None,
        meta_tool_slug: str | None = None,
        model: str | None = None,
        connected_account_id: str | None = None,
        project_id: str | None = None,
    ) -> ExecutionContext:
        """Build an ExecutionContext snapshot for a given inbound request."""
        with self._lock:
            sess = self._by_connection.get(connection_id)
            user_id = sess.user_id if sess is not None else None
            session_id = sess.aperture_session_id if sess is not None else None
        return ExecutionContext(
            project_id=project_id,
            user_id=user_id,
            session_id=session_id,
            connected_account_id=connected_account_id,
            toolkit_slug=toolkit_slug,
            tool_slug=tool_slug,
            meta_tool_slug=meta_tool_slug,
            model=model,
        )

    def turn_for(self, connection_id: str) -> int | None:
        with self._lock:
            sess = self._by_connection.get(connection_id)
            return sess.turn if sess is not None else None
