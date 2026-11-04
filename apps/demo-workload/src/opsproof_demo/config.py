"""Validated environment configuration shared by workload processes."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str

    stream_name: str = "opsproof:jobs"
    consumer_group: str = "opsproof-workers"

    max_attempts: int = 3
    lease_seconds: int = 15

    model_config = SettingsConfigDict(
        env_prefix="OPSPROOF_",
        extra="ignore",
    )


@lru_cache
def settings() -> Settings:
    return Settings()
