from pathlib import Path

from aperture.config import ApertureConfig


def test_config_loads_environment(monkeypatch):
    monkeypatch.setenv("APERTURE_MODE", "safe")
    monkeypatch.setenv("APERTURE_RAW_STORE_PATH", ".tmp/raw")
    monkeypatch.setenv("APERTURE_EVENT_SINK_PATH", ".tmp/events.jsonl")
    monkeypatch.setenv("APERTURE_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("COMPOSIO_API_KEY", "test-key")
    monkeypatch.setenv("COMPOSIO_USER_ID", "user_1")
    monkeypatch.setenv("APERTURE_ENABLE_LIVE_TESTS", "true")

    config = ApertureConfig.from_env()

    assert config.mode == "safe"
    assert config.raw_store_path == Path(".tmp/raw")
    assert config.event_sink_path == Path(".tmp/events.jsonl")
    assert config.redis_url == "redis://localhost:6379/0"
    assert config.composio_api_key == "test-key"
    assert config.composio_user_id == "user_1"
    assert config.enable_live_tests is True
