"""Separate mutation and independent verification for one fixed Kubernetes runbook."""

import logging
from datetime import UTC, datetime
from math import isfinite

import httpx2 as httpx
from psycopg.types.json import Jsonb

from . import kubernetes_client
from .config import settings
from .db import pool
from .kubernetes_operations import event
from .kubernetes_policy import PolicyDenied, validate

logger = logging.getLogger(__name__)


def telemetry():
    config = settings()
    result = {}
    with httpx.Client(base_url=config.prometheus_url, timeout=3, trust_env=False) as client:
        for name, query in {
            "sample_time": 'timestamp(up{job="opsproof-demo-api"})',
            "up": 'up{job="opsproof-demo-api"}',
            "queued": 'opsproof_demo_jobs{job="opsproof-demo-api",state="queued"}',
        }.items():
            response = client.get("/api/v1/query", params={"query": query})
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "success" or len(data["data"]["result"]) != 1:
                raise PolicyDenied("Metrics are absent or ambiguous")
            value = float(data["data"]["result"][0]["value"][1])
            if not isfinite(value):
                raise PolicyDenied("Metrics must be finite")
            result[name] = value
    with httpx.Client(base_url=config.target_url, timeout=3, trust_env=False) as client:
        response = client.get("/health/ready")
        result["ready"] = response.status_code == 200 and result["up"] == 1
    return result


def finish(recovery_id, status, reason):
    with pool().connection() as conn:
        updated = conn.execute(
            "UPDATE kubernetes_recoveries SET status=%s,error=%s,completed_at=now() "
            "WHERE id=%s AND status IN ('running','verifying') RETURNING id",
            (status, reason, recovery_id),
        ).fetchone()
        if updated:
            event(conn, recovery_id, status, {"reason": reason})


def execute_next():
    if not settings().kubernetes_recovery_enabled:
        return
    with pool().connection() as conn:
        # Never replay an uncertain PATCH after a crash or timeout.
        abandoned = conn.execute(
            "UPDATE kubernetes_recoveries SET "
            "status='indeterminate',completed_at=now(),error='Worker interrupted; "
            "mutation is not replayed' WHERE status='running' AND started_at < "
            "now()-interval '30 seconds' RETURNING id"
        ).fetchall()
        for row in abandoned:
            event(conn, row["id"], "indeterminate")
        expired = conn.execute(
            "UPDATE kubernetes_recoveries SET status='expired',completed_at=now() WHERE "
            "status IN ('pending_approval','approved') AND expires_at<=now() RETURNING "
            "id"
        ).fetchall()
        for row in expired:
            event(conn, row["id"], "expired")
        row = conn.execute(
            "SELECT * FROM kubernetes_recoveries WHERE status='approved' ORDER BY "
            "created_at FOR UPDATE SKIP LOCKED LIMIT 1"
        ).fetchone()
        if not row:
            return
        row = conn.execute(
            "UPDATE kubernetes_recoveries SET status='running',started_at=now() WHERE "
            "id=%s RETURNING *",
            (row["id"],),
        ).fetchone()
        event(conn, row["id"], "attempt_started")
    sent = False
    try:
        if kubernetes_client.request(check_scaler=True) is not None:
            raise PolicyDenied("KEDA owns worker replicas; recovery denied")
        current_telemetry = telemetry()
        target = kubernetes_client.request()
        with pool().connection() as conn:
            current = conn.execute(
                "SELECT * FROM kubernetes_recoveries WHERE id=%s", (row["id"],)
            ).fetchone()
            incident = conn.execute(
                "SELECT * FROM incidents WHERE fingerprint=%s", (row["incident_fingerprint"],)
            ).fetchone()
            experiment = conn.execute(
                "SELECT * FROM experiments WHERE id=%s", (row["run_id"],)
            ).fetchone()
        patch = validate(current, target, current_telemetry, incident, experiment)
        sent = True
        response = kubernetes_client.request("PATCH", patch)
        if response["metadata"]["annotations"].get("opsproof.io/recovery-id") != str(row["id"]):
            raise RuntimeError("Acknowledgment does not identify this operation")
        with pool().connection() as conn:
            conn.execute(
                "UPDATE kubernetes_recoveries SET status='verifying',result=%s WHERE id=%s "
                "AND status='running'",
                (
                    Jsonb({"acknowledged_version": response["metadata"]["resourceVersion"]}),
                    row["id"],
                ),
            )
            event(
                conn,
                row["id"],
                "action_acknowledged",
                {
                    "uid": response["metadata"]["uid"],
                    "resource_version": response["metadata"]["resourceVersion"],
                },
            )
    except (PolicyDenied, FileNotFoundError) as exc:
        finish(row["id"], "indeterminate" if sent else "failed", str(exc)[:200])
    except httpx.HTTPStatusError as exc:
        known_denial = exc.response.status_code in (401, 403, 404, 409, 422)
        finish(
            row["id"],
            "failed" if known_denial else "indeterminate",
            f"Kubernetes HTTP {exc.response.status_code}",
        )
    except Exception as exc:
        finish(
            row["id"],
            "indeterminate" if sent else "failed",
            f"Evidence or response unavailable: {type(exc).__name__}",
        )


