"""Sequentially adopt existing foundation releases into local Argo CD ownership.

Retains Helm history and PVCs. Do not subsequently helm-upgrade these five releases.
"""

import json
import subprocess
import time
from datetime import UTC, datetime

from local_cluster import kubectl_prefix
from preflight import ROOT
from render_gitops import LOCAL_REPO, render


def main():
    kube = kubectl_prefix()
    provenance = json.loads(
        (ROOT / ".runtime/m5/acceptance/gitops-images.json").read_text()
    )
    objects = render(
        LOCAL_REPO, provenance["revision"], provenance["tag"], allow_local=True
    )["items"]
    history = []
    for obj in objects:
        subprocess.run(
            [*kube, "apply", "-f", "-"], input=json.dumps(obj), text=True, check=True
        )
        if obj["kind"] != "Application":
            continue
        name = obj["metadata"]["name"]
        deadline = time.monotonic() + 360
        previous = None
        while time.monotonic() < deadline:
            live = json.loads(
                subprocess.check_output(
                    [*kube, "get", "application", name, "-n", "argocd", "-o", "json"],
                    text=True,
                )
            )
            status = live.get("status", {})
            state = (
                status.get("sync", {}).get("status"),
                status.get("health", {}).get("status"),
                status.get("operationState", {}).get("phase"),
            )
            if state != previous:
                print(name, state, flush=True)
                previous = state
            if (
                state[0:2] == ("Synced", "Healthy")
                and status["sync"].get("revision") == provenance["revision"]
            ):
                history.append({"name": name, "status": status})
                break
            time.sleep(3)
        else:
            raise RuntimeError(f"Argo adoption deadline exceeded for {name}")
    record = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "repository": LOCAL_REPO,
        "revision": provenance["revision"],
        "applications": history,
        "ownership": "Argo CD; Helm release histories retained but manual upgrades retired",
    }
    (ROOT / ".runtime/m5/acceptance/gitops-adoption.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    print("PASS: five applications Synced/Healthy at the exact local Git revision")


if __name__ == "__main__":
    main()
