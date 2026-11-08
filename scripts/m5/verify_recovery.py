"""Bounded real M4 or Kubernetes recovery drill with independently stored evidence."""

import argparse
import json
import subprocess
import time
from uuid import uuid4

from local_cluster import kubectl_prefix
from preflight import ROOT
from render_local_secrets import read_env
from smoke import forwarded_apis
from verify_k3d import http


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("m4", "kubernetes"), required=True)
    mode = parser.parse_args().mode
    kube = kubectl_prefix()
    key = read_env(ROOT / ".env")["OPSPROOF_CONTROL_API_KEY"]
    base = "http://127.0.0.1:18090"
    record = {"mode": mode, "passed": False, "denials": []}
    fault = False

    def command(*args):
        return subprocess.check_output([*kube, *args], text=True, timeout=30)

    def worker():
        return json.loads(command("get", "deployment", "demo-worker", "-n", "opsproof-demo", "-o", "json"))

    def call(method, path, payload=None, authenticated=True, idem=None):
        return http(base, method, "/api/v1" + path, key if authenticated else "", idem or str(uuid4()), payload)

    def data(path):
        status, body = call("GET", path)
        if status != 200:
            raise RuntimeError(f"Read {path} failed: {status}")
        return body

    def wait(check, description, seconds=120):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            time.sleep(2)
        raise RuntimeError("Timed out: " + description)

    with forwarded_apis():
        _, stats = http("http://127.0.0.1:18088", "GET", "/api/v1/stats")
        if stats["queued"] or stats["processing"]:
            raise RuntimeError("Queue must be idle before recovery drill")
        try:
            if mode == "m4":
                command("exec", "deployment/demo-worker", "-n", "opsproof-demo", "--", "python", "-m", "opsproof_demo.worker_control", "pause", "--seconds", "420")
            else:
                observed = worker()
                if observed["metadata"].get("annotations", {}).get("opsproof.io/recovery-policy") != "restore-single-worker-v1":
                    raise RuntimeError("Recovery-managed worker required")
                record["target_before"] = {"uid": observed["metadata"]["uid"], "image": observed["spec"]["template"]["spec"]["containers"][0]["image"]}
                command("scale", "deployment/demo-worker", "-n", "opsproof-demo", "--replicas=0")
                wait(lambda: worker().get("status", {}).get("replicas", 0) == 0, "worker stopped", 45)
            fault = True
            status, experiment = call("POST", "/experiments", {"scenario": "queue-burst", "count": 5, "duration_ms": 250})
            if status != 202:
                raise RuntimeError("Bounded experiment creation failed")
            record["run_id"] = experiment["id"]
            incident = wait(lambda: next((i for i in data("/incidents?status=firing") if i["name"] == "OpsProofDemoQueueBacklog" and i["target"] == "opsproof-demo-api"), None), "real queue alert")
            record["incident_fingerprint"] = incident["fingerprint"]
            print("Observed real firing incident:", mode, flush=True)
            if mode == "m4":
                status, investigation = call("POST", "/investigations", {"incident_fingerprint": incident["fingerprint"], "run_id": experiment["id"]})
                if status != 202:
                    raise RuntimeError("Investigation creation failed")
                ready = wait(lambda: next((r for r in data("/investigations?incident_fingerprint=" + incident["fingerprint"]) if r["id"] == investigation["id"] and r["status"] == "ready"), None), "deterministic investigation", 45)
                record["investigation"] = ready
                path = "/recoveries"
                payload = {"investigation_id": investigation["id"]}
                confirmation = "APPROVE DEMO WORKER RESUME"
            else:
                path = "/kubernetes/recoveries"
                payload = {"action": "restore_demo_worker", "incident_fingerprint": incident["fingerprint"], "run_id": experiment["id"]}
                confirmation = "APPROVE DEMO WORKER RESTORE"
                code, _ = call("POST", path, {**payload, "namespace": "other"})
                if code != 422:
                    raise RuntimeError("Unsupported namespace parameter not denied")
                record["denials"].append({"case": "unsupported namespace", "status": code})
            code, _ = call("POST", path, payload, authenticated=False)
            if code != 401:
                raise RuntimeError("Anonymous recovery not denied")
            record["denials"].append({"case": "unauthorized", "status": code})
            status, proposal = call("POST", path, payload)
            if status != 202:
                raise RuntimeError(f"Recovery proposal rejected: {status} {proposal}")
            record["recovery_id"] = proposal["id"]
            time.sleep(3)
            unchanged = next(r for r in data(path) if r["id"] == proposal["id"])
            if unchanged["status"] != "pending_approval":
                raise RuntimeError("Unapproved operation executed")
            if mode == "kubernetes" and worker()["spec"]["replicas"] != 0:
                raise RuntimeError("A different controller restored the worker before approval")
            record["denials"].append({"case": "unapproved operation", "status": "remained pending; target unchanged"})
            code, _ = call("POST", path + "/" + proposal["id"] + "/approve", {"confirmation": "wrong"})
            if code != 422:
                raise RuntimeError("Invalid confirmation not denied")
            record["denials"].append({"case": "wrong confirmation", "status": code})
            code, approved = call("POST", path + "/" + proposal["id"] + "/approve", {"confirmation": confirmation})
            if code != 200:
                raise RuntimeError(f"Approval failed: {code} {approved}")
            code, _ = call("POST", path + "/" + proposal["id"] + "/approve", {"confirmation": confirmation})
            if code != 409:
                raise RuntimeError("Approval replay not denied")
            record["denials"].append({"case": "replayed approval", "status": code})
            def completed():
                row = next(r for r in data(path) if r["id"] == proposal["id"])
                if row["status"] in ("failed", "expired", "indeterminate"):
                    raise RuntimeError(f"Recovery ended {row['status']}: {row.get('error')}")
                return row if row["status"] == "succeeded" else None
            record["recovery"] = wait(completed, "independently verified restoration", 190)
            record["events"] = data(path + "/" + proposal["id"] + "/events")
            record["experiment"] = data("/experiments/" + experiment["id"])
            record["incident_events"] = data("/incidents/" + incident["fingerprint"] + "/events")
            if record["experiment"]["status"] != "succeeded" or not any(e["status"] == "resolved" for e in record["incident_events"]):
                raise RuntimeError("Independent experiment/incident evidence missing")
            record["passed"] = True
            fault = False
            print("PASS:", mode, "approved recovery, five jobs, alert resolution and denial checks")
        finally:
            if fault:
                record["manual_fault_cleanup"] = True
                if mode == "m4":
                    command("exec", "demo-deps-redis-0", "-n", "opsproof-demo", "--", "redis-cli", "DEL", "opsproof:demo:worker:hold:v1")
                else:
                    command("scale", "deployment/demo-worker", "-n", "opsproof-demo", "--replicas=1")
            (ROOT / f".runtime/m5/acceptance/{mode}-recovery-trial.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    main()
