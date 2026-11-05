"""Validated configuration for independent control-plane processes."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    api_key: str = ""
    alert_webhook_token: str = ""
    target_url: str = "http://opsproof-demo-api:8080"
    action_stream: str = "opsproof:actions:v1"
    evidence_stream: str = "opsproof:evidence:v1"

    # Browser sessions are restricted to local development initially.
    secure_cookies: bool = False
    allowed_browser_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8090,http://127.0.0.1:8090"
    )

    model_config = SettingsConfigDict(
        env_prefix="OPSPROOF_CONTROL_",
        extra="ignore",
    )


@lru_cache
def settings() -> Settings:
    return Settings()
