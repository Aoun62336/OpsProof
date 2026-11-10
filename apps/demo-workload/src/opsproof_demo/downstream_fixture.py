"""Isolated, test-only HTTP latency fixture with no mutation endpoint.

The workload's worker performs a real HTTP GET to this service in the M6 profile.
Delay is configured on the Pod, not by arbitrary incoming request parameters.
"""

import time

from fastapi import FastAPI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FixtureConfig(BaseSettings):
    enabled: bool = False
    delay_ms: int = Field(default=0, ge=0, le=2000)
    model_config = SettingsConfigDict(
        env_prefix="OPSPROOF_M6_FIXTURE_", extra="ignore",
    )


app = FastAPI(title="OpsProof M6 internal downstream fixture", docs_url=None, redoc_url=None)


@app.get("/health/live")
def live():
    return {"status": "alive"}


@app.get("/health/ready")
def ready():
    if not FixtureConfig().enabled:
        from fastapi import HTTPException
        raise HTTPException(503, "M6 fixture disabled")
    return {"status": "ready"}


@app.get("/work")
def work():
    settings = FixtureConfig()
    if not settings.enabled:
        from fastapi import HTTPException
        raise HTTPException(503, "M6 fixture disabled")
    if settings.delay_ms:
        time.sleep(settings.delay_ms / 1000)
    return {"status": "ok"}
