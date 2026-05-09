"""Fetch tool schemas from fixtures or live Composio."""

from __future__ import annotations

import json
from pathlib import Path

from aperture.config import ApertureConfig
from aperture.integration.composio_adapter import ComposioToolExecutor


def _fixture_dir() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "schemas"


def fetch_fixture_schemas(path: Path | None = None) -> list[dict]:
    """Fetch fixture schemas from local JSON files."""

    selected = path or _fixture_dir()
    schemas: list[dict] = []
    for schema_file in sorted(selected.glob("*.json")):
        schemas.append(json.loads(schema_file.read_text(encoding="utf-8")))
    return schemas


def fetch_tool_schemas(live: bool = False) -> list[dict]:
    """Fetch current tool schemas from live Composio or local fixtures."""

    if live:
        config = ApertureConfig.from_env()
        executor = ComposioToolExecutor(config)
        tools = executor.get_tools(toolkits=["GITHUB", "GMAIL", "SLACK", "NOTION"])
        if isinstance(tools, list):
            return tools
        return list(tools or [])
    return fetch_fixture_schemas()

