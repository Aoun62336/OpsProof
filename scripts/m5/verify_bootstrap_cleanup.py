"""Test a disposable empty cluster, preserving and restarting the real M5 cluster."""

import hashlib
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import yaml
from local_cluster import kubectl_prefix
from preflight import ROOT, memory_available


def main():
    kube = kubectl_prefix()
    name = "opsproof-cleanup-" + uuid4().hex[:8]
    output = ROOT / ".runtime/m5/acceptance/bootstrap-cleanup.json"
    default_config = Path.home() / ".kube/config"
    default_hash = (
        hashlib.sha256(default_config.read_bytes()).hexdigest()
        if default_config.exists()
        else None
    )

    def run(args, **kwargs):
        return subprocess.check_output(args, text=True, timeout=240, **kwargs)

    def pvcs():
        return {
            p["metadata"]["namespace"] + "/" + p["metadata"]["name"]: p["metadata"][
                "uid"
            ]
            for p in json.loads(run([*kube, "get", "pvc", "-A", "-o", "json"]))["items"]
        }

    before = pvcs()
    record = {
        "passed": False,
        "disposable_cluster": name,
        "preserved_cluster": "opsproof",
        "pvc_uids_before": before,
    }
    config = yaml.safe_load((ROOT / "infra/k3d/cluster.yaml").read_text())
    config["metadata"]["name"] = name
    config["kubeAPI"]["hostPort"] = "6552"
    config.pop("ports", None)
    path = ROOT / ".runtime/m5/cleanup-cluster.yaml"
    path.write_text(yaml.safe_dump(config))
    created = False
    stopped = False
    try:
        if any(
            c["name"] == name
            for c in json.loads(run(["k3d", "cluster", "list", "-o", "json"]))
        ):
            raise RuntimeError("Disposable cluster name already exists")
        run(["k3d", "cluster", "stop", "opsproof"])
        stopped = True
        subprocess.run(
            [
                "wsl",
                "-d",
                "docker-desktop",
                "-u",
                "root",
                "--",
                "sh",
                "-c",
                "sync; echo 3 > /proc/sys/vm/drop_caches",
            ],
            check=True,
            timeout=15,
        )
        deadline = time.monotonic() + 45
        while memory_available() < 5 * 1024**3 and time.monotonic() < deadline:
            time.sleep(3)
        record["bootstrap_host_free_bytes"] = memory_available()
        if record["bootstrap_host_free_bytes"] < 5 * 1024**3:
            raise RuntimeError(
                "Disposable bootstrap did not pass the unchanged 5 GiB memory gate"
            )
        print("Resource gate passed; creating disposable empty cluster", flush=True)
        created = True  # also clean a partial create, but only this generated name
        record["create_output"] = run(
            ["k3d", "cluster", "create", "--config", str(path)]
        )
        cfg = ROOT / ".runtime/m5/cleanup-kubeconfig.yaml"
        cfg.write_text(run(["k3d", "kubeconfig", "get", name]))
        test_kube = ["kubectl", "--kubeconfig", str(cfg), "--context", "k3d-" + name]
        run(
            [
                *test_kube,
                "wait",
                "node",
                "--all",
                "--for=condition=Ready",
                "--timeout=120s",
            ]
        )
        record["nodes"] = [
            {
                "name": node["metadata"]["name"],
                "uid": node["metadata"]["uid"],
                "kubelet_version": node["status"]["nodeInfo"]["kubeletVersion"],
                "conditions": node["status"]["conditions"],
            }
            for node in json.loads(run([*test_kube, "get", "nodes", "-o", "json"]))[
                "items"
            ]
        ]
        if json.loads(run([*test_kube, "get", "pvc", "-A", "-o", "json"]))["items"]:
            raise RuntimeError(
                "Disposable cluster unexpectedly contains persistent claims"
            )
        record["empty_cluster_verified"] = True
    finally:
        if created:
            # The real cluster name can never enter this deletion path.
            if not name.startswith("opsproof-cleanup-") or name == "opsproof":
                raise RuntimeError("Unsafe cleanup target")
            record["delete_output"] = run(["k3d", "cluster", "delete", name])
            record["deleted"] = not any(
                c["name"] == name
                for c in json.loads(run(["k3d", "cluster", "list", "-o", "json"]))
            )
        if stopped:
            print("Restarting preserved OpsProof cluster", flush=True)
            run(["k3d", "cluster", "start", "opsproof"])
            run(
                [
                    *kube,
                    "wait",
                    "node",
                    "--all",
                    "--for=condition=Ready",
                    "--timeout=120s",
                ]
            )
            for ns, deployment in (
                ("opsproof-control", "control-api"),
                ("opsproof-demo", "demo-worker"),
                ("opsproof-ui", "opsproof-web"),
            ):
                run(
                    [
                        *kube,
                        "rollout",
                        "status",
                        "deployment/" + deployment,
                        "-n",
                        ns,
                        "--timeout=180s",
                    ]
                )
            record["pvc_uids_after"] = pvcs()
        current_hash = (
            hashlib.sha256(default_config.read_bytes()).hexdigest()
            if default_config.exists()
            else None
        )
        record["default_kubeconfig_unchanged"] = current_hash == default_hash
        record["passed"] = bool(
            record.get("empty_cluster_verified")
            and record.get("deleted")
            and record.get("pvc_uids_after") == before
            and record["default_kubeconfig_unchanged"]
        )
        output.write_text(json.dumps(record, indent=2) + "\n")
    if not record["passed"]:
        raise RuntimeError("Bootstrap/cleanup acceptance failed; inspect evidence")
    print(
        "PASS: disposable bootstrap and cleanup; original cluster and all PVC identities preserved"
    )


if __name__ == "__main__":
    main()
