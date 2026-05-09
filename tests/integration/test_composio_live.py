import os

import pytest


@pytest.mark.live
def test_live_composio_adapter_imports_when_configured():
    if not os.getenv("COMPOSIO_API_KEY") or os.getenv("APERTURE_ENABLE_LIVE_TESTS", "").lower() != "true":
        pytest.skip("Live Composio smoke test requires COMPOSIO_API_KEY and APERTURE_ENABLE_LIVE_TESTS=true")
    from aperture.integration.composio_adapter import ComposioToolExecutor

    executor = ComposioToolExecutor()
    assert executor.get_tools(toolkits=["GITHUB"]) is not None

