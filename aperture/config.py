"""Aperture configuration and Redis client."""

import os
from pathlib import Path

from dotenv import load_dotenv
from upstash_redis import Redis

# Load .env from repo root
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class Config:
    """Simple config container loaded from environment."""

    COMPOSIO_API_KEY: str | None = os.getenv("COMPOSIO_API_KEY")
    COMPOSIO_USER_ID: str | None = os.getenv("COMPOSIO_USER_ID")
    COMPOSIO_GITHUB_ACCOUNT_ID: str | None = os.getenv("COMPOSIO_GITHUB_ACCOUNT_ID")
    COMPOSIO_GMAIL_ACCOUNT_ID: str | None = os.getenv("COMPOSIO_GMAIL_ACCOUNT_ID")
    UPSTASH_REDIS_REST_URL: str | None = os.getenv("UPSTASH_REDIS_REST_URL")
    UPSTASH_REDIS_REST_TOKEN: str | None = os.getenv("UPSTASH_REDIS_REST_TOKEN")
    APERTURE_ENV: str = os.getenv("APERTURE_ENV", "local")

    @classmethod
    def redis_client(cls) -> Redis:
        """Return an Upstash Redis client."""
        if not cls.UPSTASH_REDIS_REST_URL or not cls.UPSTASH_REDIS_REST_TOKEN:
            raise RuntimeError(
                "UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN must be set in .env"
            )
        return Redis(
            url=cls.UPSTASH_REDIS_REST_URL,
            token=cls.UPSTASH_REDIS_REST_TOKEN,
        )
