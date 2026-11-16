"""Start only the preserved local k3d cluster after the original startup gate.

No bootstrap, recreation, default-context command, volume deletion or AWS access.
"""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from scripts.platform.preflight import ROOT
from scripts.reliability.local_environment import resource_preflight, write_json
from scripts.reliability.run_k6_local import local_prefix


def main():
    output = ROOT / ".runtime/m6/acceptance/environment" / ("startup-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    resources = resource_preflight("startup")
    write_json(output / "resources.json", resources)
    if not resources["passed"]:
        print(json.dumps({"status": "BLOCKED", "blockers": resources["blockers"]}, indent=2))
        return 2
    kube = local_prefix(ROOT / ".runtime/m5/kubeconfig.yaml")
    default_config = Path.home() / ".kube/config"
    before = (
        hashlib.sha256(default_config.read_bytes()).hexdigest() if default_config.exists() else None
    )
    clusters = json.loads(
        subprocess.check_output(["k3d", "cluster", "list", "-o", "json"], text=True)
    )
    cluster = next((item for item in clusters if item["name"] == "opsproof"), None)
    if cluster is None:
        raise RuntimeError("Preserved local cluster is missing; automatic recreation is forbidden")
    subprocess.run(["k3d", "cluster", "start", "opsproof"], check=True, timeout=180)
    subprocess.run(
        [*kube, "wait", "--for=condition=Ready", "nodes", "--all", "--timeout=180s"],
        check=True,
        timeout=190,
    )
    subprocess.run(
        [sys.executable, "-m", "scripts.reliability.refresh_api_allowlists", "--apply"],
        check=True,
        timeout=60,
    )
    for _ in range(60):
        pods = json.loads(
            subprocess.check_output(
                [*kube, "get", "pods", "-A", "-o", "json"], text=True, timeout=20
            )
        )
        active = [p for p in pods["items"] if p["status"].get("phase") != "Succeeded"]
        if active and all(
            p["status"].get("phase") == "Running"
            and all(c.get("ready") for c in p["status"].get("containerStatuses", [{}]))
            for p in active
        ):
            break
        time.sleep(3)
    pvcs = json.loads(
        subprocess.check_output([*kube, "get", "pvc", "-A", "-o", "json"], text=True, timeout=20)
    )
    historical = json.loads((ROOT / ".runtime/m5/acceptance/final-state.json").read_text())
    expected = {(p["namespace"], p["name"]): p["uid"] for p in historical["pvcs"]}
    actual = {
        (p["metadata"]["namespace"], p["metadata"]["name"]): p["metadata"]["uid"]
        for p in pvcs["items"]
    }
    preserved = all(actual.get(key) == identity for key, identity in expected.items())
    after = (
        hashlib.sha256(default_config.read_bytes()).hexdigest() if default_config.exists() else None
    )
    report = {
        "existing_pvcs_preserved": preserved,
        "pvc_count": len(actual),
        "default_kubeconfig_unchanged": before == after,
        "pods": [
            {
                "namespace": p["metadata"]["namespace"],
                "name": p["metadata"]["name"],
                "uid": p["metadata"]["uid"],
                "phase": p["status"].get("phase"),
                "images": [
                    {
                        "image": c["image"],
                        "image_id": c.get("imageID"),
                        "ready": c.get("ready"),
                    }
                    for c in p["status"].get("containerStatuses", [])
                ],
            }
            for p in pods["items"]
        ],
    }
    report["all_existing_pods_ready"] = bool(active) and all(
        p["status"].get("phase") == "Running"
        and all(c.get("ready") for c in p["status"].get("containerStatuses", [{}]))
        for p in active
    )
    write_json(output / "result.json", report)
    if not preserved or before != after:
        raise RuntimeError("M5 persistent identity or default kubeconfig preservation failed")
    if not report["all_existing_pods_ready"]:
        raise RuntimeError(
            "Existing Pods are not all Ready; inspect startup evidence before trials"
        )
    print("Preserved cluster started; PVCs and default kubeconfig verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
