"""Validated configuration for independent control-plane processes."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    redis_url: str
    api_key: str = ""
    alert_webhook_token: str = ""
    inspection_key: str = ""
    recovery_key: str = ""
    recovery_enabled: bool = False
    m6_enabled: bool = False
    m6_arm_enabled: bool = False
    m6_reuse_enabled: bool = False
    kubernetes_recovery_enabled: bool = False
    kubernetes_observation_enabled: bool = False
    environment: Literal["local", "temporary-eks"] = "local"
    prometheus_url: str = "http://prometheus:9090"
    ai_enabled: bool = False
    ai_daily_limit: int = 10
    ai_provider: str = "gemini"
    ai_model: str = "gemini-2.5-flash-lite"
    ai_api_key: str = ""
    target_url: str = "http://opsproof-demo-api:8080"
    action_stream: str = "opsproof:actions:v1"
    evidence_stream: str = "opsproof:evidence:v1"

    # Browser sessions are restricted to local development initially.
    secure_cookies: bool = False
    allowed_browser_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8090,http://127.0.0.1:8090"
    )

    @model_validator(mode="after")
    def cloud_actions_stay_disabled(self):
        if self.environment == "temporary-eks" and (
            self.recovery_enabled or self.kubernetes_recovery_enabled or self.m6_arm_enabled
        ):
            raise ValueError("Temporary EKS supports observation, not local recovery execution")
        return self

    model_config = SettingsConfigDict(
        env_prefix="OPSPROOF_CONTROL_",
        extra="ignore",
    )


@lru_cache
def settings() -> Settings:
    return Settings()
