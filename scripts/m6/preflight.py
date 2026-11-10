"""Read-only M6 Kubernetes identity and resource preflight.

Never falls back to the user's default KUBECONFIG (which may target EKS).
No resource creation or mutation. Uses only explicit local k3d context.
"""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

if __package__:
    from .contracts import assert_local_scope, assert_isolated_k3d_api
else:
    from contracts import assert_local_scope, assert_isolated_k3d_api


def inspect(kubeconfig: Path) -> dict:
    kubeconfig = kubeconfig.resolve(strict=True)
    prefix = ["kubectl", "--kubeconfig", str(kubeconfig), "--context", "k3d-opsproof"]

    def call(args):
        proc = subprocess.run([*prefix, *args], capture_output=True, text=True, timeout=20,
                              check=False)
        if proc.returncode:
            raise RuntimeError(f"kubectl {' '.join(args[:2])} failed (code {proc.returncode})")
        return proc.stdout

    local_config = json.loads(call(["config", "view", "--minify", "-o", "json"]))
    assert_isolated_k3d_api(local_config["clusters"][0]["cluster"]["server"])
    context = call(["config", "current-context"]).strip()
    if context != "k3d-opsproof":
        raise ValueError("Unexpected kubeconfig default context")
    nodes = json.loads(call(["get", "nodes", "-o", "json"]))
    if not nodes.get("items"):
        raise RuntimeError("Cluster has no nodes")
    ready = [any(c.get("type") == "Ready" and c.get("status") == "True"
                 for c in node.get("status", {}).get("conditions", []))
             for node in nodes["items"]]
    if not all(ready):
        raise RuntimeError("At least one local node is NotReady")
    namespaces = json.loads(call(["get", "namespaces", "-o", "json"]))
    names = {item["metadata"]["name"] for item in namespaces["items"]}
    if not {"opsproof-demo", "opsproof-control"}.issubset(names):
        raise RuntimeError("Missing required OpsProof namespaces")
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "context": context,
        "kubeconfig_path": "<local-explicit-k3d-config>",
        "node_count": len(nodes["items"]),
        "nodes_ready": all(ready),
        "required_namespaces_present": True,
        "limitations": "Read-only cluster identity check; not a recovery or GitOps acceptance test",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", type=Path, default=Path(".runtime/m5/kubeconfig.yaml"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert_local_scope(kubeconfig=args.kubeconfig, context="k3d-opsproof", mutation=False)
    report = inspect(args.kubeconfig)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
