"""Temporarily pause exactly two noncritical UIs; preserve and restore their state.

No controller, telemetry collector, database, credential or resource limit changes.
Both targets are existing Helm/manual resources, outside Argo application ownership.
"""

import argparse
import hashlib
import json
import subprocess
from uuid import uuid4

from scripts.m5.preflight import ROOT
from scripts.m6.local_environment import LocalEnvironment, utc, write_json

TARGETS = (("opsproof-observability", "grafana"), ("argocd", "argocd-server"))
POINTER = ROOT / ".runtime/m6/acceptance/ui-test-profile.json"


def template_hash(deployment):
    return hashlib.sha256(
        json.dumps(deployment["spec"]["template"], sort_keys=True).encode()
    ).hexdigest()


def save_pointer(record):
    POINTER.parent.mkdir(parents=True, exist_ok=True)
    POINTER.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("enter", "restore"))
    parser.add_argument(
        "--stop-cluster",
        action="store_true",
        help="Restore desired UI state and immediately stop the owned test cluster",
    )
    args = parser.parse_args()
    directory = ROOT / ".runtime/m6/acceptance/environment" / ("ui-profile-" + uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    env = LocalEnvironment(directory)
    if args.action == "enter":
        if POINTER.exists() and json.loads(POINTER.read_text())["active"]:
            raise RuntimeError("An existing UI profile must be restored first")
        record = {"active": True, "entered_at": utc(), "targets": []}
        for namespace, name in TARGETS:
            current = env.get("deployment", name, namespace)
            if (
                current["spec"].get("replicas") != 1
                or current.get("status", {}).get("readyReplicas") != 1
            ):
                raise RuntimeError("Both UIs must be healthy with one replica before pausing")
            if any("argocd" in key for key in current["metadata"].get("annotations", {})):
                raise RuntimeError("Refusing to change an Argo-owned UI outside its source")
            record["targets"].append(
                {
                    "namespace": namespace,
                    "name": name,
                    "uid": current["metadata"]["uid"],
                    "replicas": 1,
                    "template_sha256": template_hash(current),
                    "resources": current["spec"]["template"]["spec"]["containers"][0]["resources"],
                }
            )
        save_pointer(record)  # Persist original state before either PATCH.
        for item in record["targets"]:
            current = env.get("deployment", item["name"], item["namespace"])
            if (
                current["metadata"]["uid"] != item["uid"]
                or template_hash(current) != item["template_sha256"]
            ):
                raise RuntimeError("UI identity changed before entering profile")
            env.patch(
                "deployment",
                item["name"],
                current,
                [{"op": "replace", "path": "/spec/replicas", "value": 0}],
                item["namespace"],
            )
    else:
        record = json.loads(POINTER.read_text(encoding="utf-8"))
        for item in record["targets"]:
            if (item["namespace"], item["name"]) not in TARGETS:
                raise ValueError("UI profile contains an unsupported target")
            current = env.get("deployment", item["name"], item["namespace"])
            if (
                current["metadata"]["uid"] != item["uid"]
                or template_hash(current) != item["template_sha256"]
            ):
                raise RuntimeError("UI identity/template changed; automatic restore refused")
            replicas = current["spec"].get("replicas")
            if replicas not in (0, item["replicas"]):
                raise RuntimeError("UI replica ownership changed")
            if replicas == 0:
                patch = [
                    {"op": "test", "path": "/metadata/uid", "value": item["uid"]},
                    {
                        "op": "test",
                        "path": "/metadata/resourceVersion",
                        "value": current["metadata"]["resourceVersion"],
                    },
                    {
                        "op": "replace",
                        "path": "/spec/replicas",
                        "value": item["replicas"],
                    },
                ]
                env.command(
                    [
                        "patch",
                        "deployment",
                        item["name"],
                        "-n",
                        item["namespace"],
                        "--type=json",
                        "--patch",
                        json.dumps(patch),
                    ]
                )
            if args.stop_cluster:
                continue
            subprocess.run(
                [
                    *env.kube,
                    "rollout",
                    "status",
                    "deployment/" + item["name"],
                    "-n",
                    item["namespace"],
                    "--timeout=45s",
                ],
                check=True,
                timeout=50,
            )
        if args.stop_cluster:
            subprocess.run(["k3d", "cluster", "stop", "opsproof"], check=True, timeout=120)
        record.update(
            active=False,
            restored_at=utc(),
            cluster_stopped=args.stop_cluster,
            readiness_verified=not args.stop_cluster,
        )
        save_pointer(record)
    write_json(directory / "result.json", record)
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
