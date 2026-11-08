"""One bounded comparable fixed/HPA/KEDA trial with real service traffic."""

import argparse
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from uuid import uuid4

from local_cluster import kubectl_prefix
from preflight import ROOT, memory_available


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=("fixed", "hpa", "keda"))
    args = parser.parse_args()
    kube = kubectl_prefix()
    output = ROOT / ".runtime/m5/acceptance"

    def run(command, **kwargs):
        return subprocess.check_output(
            [*kube, *command], text=True, timeout=30, **kwargs
        )

    def get(kind, name=None, ns="opsproof-demo"):
        return json.loads(
            run(["get", kind, *([name] if name else []), "-n", ns, "-o", "json"])
        )

    application = get("application", "demo", "argocd")
    original_parameters = application["spec"]["source"]["helm"]["parameters"]

    def configure(mode):
        parameters = [
            p for p in original_parameters if not p["name"].startswith("autoscaling.")
        ]
        parameters += [
            {"name": "autoscaling.hpa.enabled", "value": str(mode == "hpa").lower()},
            {"name": "autoscaling.keda.enabled", "value": str(mode == "keda").lower()},
        ]
        patch = output / "scaling-application-patch.json"
        patch.write_text(
            json.dumps({"spec": {"source": {"helm": {"parameters": parameters}}}})
        )
        run(
            [
                "patch",
                "application",
                "demo",
                "-n",
                "argocd",
                "--type=merge",
                "--patch-file",
                str(patch),
            ]
        )
        # Automated pruning is disabled to protect data. Explicitly retire only
        # these two trial controllers after they are no longer desired.
        if mode != "hpa":
            run(
                [
                    "delete",
                    "hpa",
                    "demo-api-cpu",
                    "-n",
                    "opsproof-demo",
                    "--ignore-not-found",
                ]
            )
        if mode != "keda":
            run(
                [
                    "delete",
                    "scaledobject",
                    "demo-worker-lag",
                    "-n",
                    "opsproof-demo",
                    "--ignore-not-found",
                ]
            )
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            app = get("application", "demo", "argocd")
            if (
                app.get("status", {}).get("sync", {}).get("status") == "Synced"
                and app["status"].get("health", {}).get("status") == "Healthy"
                and app["status"]["sync"]
                .get("comparedTo", {})
                .get("source", {})
                .get("helm", {})
                .get("parameters")
                == parameters
            ):
                return
            time.sleep(3)
        raise RuntimeError("Autoscaler configuration did not synchronize")

    configure(args.mode)
    drain_deadline = time.monotonic() + 180
    while True:
        groups = json.loads(
            run(
                [
                    "exec",
                    "-n",
                    "opsproof-demo",
                    "demo-deps-redis-0",
                    "--",
                    "redis-cli",
                    "--json",
                    "XINFO",
                    "GROUPS",
                    "opsproof:jobs",
                ]
            )
        )
        group = next(item for item in groups if item["name"] == "opsproof-workers")
        if group["pending"] == 0 and group["lag"] == 0:
            break
        if time.monotonic() >= drain_deadline:
            raise RuntimeError("Previous workload did not drain; trial not started")
        time.sleep(5)
    image = get("deployment", "demo-api")["spec"]["template"]["spec"]["containers"][0][
        "image"
    ]
    name = "m5-capacity-" + args.mode + "-" + uuid4().hex[:8]
    script = (ROOT / "scripts/m5/capacity_load.py").read_text()
    pod = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": name,
            "namespace": "opsproof-control",
            "labels": {
                "app.kubernetes.io/part-of": "opsproof",
                "opsproof.io/trial": "capacity",
            },
        },
        "spec": {
            "terminationGracePeriodSeconds": 5,
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
            "securityContext": {
                "runAsUser": 10001,
                "runAsNonRoot": True,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "load",
                    "image": image,
                    "imagePullPolicy": "IfNotPresent",
                    "command": ["python", "-u", "-c", script],
                    "securityContext": {
                        "readOnlyRootFilesystem": True,
                        "allowPrivilegeEscalation": False,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "64Mi"},
                        "limits": {"cpu": "400m", "memory": "128Mi"},
                    },
                }
            ],
        },
    }
    samples = []
    result = None
    failure = None
    started = time.monotonic()
    try:
        subprocess.run(
            [*kube, "create", "-f", "-"], input=json.dumps(pod), text=True, check=True
        )
        deadline = started + 540
        completed_at = None
        while time.monotonic() < deadline:
            if memory_available() < 1024**3:
                raise RuntimeError(
                    "Capacity trial stopped: host free memory below 1 GiB"
                )
            api = get("deployment", "demo-api")
            worker = get("deployment", "demo-worker")
            hpa = get("hpa")
            groups = json.loads(
                run(
                    [
                        "exec",
                        "-n",
                        "opsproof-demo",
                        "demo-deps-redis-0",
                        "--",
                        "redis-cli",
                        "--json",
                        "XINFO",
                        "GROUPS",
                        "opsproof:jobs",
                    ]
                )
            )
            sample = {
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "api_replicas": api["spec"]["replicas"],
                "worker_replicas": worker["spec"]["replicas"],
                "hpa": hpa["items"],
                "redis_groups": groups,
                "resource_metrics": run(
                    ["top", "pods", "-n", "opsproof-demo", "--no-headers"]
                ).strip(),
            }
            samples.append(sample)
            load = get("pod", name, "opsproof-control")
            phase = load["status"]["phase"]
            if phase in ("Succeeded", "Failed") and completed_at is None:
                log = run(["logs", name, "-n", "opsproof-control"])
                (output / f"scaling-{args.mode}-load.log").write_text(log)
                if phase != "Succeeded":
                    raise RuntimeError("Bounded workload Pod failed; inspect saved log")
                result = next(
                    json.loads(line)
                    for line in log.splitlines()
                    if line.startswith('{"type": "result"')
                )
                completed_at = time.monotonic()
            print(
                args.mode,
                sample["elapsed_seconds"],
                "api",
                sample["api_replicas"],
                "workers",
                sample["worker_replicas"],
                phase,
                flush=True,
            )
            if completed_at is not None:
                target = "api_replicas" if args.mode == "hpa" else "worker_replicas"
                scaled = args.mode == "fixed" or max(s[target] for s in samples) > 1
                if scaled and sample[target] == 1:
                    break
                if time.monotonic() - completed_at > 240:
                    raise RuntimeError(
                        "Scale-out and subsequent scale-in were not both observed"
                    )
            time.sleep(5)
        else:
            raise RuntimeError("Capacity trial overall deadline exceeded")
        if (
            result is None
            or result["http_failures"]
            or any(job["attempts"] != 1 for job in result["jobs"])
        ):
            raise RuntimeError(
                "HTTP failures or unexpected durable job retries observed"
            )
    except Exception as exc:
        failure = str(exc)
        raise
    finally:
        record = {
            "timestamp_utc": datetime.now(UTC).isoformat(),
            "mode": args.mode,
            "passed": failure is None and result is not None,
            "failure": failure,
            "workload": result,
            "samples": samples,
            "trials": 1,
            "load_script_sha256": hashlib.sha256(script.encode()).hexdigest(),
            "application_revision": application.get("status", {})
            .get("sync", {})
            .get("revision"),
        }
        (output / f"scaling-{args.mode}.json").write_text(
            json.dumps(record, indent=2) + "\n"
        )
        run(
            [
                "delete",
                "pod",
                name,
                "-n",
                "opsproof-control",
                "--ignore-not-found",
                "--wait=false",
            ]
        )
        configure("fixed")
    print("PASS:", args.mode, "bounded workload, queue integrity and scale cycle")


if __name__ == "__main__":
    main()
