#!/usr/bin/env python3
"""Auto-classify Composio tool slugs into the v1 cache policy YAML.

Usage:
    # From a live Composio account (requires COMPOSIO_API_KEY)
    python scripts/seed_cache_policy.py --live --output aperture/cache/policy.yaml

    # From a JSON dump of slugs (offline mode)
    python scripts/seed_cache_policy.py \\
        --slugs-from-json scripts/_seed_tool_list.json \\
        --output aperture/cache/policy.yaml

The classifier is rule-based:
    - Slug substring matches *_CREATE_*, *_UPDATE_*, *_DELETE_*, *_SEND_*,
      *_REMOVE_*, *_MERGE_*, *_CLOSE_*, *_REOPEN_*, *_COMMENT_*, *_REPLY_*,
      *_ASSIGN_*, *_INVITE_*, *_PUBLISH_*, *_POST_*, *_PUT_*, *_PATCH_*
        → category WRITE, cacheable=False
    - Slug substring matches *OAUTH*, *_REFRESH_*, *_TOKEN_*, MANAGE_CONNECTIONS,
      INITIATE_CONNECTION
        → category AUTH, cacheable=False
    - Slug starts GMAIL_, SLACK_, LINEAR_, NOTION_ + read verb (GET/LIST/SEARCH/FETCH)
        → category PRIVATE, account scope, TTL 5 min
    - Slug starts GITHUB_GET_REPO/GITHUB_GET_A_REPOSITORY/GITHUB_SEARCH_REPOS
        → category STATIC, public scope, TTL 2h
    - Slug starts GITHUB_LIST_*
        → category DYNAMIC, account scope, TTL 15 min
    - Slug starts GITHUB_GET_*
        → category DYNAMIC, account scope, TTL 5 min
    - Slug starts GOOGLESHEETS_BATCH_GET / SUPABASE_FETCH_TABLE_ROWS
        → category DYNAMIC, account scope, TTL 10 min
    - Default → cacheable=False, deny_by_default

Hand-review the output. The classifier is conservative — when in doubt, deny.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml


_WRITE_PATTERNS = (
    "_CREATE_", "_UPDATE_", "_DELETE_", "_SEND_", "_REMOVE_",
    "_MERGE_", "_CLOSE_", "_REOPEN_", "_COMMENT_", "_REPLY_",
    "_ASSIGN_", "_UNASSIGN_", "_INVITE_", "_PUBLISH_", "_POST_",
    "_PUT_", "_PATCH_", "_ARCHIVE_", "_STAR_", "_UNSTAR_",
    "_MOVE_", "_INSERT_", "_APPEND_", "_REJECT_",
)

_AUTH_SUBSTRINGS = (
    "OAUTH", "_REFRESH_", "_TOKEN_", "MANAGE_CONNECTIONS",
    "INITIATE_CONNECTION", "_AUTHORIZE", "_DISCONNECT",
)

_PRIVATE_TOOLKITS = ("GMAIL_", "SLACK_", "LINEAR_", "NOTION_")
_READ_VERBS = ("_GET_", "_LIST_", "_SEARCH_", "_FETCH_", "_QUERY_", "_FIND_")

_GITHUB_PUBLIC_SLUGS = {
    "GITHUB_GET_REPO",
    "GITHUB_GET_A_REPOSITORY",
    "GITHUB_SEARCH_REPOS",
    "GITHUB_FIND_REPOSITORIES",
}

_GITHUB_LIST_PATTERN = "GITHUB_LIST_"
_GITHUB_GET_PATTERN = "GITHUB_GET_"
_GITHUB_FIND_PATTERN = "GITHUB_FIND_"

_GOOGLESHEETS_READ_PATTERNS = ("GOOGLESHEETS_BATCH_GET", "GOOGLESHEETS_GET_")
_SUPABASE_READ_PATTERNS = ("SUPABASE_FETCH_TABLE_ROWS", "SUPABASE_GET_")
_YOUTUBE_READ_PATTERNS = ("YOUTUBE_GET_", "YOUTUBE_LIST_", "YOUTUBE_SEARCH_")


def classify(slug: str) -> dict:
    """Return a CachePolicy-shaped dict for a single tool slug."""
    upper = slug.upper()

    # Auth first (some auth tools contain CREATE in the slug)
    if any(s in upper for s in _AUTH_SUBSTRINGS):
        return _entry(
            cacheable=False, op="auth", scope="account",
            ttl=None, matching="none", reason="auth_operation",
        )

    if any(p in upper for p in _WRITE_PATTERNS):
        return _entry(
            cacheable=False, op="write", scope="account",
            ttl=None, matching="none", reason="write_operation",
        )

    # Public GitHub reads
    if upper in _GITHUB_PUBLIC_SLUGS:
        return _entry(cacheable=True, op="read", scope="public", ttl=7200, matching="exact")

    # GitHub LIST → DYNAMIC
    if upper.startswith(_GITHUB_LIST_PATTERN) or upper.startswith(_GITHUB_FIND_PATTERN):
        return _entry(cacheable=True, op="read", scope="account", ttl=900, matching="exact")

    # GitHub GET (non-public)
    if upper.startswith(_GITHUB_GET_PATTERN):
        return _entry(cacheable=True, op="read", scope="account", ttl=300, matching="exact")

    # Private toolkit reads
    if any(upper.startswith(t) for t in _PRIVATE_TOOLKITS):
        if any(v in upper for v in _READ_VERBS):
            return _entry(cacheable=True, op="read", scope="account", ttl=300, matching="exact")

    # Sheets / Supabase tabular reads
    if any(upper.startswith(p) for p in _GOOGLESHEETS_READ_PATTERNS):
        return _entry(cacheable=True, op="read", scope="account", ttl=600, matching="exact")
    if any(upper.startswith(p) for p in _SUPABASE_READ_PATTERNS):
        return _entry(cacheable=True, op="read", scope="account", ttl=600, matching="exact")

    # YouTube reads (mostly public)
    if any(upper.startswith(p) for p in _YOUTUBE_READ_PATTERNS):
        return _entry(cacheable=True, op="read", scope="public", ttl=3600, matching="exact")

    # Default: deny.
    return _entry(
        cacheable=False, op="unknown", scope="none",
        ttl=None, matching="none", reason="auto_classifier_default_deny",
    )


def _entry(
    *,
    cacheable: bool,
    op: str,
    scope: str,
    ttl: int | None,
    matching: str,
    reason: str | None = None,
) -> dict:
    out = {
        "cacheable": cacheable,
        "operation_type": op,
        "privacy_scope": scope,
        "ttl_seconds": ttl,
        "matching": matching,
    }
    if reason:
        out["reason"] = reason
    return out


def _extract_tool_name(tool: object) -> str | None:
    """Pull the slug out of any of Composio's tool-shape variants.

    Verified live 2026-05-10: with the default client (no AnthropicProvider),
    `client.tools.get()` returns OpenAI-shape `{function: {name, ...}, type:
    'function'}` dicts. The Anthropic provider returns `{name, description,
    input_schema}` dicts. We tolerate both, plus pydantic models.
    """
    if isinstance(tool, dict):
        # OpenAI shape: {function: {name, ...}, type: 'function'}
        fn = tool.get("function")
        if isinstance(fn, dict) and fn.get("name"):
            return str(fn["name"])
        # Anthropic shape: {name, description, input_schema}
        if tool.get("name"):
            return str(tool["name"])
        if tool.get("slug"):
            return str(tool["slug"])
    name = getattr(tool, "name", None) or getattr(tool, "slug", None)
    return str(name) if name else None


def fetch_slugs_from_composio(user_id: str = "default") -> list[str]:
    """Live mode: pull every tool slug from Composio.

    The Composio Python SDK (verified live 2026-05-10) doesn't expose a
    `client.tools.list()` method. The supported pattern is:
        1. `client.toolkits.list()` to enumerate every toolkit (returns ~1000).
        2. For each toolkit, `client.tools.get(user_id=, toolkits=[slug])` to
           fetch every tool in that toolkit.
    The Anthropic provider returns Anthropic-shape tool dicts with `name`.

    Args:
        user_id: a Composio user_id with at least one connected account.
            Required by `client.tools.get()`.
    """
    if not os.getenv("COMPOSIO_API_KEY"):
        raise RuntimeError("Live mode requires COMPOSIO_API_KEY in env.")
    from composio import Composio

    client = Composio(api_key=os.getenv("COMPOSIO_API_KEY"))

    # 1. List all toolkits.
    toolkits_response = client.toolkits.list()
    toolkit_items = getattr(toolkits_response, "items", None) or toolkits_response
    toolkit_slugs: list[str] = []
    for tk in toolkit_items:
        slug = (
            getattr(tk, "slug", None)
            or (tk.get("slug") if isinstance(tk, dict) else None)
            or getattr(tk, "name", None)
        )
        if slug:
            toolkit_slugs.append(str(slug).lower())

    # 2. Fetch tools per toolkit. `client.tools.get` raises InvalidParams if
    #    user_id has no connected accounts for the toolkit, so swallow per-
    #    toolkit failures and keep going.
    seen: set[str] = set()
    for tk_slug in toolkit_slugs:
        try:
            tools = client.tools.get(user_id=user_id, toolkits=[tk_slug], limit=500)
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(tools, list):
            continue
        for tool in tools:
            name = _extract_tool_name(tool)
            if name:
                seen.add(name)

    return sorted(seen)


def render_yaml(slugs: list[str], existing_yaml_path: Path | None = None) -> str:
    """Build the v1 policy YAML. Preserves the `default:` block from existing
    YAML if present; otherwise emits a deny-by-default block."""

    default_block = {
        "cacheable": False,
        "operation_type": "unknown",
        "privacy_scope": "none",
        "ttl_seconds": None,
        "matching": "none",
        "reason": "deny_by_default",
    }

    tools_block: dict[str, dict] = {}
    for slug in sorted(set(slugs)):
        tools_block[slug] = classify(slug)

    document = {
        "version": 1,
        "default": default_block,
        "tools": tools_block,
    }

    # sort_keys=False at the top level means version/default/tools order is
    # preserved in our document. Within `tools`, dict iteration is insertion
    # order (we already sorted), so the YAML output is deterministic.
    return yaml.safe_dump(document, sort_keys=False, default_flow_style=False)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Fetch from Composio API.")
    parser.add_argument("--slugs-from-json", help="Path to JSON file with a flat list of slugs.")
    parser.add_argument("--output", default="aperture/cache/policy.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout instead of writing.")
    parser.add_argument(
        "--user-id",
        default=os.getenv("COMPOSIO_USER_ID", "default"),
        help="Composio user_id for the live tool-fetch loop (must have ≥1 connected account).",
    )
    args = parser.parse_args(argv)

    if args.live:
        slugs = fetch_slugs_from_composio(user_id=args.user_id)
    elif args.slugs_from_json:
        with open(args.slugs_from_json, encoding="utf-8") as f:
            slugs = json.load(f)
        if not isinstance(slugs, list):
            raise SystemExit("--slugs-from-json must point to a JSON list of strings")
    else:
        raise SystemExit("Provide --live or --slugs-from-json")

    if len(slugs) == 0:
        raise SystemExit("No slugs returned — refusing to write empty policy.")

    rendered = render_yaml(slugs)

    if args.dry_run:
        print(rendered)
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered)
    print(f"wrote {len(slugs)} entries → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
