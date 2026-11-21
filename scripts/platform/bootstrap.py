"""Create only the local opsproof cluster after a passing resource gate.

Does not delete clusters, stop Compose, or change the user's default kubeconfig.
"""

import json
import subprocess

from scripts.platform.preflight import ROOT
from scripts.platform.preflight import main as preflight


def main():
    if preflight() != 0:
        raise SystemExit("Bootstrap blocked by measured resource/tool gate")
    result = subprocess.run(
        ["k3d", "cluster", "list", "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    if any(cluster["name"] == "opsproof" for cluster in json.loads(result.stdout)):
        raise SystemExit("Existing opsproof cluster requires inspection; not recreating it")
    subprocess.run(
        ["k3d", "cluster", "create", "--config", str(ROOT / "infra/k3d/cluster.yaml")],
        check=True,
    )
    result = subprocess.run(
        ["k3d", "kubeconfig", "get", "opsproof"],
        capture_output=True,
        text=True,
        check=True,
    )
    target = ROOT / ".runtime/platform/kubeconfig.yaml"
    target.write_text(result.stdout, encoding="utf-8")
    subprocess.run(
        [
            "kubectl",
            "--kubeconfig",
            str(target),
            "--context",
            "k3d-opsproof",
            "wait",
            "--for=condition=Ready",
            "node",
            "--all",
            "--timeout=120s",
        ],
        check=True,
    )
    print("Local cluster Ready; use .runtime/platform/kubeconfig.yaml explicitly")


if __name__ == "__main__":
    main()
