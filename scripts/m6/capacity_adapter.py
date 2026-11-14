"""M6 repeated capacity protocol, preserving each attempt and the M5 evidence.

HPA can explicitly target the existing Rollout scale subresource. No cutover,
Rollout deletion or duplicate API Deployment is needed for capacity measurement.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from uuid import UUID

from scripts.m6.local_environment import ROOT, utc
from scripts.m6.process_identity import running
from scripts.m6.scenario_adapters import Adapter


def delete_exact(env, kind, name, namespace, uid):
    # REST paths are selected from fixed adapter-owned resource kinds only.
    paths = {
        "pod": "/api/v1",
        "hpa": "/apis/autoscaling/v2",
        "scaledobject": "/apis/keda.sh/v1alpha1",
    }
    plurals = {
        "pod": "pods",
        "hpa": "horizontalpodautoscalers",
        "scaledobject": "scaledobjects",
    }
    raw = env.command(["get", kind, name, "-n", namespace, "--ignore-not-found", "-o", "json"])
    if not raw.strip():
        return {"already_absent": True}
    current = json.loads(raw)
    if current["metadata"]["uid"] != uid:
        raise RuntimeError("Owned temporary resource was replaced; deletion refused")
    body = {
        "apiVersion": "v1",
        "kind": "DeleteOptions",
        "preconditions": {"uid": uid},
        "propagationPolicy": "Background",
    }
    return env.command(
        [
            "delete",
            "--raw",
            f"{paths[kind]}/namespaces/{namespace}/{plurals[kind]}/{name}",
            "-f",
            "-",
        ],
        input=json.dumps(body),
    )


class Capacity(Adapter):
    scenario = "worker_saturation"

    def __init__(self, environment, mode):
        super().__init__(environment)
        if mode not in ("fixed", "hpa", "keda"):
            raise ValueError("Capacity mode outside fixed/HPA/KEDA")
        self.mode = mode
        self.load_process = None
        self.load_log = None
        self.state.update(capacity_mode=mode, temporary_controllers=[])

    def snapshot(self):
        super().snapshot()
        app = self.env.get("application", "demo", "argocd")
        self.state["original_application"] = app
        self.state["original_worker_replicas"] = 1
        params = {p["name"]: p["value"] for p in app["spec"]["source"]["helm"]["parameters"]}
        self.state["api_kind"] = (
            "rollout" if params.get("rollout.enabled", "false") == "true" else "deployment"
        )
        self.state["capacity_record"] = {
            "timestamp_utc": utc(),
            "mode": self.mode,
            "passed": False,
            "failure": "not yet independently verified",
            "workload": None,
            "samples": [],
            "trials": 1,
            "load_script_sha256": hashlib.sha256(
                (ROOT / "scripts/m6/capacity_load.py").read_bytes()
            ).hexdigest(),
            "application_revision": app["status"]["sync"]["revision"],
            "protocol": "m6-python-capacity-v3-local",
            "worker_image": self.state["worker_image"],
        }
        self.state["capacity_log_path"] = (
            (self.env.output / "capacity-load.jsonl").relative_to(ROOT).as_posix()
        )
        return self.state

    def inject(self):
        self.state["injection_started_at"] = utc()
        original = self.state["original_application"]
        params = {p["name"]: p["value"] for p in original["spec"]["source"]["helm"]["parameters"]}
        params.update(
            {
                "autoscaling.hpa.enabled": str(self.mode == "hpa").lower(),
                "autoscaling.keda.enabled": str(self.mode == "keda").lower(),
                "worker.recoveryManaged": "false",
                "autoscaling.hpa.rolloutTargetEnabled": str(
                    self.mode == "hpa" and self.state["api_kind"] == "rollout"
                ).lower(),
            }
        )
        expected = [{"name": k, "value": v} for k, v in params.items()]
        self.state["expected_parameters"] = expected
        ignore = list(original["spec"].get("ignoreDifferences", []))
        if self.mode == "hpa":
            ignore.append(
                {
                    "group": "argoproj.io" if self.state["api_kind"] == "rollout" else "apps",
                    "kind": "Rollout" if self.state["api_kind"] == "rollout" else "Deployment",
                    "name": "demo-api",
                    "namespace": "opsproof-demo",
                    "jsonPointers": ["/spec/replicas"],
                }
            )
        self.state["expected_ignore"] = ignore
        self.checkpoint()
        self.env.patch(
            "application",
            "demo",
            original,
            [
                {
                    "op": "replace",
                    "path": "/spec/source/helm/parameters",
                    "value": expected,
                },
                {"op": "add", "path": "/spec/ignoreDifferences", "value": ignore},
            ],
            "argocd",
        )
        until = time.monotonic() + 180
        while time.monotonic() < until:
            self.env.guard()
            current = self.env.get("application", "demo", "argocd")
            compared = (
                current.get("status", {}).get("sync", {}).get("comparedTo", {}).get("source", {})
            )
            if (
                current.get("status", {}).get("sync", {}).get("status") == "Synced"
                and current["status"].get("health", {}).get("status") == "Healthy"
                and compared.get("helm", {}).get("parameters") == expected
            ):
                break
            time.sleep(2)
        else:
            raise TimeoutError("Capacity configuration did not reconcile")
        for kind, name in (
            ("hpa", "demo-api-cpu"),
            ("scaledobject", "demo-worker-lag"),
        ):
            items = self.env.get(kind)["items"]
            for item in items:
                if item["metadata"]["name"] == name:
                    self.state["temporary_controllers"].append(
                        {"kind": kind, "name": name, "uid": item["metadata"]["uid"]}
                    )
        self.env.guard()
        self.load_log = (self.env.output / "capacity-load.jsonl").open("x", encoding="utf-8")
        child_env = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(("AWS_", "GROQ_", "GEMINI_", "OPSPROOF_"))
        }
        child_env.update(M6_RUN_ID=self.env.output.name, M6_LOAD_TARGET="owned-local-forward")
        self.load_process = subprocess.Popen(
            [sys.executable, "-u", "-m", "scripts.m6.capacity_load"],
            cwd=ROOT,
            env=child_env,
            stdout=self.load_log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.state["load_process_pid"] = self.load_process.pid
        self.checkpoint()
        return {
            "mechanism": "GitOps capacity profile plus bounded local generator over owned forward",
            "mode": self.mode,
            "process_pid": self.load_process.pid,
            "protocol": "m6-python-capacity-v3-local",
        }

    def load_logs(self):
        path = (ROOT / self.state["capacity_log_path"]).resolve(strict=True)
        if not path.is_relative_to(ROOT / ".runtime/m6/trials"):
            raise ValueError("Capacity log must belong to the original local trial")
        logs = path.read_text(encoding="utf-8")
        if len(logs) > 2_000_000:
            raise RuntimeError("Capacity receipts exceed the declared bound")
        result = None
        keys, ids = [], []
        for line in logs.splitlines():
            if not line.startswith("{"):
                continue
            row = json.loads(line)
            if row.get("type") == "intent":
                keys.append(row["key"])
            if row.get("type") == "receipt":
                ids.append(str(UUID(row["id"])))
            if row.get("type") == "result":
                result = row
        self.state["submitted_keys"] = keys
        self.state["job_ids"] = ids
        self.env.save("capacity-load-log", {"log": logs})
        self.checkpoint()
        return result

    def observe(self):
        record = self.state["capacity_record"]
        until = time.monotonic() + 420
        result = None
        while time.monotonic() < until:
            self.env.guard()
            api = self.env.get(self.state["api_kind"], "demo-api")
            worker = self.env.get("deployment", "demo-worker")
            sample = {
                "at": utc(),
                "api_replicas": api["spec"]["replicas"],
                "worker_replicas": worker["spec"]["replicas"],
                "api_available": api.get("status", {}).get("availableReplicas", 0),
                "worker_available": worker.get("status", {}).get("availableReplicas", 0),
                "queue": self.env.queue(),
                "resource_metrics": self.env.command(
                    ["top", "pods", "-n", "opsproof-demo", "--no-headers"]
                ).strip(),
            }
            record["samples"].append(sample)
            self.env.save("capacity-sample", sample)
            if self.load_process.poll() is not None:
                result = self.load_logs()
                if self.load_process.returncode != 0:
                    raise RuntimeError("Bounded capacity load failed; raw receipts retained")
            target = "api_replicas" if self.mode == "hpa" else "worker_replicas"
            scaled = self.mode == "fixed" or max(s[target] for s in record["samples"]) > 1
            if result and scaled and sample[target] == 1:
                break
            time.sleep(5)
        if not result or result["http_failures"] or any(j["attempts"] != 1 for j in result["jobs"]):
            raise RuntimeError("Capacity protocol lacks clean exact jobs and measurements")
        if self.mode != "fixed" and not scaled:
            raise RuntimeError("Actual scale-out and scale-in not observed")
        record["workload"] = result
        self.state["observed"] = True
        return {
            "hypothesis_observed": True,
            "capacity_record": record,
            "recovery_attribution": "ordinary fixed/HPA/KEDA capacity, not an OpsProof recovery",
        }

    def cleanup(self):
        original = self.state["original_application"]
        if self.load_process is not None:
            if self.load_process.poll() is None:
                self.load_process.terminate()
                self.load_process.wait(timeout=10)
            self.load_log.close()
            self.load_logs()
            self.state["load_process_stopped"] = True
        current = self.env.get("application", "demo", "argocd")
        original_parameters = original["spec"]["source"]["helm"]["parameters"]
        original_ignore = original["spec"].get("ignoreDifferences", [])
        already_restored = (
            current["spec"]["source"]["helm"]["parameters"] == original_parameters
            and current["spec"].get("ignoreDifferences", []) == original_ignore
        )
        if (
            current["metadata"]["uid"] != original["metadata"]["uid"]
            or not already_restored
            and (
                current["spec"]["source"]["helm"]["parameters"] != self.state["expected_parameters"]
                or current["spec"].get("ignoreDifferences", []) != self.state["expected_ignore"]
            )
        ):
            raise RuntimeError("Capacity source ownership changed; automatic restore refused")
        patch = [
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": current["metadata"]["resourceVersion"],
            },
            {
                "op": "test",
                "path": "/metadata/uid",
                "value": original["metadata"]["uid"],
            },
            {
                "op": "replace",
                "path": "/spec/source/helm/parameters",
                "value": original["spec"]["source"]["helm"]["parameters"],
            },
            {
                "op": "replace",
                "path": "/spec/ignoreDifferences",
                "value": original["spec"].get("ignoreDifferences", []),
            },
        ]
        if not already_restored:
            self.env.command(
                [
                    "patch",
                    "application",
                    "demo",
                    "-n",
                    "argocd",
                    "--type=json",
                    "--patch",
                    json.dumps(patch),
                ]
            )
        until = time.monotonic() + 180
        while time.monotonic() < until:
            app = self.env.get("application", "demo", "argocd")
            status = app.get("status", {})
            compared = status.get("sync", {}).get("comparedTo", {}).get("source", {})
            if (
                compared.get("helm", {}).get("parameters") == original_parameters
                and status.get("operationState", {}).get("phase") != "Running"
            ):
                break
            time.sleep(2)
        else:
            raise TimeoutError("Original capacity source has not reconciled")
        for controller in self.state["temporary_controllers"]:
            delete_exact(
                self.env,
                controller["kind"],
                controller["name"],
                "opsproof-demo",
                controller["uid"],
            )
        worker = self.env.get("deployment", "demo-worker")
        if worker["metadata"]["uid"] != self.state["target_uid"]:
            raise RuntimeError("Worker Deployment identity changed")
        if worker["spec"]["replicas"] != 1:
            patch = [
                {
                    "op": "test",
                    "path": "/metadata/uid",
                    "value": worker["metadata"]["uid"],
                },
                {
                    "op": "test",
                    "path": "/metadata/resourceVersion",
                    "value": worker["metadata"]["resourceVersion"],
                },
                {"op": "replace", "path": "/spec/replicas", "value": 1},
            ]
            self.env.command(
                [
                    "patch",
                    "deployment",
                    "demo-worker",
                    "-n",
                    "opsproof-demo",
                    "--type=json",
                    "--patch",
                    json.dumps(patch),
                ]
            )
        if self.load_process is None and self.state.get("load_process_pid"):
            deadline = time.monotonic() + 330
            while running(self.state["load_process_pid"]) and time.monotonic() < deadline:
                time.sleep(1)
            if running(self.state["load_process_pid"]):
                raise RuntimeError(
                    "Original generator still active; no PID-based kill or reservation release"
                )
            self.load_logs()
        while time.monotonic() < until:
            app = self.env.get("application", "demo", "argocd")
            worker = self.env.get("deployment", "demo-worker")
            status = app.get("status", {})
            if (
                status.get("sync", {}).get("status") == "Synced"
                and status.get("health", {}).get("status") == "Healthy"
                and worker.get("status", {}).get("observedGeneration")
                == worker["metadata"]["generation"]
                and worker.get("status", {}).get("readyReplicas") == 1
                and not self.env.get("hpa")["items"]
                and not self.env.get("scaledobjects")["items"]
            ):
                break
            time.sleep(2)
        else:
            raise TimeoutError("Original healthy fixed-capacity baseline has not returned")
        return {
            "original_source_restored": True,
            "jobs": self.wait_jobs(180, guard=False),
        }
