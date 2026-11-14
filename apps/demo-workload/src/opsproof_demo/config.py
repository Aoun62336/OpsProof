"""Validated environment configuration shared by workload processes."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str

    stream_name: str = "opsproof:jobs"
    consumer_group: str = "opsproof-workers"

    inspection_key: str = ""
    recovery_key: str = ""
    m6_dependency_probe_enabled: bool = False

    # Fixed in-namespace, test-only HTTP downstream; disabled in all M5 profiles.
    downstream_enabled: bool = False
    downstream_url: Literal["http://demo-downstream.opsproof-demo.svc.cluster.local:8080/work"] = (
        "http://demo-downstream.opsproof-demo.svc.cluster.local:8080/work"
    )
    downstream_timeout_ms: int = Field(default=400, ge=100, le=2000)
    downstream_attempts: int = Field(default=1, ge=1, le=2)

    max_attempts: int = 3
    lease_seconds: int = 15

    model_config = SettingsConfigDict(
        env_prefix="OPSPROOF_",
        extra="ignore",
    )


@lru_cache
def settings() -> Settings:
    return Settings()
