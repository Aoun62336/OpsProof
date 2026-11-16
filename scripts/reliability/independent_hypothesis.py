"""Decide hypotheses from independent live samples and durable observations."""

from datetime import UTC, datetime

from opsproof_control.reliability_diagnosis import Observation, deterministic_reliability


def establish(state, samples, jobs, signals):
    start = datetime.fromisoformat(state["dispatch_intent_at"])
    stop = datetime.fromisoformat(state["cleanup_started_at"])
    if start.tzinfo is None or stop.tzinfo is None or stop < start:
        raise ValueError("Bounded dispatch/cleanup window required")
    if state["scenario"] == "database_connectivity":
        return any(
            r.get("database_probe_status") == 503
            and r.get("database_probe_detail") == "Fresh database connection unavailable"
            and r.get("control_ready") == 200
            and start
            <= datetime.fromisoformat(r["database_probe_at"])
            <= datetime.fromisoformat(r["database_probe_until"])
            <= stop
            and start
            <= datetime.fromisoformat(r["control_ready_at"])
            <= datetime.fromisoformat(r["control_ready_until"])
            <= stop
            for r in samples
            if "database_probe_at" in r
        )
    rows = [
        r
        for r in samples
        if start <= datetime.fromisoformat(r["at"])
        and datetime.fromisoformat(r.get("collected_until", r["at"])) <= stop
    ]
    if not rows:
        return False
    mode = state.get("capacity_mode")
    if mode:
        values = [r.get("rollout" if mode == "hpa" else "worker", {}).get("desired") for r in rows]
        values = [v for v in values if type(v) is int]
        return bool(
            len(jobs) == 60
            and all(j["attempts"] == 1 and j["duration_ms"] == 2000 for j in jobs)
            and values
            and (mode == "fixed" or max(values) > 1 and values[-1] == 1)
            and signals["logs_relevant"]
        )
    scenario = state["scenario"]
    if scenario == "worker_saturation":
        return bool(
            len(jobs) == 60
            and all(j["attempts"] == 1 and j["duration_ms"] == 2000 for j in jobs)
            and any(
                type(r.get("queue", {}).get("lag")) is int and r["queue"]["lag"] >= 10 for r in rows
            )
            and signals["logs_relevant"]
        )
    if scenario == "worker_failure":
        old = state["old_worker"]["uid"]
        before = any(any(p["uid"] == old for p in r.get("worker_pods", [])) for r in samples)
        after = any(
            any(p["uid"] != old and p["ready"] for p in r.get("worker_pods", [])) for r in rows
        )
        return bool(
            before
            and after
            and len(jobs) == 1
            and jobs[0]["attempts"] == 2
            and signals["logs_relevant"]
        )
    if scenario == "faulty_release":
        failures = [r for r in rows if r.get("release_status") == 500]
        rejected = any(
            a["phase"] in ("Failed", "Error")
            and datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")) >= start
            and any(owner["uid"] == r.get("rollout", {}).get("uid") for owner in a["owners"])
            for r in rows
            for a in r.get("analyses", [])
        )
        return bool(
            failures
            and rejected
            and any(r.get("rollout", {}).get("abort") for r in rows)
            and signals["traces"]
        )
    if scenario == "downstream_latency":
        return bool(
            jobs
            and signals["logs_relevant"]
            and signals["downstream_linked"]
            and signals["downstream_timeout"]
        )
    if scenario == "misleading_evidence":
        missing = [
            r
            for r in rows
            if "observer_metrics_status" in r and r["observer_metrics_status"] is None
        ]
        if not missing:
            return False
        actual = Observation(
            observed_at=datetime.fromisoformat(missing[0]["at"]),
            target="opsproof-demo",
            metrics_fresh=False,
            collection_errors=["Independent observer connection unavailable"],
        )
        cases = [
            actual,
            actual.model_copy(update={"observed_at": datetime(2020, 1, 1, tzinfo=UTC)}),
            actual.model_copy(
                update={
                    "metrics_fresh": True,
                    "contradictions": ["Controlled contradictory replay"],
                }
            ),
        ]
        return all(
            (finding := deterministic_reliability(case)).abstained and finding.action == "none"
            for case in cases
        )
    raise ValueError("Unknown fixed scenario")
