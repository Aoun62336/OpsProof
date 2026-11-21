"""Interrupt one active local consumer, prove pending reclaim and duplicate fencing."""

import json
import subprocess
import time
from urllib.request import Request, urlopen
from uuid import uuid4

from scripts.platform.forward import services
from scripts.platform.local_cluster import kubectl_prefix
from scripts.platform.preflight import ROOT


def main():
    kube = kubectl_prefix()

    def run(*args):
        return subprocess.check_output([*kube, *args], text=True, timeout=30)

    def redis(*args):
        return json.loads(
            run(
                "exec",
                "-n",
                "opsproof-demo",
                "demo-deps-redis-0",
                "--",
                "redis-cli",
                "--json",
                *args,
            )
        )

    groups = redis("XINFO", "GROUPS", "opsproof:jobs")
    group = next(g for g in groups if g["name"] == "opsproof-workers")
    if group["lag"] or group["pending"]:
        raise RuntimeError("Queue must be idle before consumer interruption")
    pods = json.loads(
        run(
            "get",
            "pods",
            "-n",
            "opsproof-demo",
            "-l",
            "opsproof.io/role=worker",
            "-o",
            "json",
        )
    )["items"]
    if len(pods) != 1 or pods[0]["status"]["phase"] != "Running":
        raise RuntimeError("Trial requires exactly one running worker, no autoscaler")
    name = pods[0]["metadata"]["name"]
    uid = pods[0]["metadata"]["uid"]
    container_id = pods[0]["status"]["containerStatuses"][0]["containerID"].split("://")[1]

    def signal_worker(signal):
        info = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "exec",
                    "k3d-opsproof-server-0",
                    "crictl",
                    "inspect",
                    container_id,
                ],
                text=True,
            )
        )
        if info["status"]["labels"].get("io.kubernetes.pod.uid") != uid or info["info"]["pid"] <= 1:
            raise RuntimeError("Container identity does not match the trial worker")
        subprocess.run(
            [
                "docker",
                "exec",
                "k3d-opsproof-server-0",
                "kill",
                "-" + signal,
                str(info["info"]["pid"]),
            ],
            check=True,
        )

    stopped = False
    record = {"worker_pod": name, "worker_uid": uid, "passed": False}
    with services([("opsproof-demo", "demo-api", 18088, 8080)]):

        def api(path, body=None):
            req = Request(
                "http://127.0.0.1:18088" + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={
                    "Content-Type": "application/json",
                    "Idempotency-Key": str(uuid4()),
                },
            )
            with urlopen(req, timeout=5) as response:
                return json.load(response)

        try:
            job = api("/api/v1/jobs", {"duration_ms": 2000})
            job_id = job["id"]
            record["job_id"] = job_id
            deadline = time.monotonic() + 20
            while api("/api/v1/jobs/" + job_id)["status"] != "processing":
                if time.monotonic() > deadline:
                    raise RuntimeError("Could not observe active job before interruption")
                time.sleep(0.05)
            signal_worker("STOP")
            stopped = True
            record["pending_before"] = redis(
                "XPENDING", "opsproof:jobs", "opsproof-workers", "-", "+", "10"
            )
            record["job_before"] = api("/api/v1/jobs/" + job_id)
            if record["job_before"]["status"] != "processing" or not record["pending_before"]:
                raise RuntimeError("Interruption did not leave actual pending work")
            # Delete only the observed disposable worker Pod. Its Deployment
            # replaces it; no database, Redis, PVC, or controller is removed.
            current = json.loads(run("get", "pod", name, "-n", "opsproof-demo", "-o", "json"))
            if current["metadata"]["uid"] != uid:
                raise RuntimeError("Worker identity changed")
            signal_worker("KILL")
            run(
                "delete",
                "pod",
                name,
                "-n",
                "opsproof-demo",
                "--grace-period=0",
                "--force",
                "--wait=false",
            )
            stopped = False
            deadline = time.monotonic() + 150
            while True:
                result = api("/api/v1/jobs/" + job_id)
                if result["status"] == "completed":
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError("Interrupted job was not reclaimed")
                time.sleep(1)
            if result["attempts"] != 2:
                raise RuntimeError("Expected exactly one interrupted attempt and one fenced retry")
            record["job_after_reclaim"] = result
            record["duplicate_stream_id"] = redis("XADD", "opsproof:jobs", "*", "job_id", job_id)
            time.sleep(5)
            after = api("/api/v1/jobs/" + job_id)
            if after != result:
                raise RuntimeError("Duplicate delivery changed the durable completed job")
            record["groups_after"] = redis("XINFO", "GROUPS", "opsproof:jobs")
            group = next(g for g in record["groups_after"] if g["name"] == "opsproof-workers")
            if group["lag"] or group["pending"]:
                raise RuntimeError("Queue did not drain after duplicate acknowledgment")
            record["consumers_after"] = redis(
                "XINFO", "CONSUMERS", "opsproof:jobs", "opsproof-workers"
            )
            record["passed"] = True
        finally:
            if stopped:
                signal_worker("CONT")
            (ROOT / ".runtime/platform/acceptance/consumer-recovery.json").write_text(
                json.dumps(record, indent=2) + "\n"
            )
    print("PASS: pending consumer reclaimed, exact job completed, duplicate delivery fenced")


if __name__ == "__main__":
    main()
