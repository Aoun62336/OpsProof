"""Read-only verification of a second workload Kubernetes identity/status.

This does not fabricate incident detection or imply its recovery is authorized.
The second target is intentionally separate from demo/control namespaces.
"""
import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.m6.contracts import assert_isolated_k3d_api, assert_local_scope


def inspect(config: Path) -> dict:
    config = config.resolve(strict=True)
    assert_local_scope(kubeconfig=config, context="k3d-opsproof", mutation=False)
    base = ["kubectl", "--kubeconfig", str(config), "--context", "k3d-opsproof"]

    def get(*args):
        proc = subprocess.run([*base, *args], text=True, capture_output=True, timeout=20, check=False)
        if proc.returncode:
            raise RuntimeError("Read-only reuse resource inspection failed")
        return json.loads(proc.stdout)

    view = get("config", "view", "--minify", "-o", "json")
    assert_isolated_k3d_api(view["clusters"][0]["cluster"]["server"])
    target = get("get", "deploy", "reuse-target", "-n", "opsproof-reuse-test", "-o", "json")
    metadata = target["metadata"]
    if metadata["namespace"] != "opsproof-reuse-test" or metadata["name"] != "reuse-target":
        raise ValueError("Unexpected reuse target resource")
    ready = target.get("status", {}).get("readyReplicas", 0)
    desired = target["spec"]["replicas"]
    endpoints = get("get", "endpointslices", "-n", "opsproof-reuse-test", "-o", "json")
    return {
        "observed_utc": datetime.now(UTC).isoformat(),
        "target": "opsproof-reuse-test",
        "resource_uid": metadata["uid"],
        "resource_version": metadata["resourceVersion"],
        "desired_replicas": desired,
        "ready_replicas": ready,
        "endpointslice_count": len(endpoints.get("items", [])),
        "observation_only": True,
        "recovery_authorized": False,
        "limitations": "Kubernetes readiness metadata alone does not verify application or diagnosis reuse",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.kubeconfig)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Read-only reuse target observation written. No recovery authority.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
