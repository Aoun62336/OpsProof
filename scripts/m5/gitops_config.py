"""Change local Application parameters and wait for observed source reconciliation."""

import json
import subprocess
import time

from local_cluster import kubectl_prefix
from preflight import ROOT


def configure(name, values, revision=None, extra_spec=None, wait=True):
    if name not in ("demo", "control", "web"):
        raise ValueError("Unsupported local application")
    kube = kubectl_prefix()

    def get():
        return json.loads(
            subprocess.check_output(
                [*kube, "get", "application", name, "-n", "argocd", "-o", "json"],
                text=True,
            )
        )

    app = get()
    parameters = {
        p["name"]: p["value"] for p in app["spec"]["source"]["helm"]["parameters"]
    }
    parameters.update(
        {
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in values.items()
        }
    )
    params = [{"name": key, "value": value} for key, value in parameters.items()]
    source = {"helm": {"parameters": params}}
    if revision:
        source["targetRevision"] = revision
    patch = ROOT / f".runtime/m5/{name}-configuration-patch.json"
    patch.write_text(json.dumps({"spec": {"source": source, **(extra_spec or {})}}))
    subprocess.run(
        [
            *kube,
            "patch",
            "application",
            name,
            "-n",
            "argocd",
            "--type=merge",
            "--patch-file",
            str(patch),
        ],
        check=True,
    )
    if not wait:
        return
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        app = get()
        sync = app.get("status", {}).get("sync", {})
        compared = sync.get("comparedTo", {}).get("source", {})
        if (
            compared.get("helm", {}).get("parameters") == params
            and sync.get("status") == "Synced"
            and (not revision or sync.get("revision") == revision)
            and app["status"].get("health", {}).get("status") == "Healthy"
        ):
            print("Observed Synced/Healthy:", name)
            return
        time.sleep(3)
    raise RuntimeError("Application did not become Synced/Healthy: " + name)
