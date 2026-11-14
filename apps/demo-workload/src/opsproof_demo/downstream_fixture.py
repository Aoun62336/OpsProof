"""Isolated, test-only HTTP latency fixture with no mutation endpoint.

The workload's worker performs a real HTTP GET to this service in the M6 profile.
Delay is configured on the Pod, not by arbitrary incoming request parameters.
"""

import time

from fastapi import FastAPI, Response
from prometheus_client import CollectorRegistry, Histogram, generate_latest
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FixtureConfig(BaseSettings):
    enabled: bool = False
    delay_ms: int = Field(default=0, ge=0, le=2000)
    model_config = SettingsConfigDict(
        env_prefix="OPSPROOF_M6_FIXTURE_",
        extra="ignore",
    )


app = FastAPI(title="OpsProof M6 internal downstream fixture", docs_url=None, redoc_url=None)
registry = CollectorRegistry()
latency = Histogram(
    "opsproof_fixture_work_seconds",
    "Observed fixture HTTP work time",
    registry=registry,
    buckets=(0.05, 0.1, 0.4, 0.5, 1, 2, 3),
)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(registry), media_type="text/plain; version=0.0.4")


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
    with latency.time():
        if settings.delay_ms:
            time.sleep(settings.delay_ms / 1000)
    return {"status": "ok"}
