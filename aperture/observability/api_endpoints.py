"""v3.1-shape HTTP endpoints for token attribution and cache savings.

Mirrors Composio's `/api/v3.1/project/usage/{entity_type}` shape (handoff §17.2)
on a separate host. Aperture cannot extend Composio's actual API surface
(no internal access), so developers query Aperture for token cost and
Composio for tool counts, joining client-side by `session_id`.

Endpoints:
    POST /api/v3.1/project/usage/input_tokens_contributed
    POST /api/v3.1/project/usage/cache_tokens_saved
    GET  /api/v3.1/health

Backed by `event_log_sqlite.SQLiteEventLog`. If no SQLite log is configured,
endpoints return `{"data": [], ...}` rather than failing — the proxy might
not have written any events yet.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from pydantic import BaseModel, Field

from aperture import __version__
from aperture.proxy.overlay import default_overlay_path
from aperture.observability.aggregations import (
    aggregate_cache_events_v1,
    aggregate_token_events_v1,
)
from aperture.observability.event_log_sqlite import SQLiteEventLog, get_default_log

router = APIRouter(prefix="/api/v3.1", tags=["v3.1"])


class TokenUsageRequest(BaseModel):
    """POST /api/v3.1/project/usage/input_tokens_contributed body."""

    group_by: str = Field(..., description="meta_tool_slug | toolkit_slug | session_turn | user_id | tool_slug | model | date")
    order_by: str = Field("total_quantity")
    order_direction: str = Field("desc")
    dt_gt: str | None = None
    dt_lt: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    page: int = 1
    page_size: int = 100


class CacheSavingsRequest(BaseModel):
    """POST /api/v3.1/project/usage/cache_tokens_saved body."""

    group_by: str = Field(..., description="tool_slug | toolkit_slug | user_id | cache_status | date")
    dt_gt: str | None = None
    dt_lt: str | None = None
    user_id: str | None = None
    page: int = 1
    page_size: int = 100


def _log_or_404() -> SQLiteEventLog:
    log = get_default_log()
    if log is None:
        # Empty response is friendlier than 404 — let the endpoint return data: []
        # callers handle that without HTTP errors.
        return None  # type: ignore[return-value]
    return log


@router.get("/health")
def health() -> dict[str, Any]:
    log = get_default_log()
    return {
        "status": "ok",
        "aperture_version": __version__,
        "sqlite_log_configured": log is not None,
        "token_event_count": log.count_tokens() if log is not None else 0,
        "cache_event_count": log.count_cache() if log is not None else 0,
    }


@router.post("/project/usage/input_tokens_contributed")
def input_tokens_contributed(body: TokenUsageRequest) -> dict[str, Any]:
    log = _log_or_404()
    if log is None:
        return {"data": [], "page": body.page, "page_size": body.page_size, "total_groups": 0,
                "queried_at": _now_iso(), "warning": "no_sqlite_event_log"}
    try:
        rows = log.all_token_events()
        return {
            **aggregate_token_events_v1(
                rows,
                group_by=body.group_by,
                dt_gt=body.dt_gt,
                dt_lt=body.dt_lt,
                user_id=body.user_id,
                session_id=body.session_id,
                order_by=body.order_by,
                order_direction=body.order_direction,
                page=body.page,
                page_size=body.page_size,
            ),
            "queried_at": _now_iso(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/project/usage/cache_tokens_saved")
def cache_tokens_saved(body: CacheSavingsRequest) -> dict[str, Any]:
    log = _log_or_404()
    if log is None:
        return {"data": [], "page": body.page, "page_size": body.page_size, "total_groups": 0,
                "queried_at": _now_iso(), "warning": "no_sqlite_event_log"}
    try:
        rows = log.all_cache_events()
        return {
            **aggregate_cache_events_v1(
                rows,
                group_by=body.group_by,
                dt_gt=body.dt_gt,
                dt_lt=body.dt_lt,
                user_id=body.user_id,
                page=body.page,
                page_size=body.page_size,
            ),
            "queried_at": _now_iso(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/overlay")
def schema_overlay() -> dict[str, Any]:
    """Serve the generated schema optimizer overlay for the dashboard."""

    import json
    import os
    from pathlib import Path

    path = Path(os.getenv("APERTURE_OVERLAY_PATH") or default_overlay_path())
    if not path.exists():
        return {
            "version": 1,
            "aperture_optimizer_version": __version__,
            "generated_at": None,
            "tools": {},
            "stats": {
                "total_results": 0,
                "accepted": 0,
                "rejected": 0,
                "total_tokens_saved": 0,
            },
            "warning": "overlay_not_found",
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"invalid overlay JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="invalid overlay JSON: expected object")
    return data


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def create_api_app() -> FastAPI:
    """Standalone FastAPI app — useful for `uvicorn aperture.observability.api_endpoints:create_api_app --factory`.

    The proxy itself is an MCP server, not a FastAPI app; the v3.1 endpoints
    typically run on a different port (e.g., 8002) so the LLM client and the
    dashboard don't share infrastructure.
    """
    app = FastAPI(
        title="Aperture v3.1 API",
        version=__version__,
        description="v3.1-shape token attribution + cache savings for Aperture.",
    )
    app.include_router(router)
    return app
