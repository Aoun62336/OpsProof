"""Validated configuration for independent control-plane processes."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    api_key: str = ""
    target_url: str = "http://opsproof-demo-api:8080"
    action_stream: str = "opsproof:actions:v1"
    evidence_stream: str = "opsproof:evidence:v1"

    model_config = SettingsConfigDict(
        env_prefix="OPSPROOF_CONTROL_",
        extra="ignore",
    )


@lru_cache
def settings() -> Settings:
    return Settings()
