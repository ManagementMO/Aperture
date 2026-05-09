"""Thin live Composio SDK adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aperture.config import ApertureConfig


def _to_plain(value: Any) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if all(hasattr(value, attr) for attr in ("id", "redirect_url", "status")):
        return {
            "id": getattr(value, "id"),
            "redirect_url": getattr(value, "redirect_url"),
            "status": getattr(value, "status"),
        }
    return value


@dataclass
class ComposioToolExecutor:
    """Execute tools through the Composio Python SDK when credentials exist."""

    config: ApertureConfig | None = None

    def __post_init__(self) -> None:
        self.config = self.config or ApertureConfig.from_env()
        if not self.config.composio_api_key:
            raise RuntimeError("COMPOSIO_API_KEY is required for live Composio execution")
        try:
            from composio import Composio
        except Exception as exc:
            raise RuntimeError("composio package is required for live Composio execution") from exc
        self._client = Composio(api_key=self.config.composio_api_key)

    def create_session(self, user_id: str | None = None, toolkits: list[str] | None = None) -> object:
        """Create a Composio Tool Router session for agent SDK integrations."""

        selected_user = user_id or self.config.composio_user_id  # type: ignore[union-attr]
        return self._client.create(user_id=selected_user, toolkits=toolkits)

    def session_tools(self, user_id: str | None = None, toolkits: list[str] | None = None) -> object:
        """Return Tool Router session tools for MCP/agent SDK use."""

        return _to_plain(self.create_session(user_id=user_id, toolkits=toolkits).tools())

    def session_search(self, query: str, user_id: str | None = None, toolkits: list[str] | None = None) -> object:
        """Search Composio tools through a Tool Router session."""

        session = self.create_session(user_id=user_id, toolkits=toolkits)
        return _to_plain(session.search(query=query))

    def session_execute(
        self,
        tool_slug: str,
        arguments: dict[str, Any],
        user_id: str | None = None,
        toolkits: list[str] | None = None,
        account: str | None = None,
    ) -> object:
        """Execute a tool through a Tool Router session."""

        session = self.create_session(user_id=user_id, toolkits=toolkits)
        return _to_plain(session.execute(tool_slug, arguments=arguments, account=account))

    def authorize_toolkit(
        self,
        toolkit: str,
        user_id: str | None = None,
        callback_url: str | None = None,
        alias: str | None = None,
    ) -> object:
        """Create a Tool Router connection request for a toolkit."""

        session = self.create_session(user_id=user_id, toolkits=[toolkit.lower()])
        return _to_plain(session.authorize(toolkit.lower(), callback_url=callback_url, alias=alias))

    def find_active_connected_account_id(self, toolkit: str, user_id: str | None = None) -> str | None:
        """Return the first active connected account id for a toolkit/user."""

        selected_user = user_id or self.config.composio_user_id  # type: ignore[union-attr]
        accounts = _to_plain(self._client.connected_accounts.list(user_ids=[selected_user]))
        if not isinstance(accounts, dict):
            return None
        for item in accounts.get("items", []):
            toolkit_data = item.get("toolkit") or {}
            toolkit_slug = toolkit_data.get("slug") or item.get("toolkit_slug") or item.get("toolkit")
            if str(toolkit_slug).lower() == toolkit.lower() and item.get("status") == "ACTIVE":
                account_id = item.get("id")
                if isinstance(account_id, str):
                    return account_id
        return None

    def execute(
        self,
        tool_slug: str,
        arguments: dict[str, Any],
        user_id: str | None = None,
        connected_account_id: str | None = None,
        version: str | None = None,
    ) -> object:
        """Execute one Composio tool with direct native SDK execution."""

        selected_user = user_id or self.config.composio_user_id  # type: ignore[union-attr]
        return _to_plain(
            self._client.tools.execute(
                slug=tool_slug,
                arguments=arguments,
                user_id=selected_user,
                connected_account_id=connected_account_id,
                version=version,
            )
        )

    def get_toolkit_version(self, toolkit_slug: str) -> str | None:
        """Return the current Composio toolkit version if exposed by the SDK."""

        toolkit = _to_plain(self._client.toolkits.get(slug=toolkit_slug.upper()))
        if isinstance(toolkit, dict):
            meta = toolkit.get("meta") or {}
            version = meta.get("version")
            if isinstance(version, str):
                return version
        return None

    def get_tools(self, *, toolkits: list[str] | None = None, slug: str | None = None) -> object:
        """Fetch Composio tool schemas for live schema optimization or smoke tests."""

        kwargs: dict[str, Any] = {
            "user_id": self.config.composio_user_id,  # type: ignore[union-attr]
            "toolkits": toolkits,
        }
        if slug:
            kwargs["tools"] = [slug]
        return _to_plain(self._client.tools.get(
            **kwargs,
        ))
