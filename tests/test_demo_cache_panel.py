from fastapi.testclient import TestClient

from aperture.agent.composio_agent import AgentRunResult, clear_result_cache
from aperture.cache.store import CacheStore
from api.main import _demo_cache_stats, app


def test_demo_cache_stats_include_current_successful_run():
    clear_result_cache()
    CacheStore().clear_tracked()
    run = AgentRunResult(
        ask="Get the repo overview",
        answer="The repo has 1,234 stars.",
        model="claude-haiku-4-5",
        effort_mode="medium",
    )

    stats = _demo_cache_stats(run)

    assert stats["entries"] == 1
    assert stats["result_entries"] == 1
    assert stats["result_items"][0]["ask"] == "Get the repo overview"
    assert stats["result_items"][0]["source"] == "current_run"


def test_demo_run_endpoint_returns_visible_cache_snapshot(monkeypatch):
    clear_result_cache()
    CacheStore().clear_tracked()

    def fake_run_agent(ask: str, *, effort_mode: str):
        return AgentRunResult(
            ask=ask,
            answer="ok",
            model="claude-haiku-4-5",
            effort_mode=effort_mode,
        )

    import aperture.agent.composio_agent as composio_agent

    monkeypatch.setattr(composio_agent, "run_agent", fake_run_agent)
    response = TestClient(app).post(
        "/api/demo/run",
        json={"ask": "cache smoke", "effort_mode": "medium"},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["cache"]["entries"] == 1
    assert payload["cache"]["result_items"][0]["ask"] == "cache smoke"