def observe_and_verify():
    if not settings().kubernetes_recovery_enabled:
        return
    with pool().connection() as conn:
        expired = conn.execute(
            "UPDATE kubernetes_recoveries SET status='indeterminate',completed_at=now(), "
            "error='Independent verification deadline exceeded' WHERE status='verifying' "
            "AND started_at < now()-interval '180 seconds' RETURNING id"
        ).fetchall()
        for item in expired:
            event(conn, item["id"], "indeterminate")
    try:
        target = kubernetes_client.request()
        current_telemetry = telemetry()
        # Deliberately exclude environment, managedFields and last-applied data.
        safe_target = {
            "kind": target["kind"],
            "metadata": {
                key: target["metadata"][key]
                for key in ("name", "namespace", "uid", "resourceVersion", "generation")
            },
            "spec": {
                "replicas": target["spec"]["replicas"],
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "image": target["spec"]["template"]["spec"]["containers"][0][
                                    "image"
                                ],
                                "resources": target["spec"]["template"]["spec"]["containers"][0][
                                    "resources"
                                ],
                            }
                        ]
                    }
                },
            },
            "status": target.get("status", {}),
        }
        safe_target["metadata"]["annotations"] = {
            k: v
            for k, v in target["metadata"].get("annotations", {}).items()
            if k.startswith("opsproof.io/")
        }
        with pool().connection() as conn:
            conn.execute(
                "INSERT INTO kubernetes_observations (name,observed_at,resource,telemetry) "
                "VALUES ('demo-worker',now(),%s,%s) ON CONFLICT(name) DO UPDATE SET "
                "observed_at=excluded.observed_at,resource=excluded.resource,telemetry=excluded.telemetry",
                (Jsonb(safe_target), Jsonb(current_telemetry)),
            )
            rows = conn.execute(
                "SELECT * FROM kubernetes_recoveries WHERE status='verifying'"
            ).fetchall()
        for row in rows:
            now = datetime.now(UTC)
            if (now - row["started_at"]).total_seconds() > 180:
                finish(row["id"], "indeterminate", "Independent verification deadline exceeded")
                continue
            meta, status = target["metadata"], target.get("status", {})
            if meta["uid"] != row["target_uid"] or meta.get("annotations", {}).get(
                "opsproof.io/recovery-id"
            ) != str(row["id"]):
                finish(
                    row["id"],
                    "indeterminate",
                    "Target was replaced or a different operation changed it",
                )
                continue
            if target["spec"]["template"]["spec"]["containers"][0]["image"] != row["target_image"]:
                finish(row["id"], "indeterminate", "Workload revision changed")
                continue
            if (
                target["spec"]["replicas"] != 1
                or status.get("readyReplicas") != 1
                or status.get("observedGeneration") != meta["generation"]
            ):
                continue
            if (
                not current_telemetry["ready"]
                or not 0 <= now.timestamp() - current_telemetry["sample_time"] <= 30
            ):
                continue
            jobs = []
            with httpx.Client(base_url=settings().target_url, timeout=3, trust_env=False) as client:
                for job_id in row["job_ids"]:
                    response = client.get("/api/v1/jobs/" + job_id)
                    response.raise_for_status()
                    jobs.append(response.json())
            if any(
                job.get("id") != job_id or job.get("status") != "completed"
                for job_id, job in zip(row["job_ids"], jobs, strict=True)
            ):
                continue
            with pool().connection() as conn:
                incident = conn.execute(
                    "SELECT status,resolved_at FROM incidents WHERE fingerprint=%s",
                    (row["incident_fingerprint"],),
                ).fetchone()
                experiment = conn.execute(
                    "SELECT status FROM experiments WHERE id=%s", (row["run_id"],)
                ).fetchone()
                if (
                    not incident
                    or incident["status"] != "resolved"
                    or not incident["resolved_at"]
                    or incident["resolved_at"] < row["started_at"]
                    or not experiment
                    or experiment["status"] != "succeeded"
                ):
                    continue
                result = {
                    **row["result"],
                    "target_uid": meta["uid"],
                    "image": row["target_image"],
                    "ready_replicas": 1,
                    "job_ids": row["job_ids"],
                    "job_statuses": [j["status"] for j in jobs],
                    "incident_status": "resolved",
                    "experiment_status": "succeeded",
                    "sample_time": current_telemetry["sample_time"],
                }
                conn.execute(
                    "UPDATE kubernetes_recoveries SET "
                    "status='succeeded',result=%s,completed_at=now() WHERE id=%s AND "
                    "status='verifying'",
                    (Jsonb(result), row["id"]),
                )
                event(conn, row["id"], "independently_verified", result)
    except Exception:
        # Missing observations age out; they never become a false healthy signal.
        logger.warning("Kubernetes observation unavailable", exc_info=False)
