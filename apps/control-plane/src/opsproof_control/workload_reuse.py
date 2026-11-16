"""Fixed second-workload, read-only observations; never a recovery authority."""

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

import httpx2 as httpx
from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb

from .auth import authorize
from .config import settings
from .db import pool
from .reliability_diagnosis import Observation, deterministic_reliability

BASE = "http://reuse-target.opsproof-reuse-test.svc.cluster.local:8080"
router = APIRouter(
    prefix="/api/v1/m6/reuse", tags=["M6 second workload"], dependencies=[Depends(authorize)]
)


def collect():
    observed = datetime.now(UTC)
    facts = {
        "target": "opsproof-reuse-test",
        "observed_at": observed.isoformat(),
        "ready": False,
        "work_samples_seconds": [],
        "errors": [],
        "metrics_available": False,
    }
    with httpx.Client(base_url=BASE, timeout=3, trust_env=False, follow_redirects=False) as client:
        try:
            response = client.get("/health/ready")
            facts["ready"] = response.status_code == 200
            for _ in range(3):
                started = perf_counter()
                response = client.get("/work")
                response.raise_for_status()
                if response.json() != {"status": "ok"}:
                    raise ValueError("Unexpected second workload response")
                facts["work_samples_seconds"].append(perf_counter() - started)
            response = client.get("/metrics")
            response.raise_for_status()
            if len(response.content) > 128_000:
                raise ValueError("Second workload metrics exceed bound")
            facts["metrics_available"] = "opsproof_fixture_work_seconds_count" in response.text
        except (httpx.HTTPError, ValueError) as exc:
            facts["errors"].append(type(exc).__name__)
    # Direct HTTP samples establish observed health and timing, not Prometheus
    # freshness or corroborated traces. Missing independent signals force abstention.
    observation = Observation(
        observed_at=observed,
        target="opsproof-reuse-test",
        metrics_fresh=False,
        collection_errors=["Independent Prometheus/log/trace correlation unavailable"],
    )
    return facts, deterministic_reliability(observation).model_dump()


@router.post("/investigations", status_code=201)
def investigate():
    config = settings()
    if not config.m6_enabled or not config.m6_reuse_enabled:
        raise HTTPException(status_code=404, detail="M6 reuse observation is disabled")
    facts, finding = collect()
    identifier = uuid4()
    with pool().connection() as conn:
        conn.execute(
            "INSERT INTO m6_reuse_observations(id,target,observed_at,observations,finding) "
            "VALUES (%s,'opsproof-reuse-test',%s,%s,%s)",
            (identifier, facts["observed_at"], Jsonb(facts), Jsonb(finding)),
        )
    return {
        "id": identifier,
        "observations": facts,
        "finding": finding,
        "observation_only": True,
        "recovery_authorized": False,
    }


@router.get("/investigations")
def history():
    config = settings()
    if not config.m6_enabled or not config.m6_reuse_enabled:
        raise HTTPException(status_code=404, detail="M6 reuse observation is disabled")
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM m6_reuse_observations ORDER BY observed_at DESC LIMIT 30"
        ).fetchall()
