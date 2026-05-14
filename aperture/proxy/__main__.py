"""`python -m aperture.proxy` entrypoint.

Reads `ProxyConfig.from_env()` and starts a uvicorn server hosting the
proxy's ASGI app. For local dev you'd typically run:

    APERTURE_COMPOSIO_MCP_URL_TEMPLATE="https://backend.composio.dev/tool_router/{session_id}/mcp" \\
    python -m aperture.proxy

Then point your LLM client's MCP URL at
`http://127.0.0.1:8001/mcp/?session_id=<composio_tool_router_session>&user_id=<user>`.
If APERTURE_COMPOSIO_MCP_URL_TEMPLATE is a literal URL with no placeholders,
the query params are optional.
"""

from __future__ import annotations

import logging
import sys

import uvicorn

from aperture.proxy.config import ProxyConfig
from aperture.proxy.server import create_app


def main() -> int:
    cfg = ProxyConfig.from_env()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    uvicorn.run(
        create_app,
        factory=True,
        host=cfg.host,
        port=cfg.port,
        log_level=cfg.log_level.lower(),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
