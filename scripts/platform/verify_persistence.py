"""Restart only the four local StatefulSet Pods; preserve PVCs and exact job state."""

import json
import subprocess
import time
from datetime import UTC, datetime
from uuid import uuid4

from local_cluster import kubectl_prefix
from preflight import ROOT
from render_local_secrets import read_env
from smoke import forwarded_apis
from verify_k3d import http


def main():
    kube = kubectl_prefix()
    smoke = json.loads((ROOT / ".runtime/m5/k3d-smoke.json").read_text())
    key = read_env(ROOT / ".env")["OPSPROOF_CONTROL_API_KEY"]
    marker = "opsproof:m5:persistence:" + str(uuid4())
    changes = []

    def run(args):
        return subprocess.check_output([*kube, *args], text=True, timeout=180).strip()

    def get(resource, name, namespace):
        return json.loads(run(["get", resource, name, "-n", namespace, "-o", "json"]))

    for component in ("demo", "control"):
        namespace = "opsproof-" + component
        redis_pod = component + "-deps-redis-0"
        if (
            run(
                [
                    "exec",
                    "-n",
                    namespace,
                    redis_pod,
                    "--",
                    "redis-cli",
                    "SET",
                    marker,
                    "durable",
                    "EX",
                    "1800",
                ]
            )
            != "OK"
        ):
            raise RuntimeError("Redis marker write failed")
        # AOF everysec: wait for its declared flush interval before a graceful restart.
        time.sleep(2)
        for service in ("postgres", "redis"):
            name = f"{component}-deps-{service}"
            old_pod = get("pod", name + "-0", namespace)["metadata"]["uid"]
            pvc = get("pvc", "data-" + name + "-0", namespace)["metadata"]["uid"]
            run(["rollout", "restart", "statefulset/" + name, "-n", namespace])
            run(
                [
                    "rollout",
                    "status",
                    "statefulset/" + name,
                    "-n",
                    namespace,
                    "--timeout=150s",
                ]
            )
            new_pod = get("pod", name + "-0", namespace)["metadata"]["uid"]
            new_pvc = get("pvc", "data-" + name + "-0", namespace)["metadata"]["uid"]
            if old_pod == new_pod or pvc != new_pvc:
                raise RuntimeError("Expected replacement Pod with unchanged PVC")
            changes.append(
                {
                    "statefulset": name,
                    "old_pod_uid": old_pod,
                    "new_pod_uid": new_pod,
                    "retained_pvc_uid": pvc,
                }
            )
        if run(["exec", "-n", namespace, redis_pod, "--", "redis-cli", "GET", marker]) != "durable":
            raise RuntimeError("Redis acknowledged marker lost")
        run(["exec", "-n", namespace, redis_pod, "--", "redis-cli", "DEL", marker])

    with forwarded_apis():
        jobs = []
        for job in smoke["jobs"]:
            status, item = http("http://127.0.0.1:18088", "GET", "/api/v1/jobs/" + job["id"])
            if status != 200 or item.get("id") != job["id"] or item.get("status") != "completed":
                raise RuntimeError("Durable exact-job state did not survive restart")
            jobs.append(job)
        status, experiment = http(
            "http://127.0.0.1:18090",
            "GET",
            "/api/v1/experiments/" + smoke["run_id"],
            key,
        )
        if (
            status != 200
            or experiment.get("status") != "succeeded"
            or experiment["result"]["verified_completed"] != 5
        ):
            raise RuntimeError("Control experiment state did not survive restart")
        status, events = http(
            "http://127.0.0.1:18090",
            "GET",
            "/api/v1/experiments/" + smoke["run_id"] + "/events",
            key,
        )
        if status != 200 or sum(event["type"] == "verified" for event in events) != 1:
            raise RuntimeError("Expected exactly one durable completion verification")
    record = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "passed": True,
        "run_id": smoke["run_id"],
        "jobs": jobs,
        "statefulsets": changes,
        "redis_markers_retained": ["demo", "control"],
        "verified_event_count": 1,
    }
    (ROOT / ".runtime/m5/acceptance/persistence.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    print(
        "PASS: four StatefulSet Pod replacements retained PVCs, Redis "
        "markers and exact job/experiment state"
    )


if __name__ == "__main__":
    main()
