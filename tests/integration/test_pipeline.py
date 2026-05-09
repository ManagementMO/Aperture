from aperture.cache.redis_store import InMemoryCacheStore
from aperture.integration.pipeline import aperture_tool_result_pipeline
from aperture.types import ExecutionContext


async def test_pipeline_compresses_model_facing_payload():
    context = ExecutionContext("p1", "u1", "s1", "acct_1", "GITHUB", "GITHUB_LIST_ISSUES", None, "gpt-4o-mini")

    async def execute():
        return [{"title": "Bug", "state": "open", "labels": [{"name": "bug"}], "url": "api"}]

    result = await aperture_tool_result_pipeline("GITHUB_LIST_ISSUES", {"q": "auth"}, context, execute, cache_store=InMemoryCacheStore())
    assert result["aperture_compressed"] is True
    assert result["data"][0]["title"] == "Bug"

