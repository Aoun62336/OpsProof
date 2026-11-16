"""Prepare Argo CD's four-namespace boundary without bearer tokens or cluster grants."""

import argparse
import json
from pathlib import Path

from scripts.platform.gitops_permissions import permissions

NAMESPACES = ("opsproof-demo", "opsproof-control", "opsproof-ui", "opsproof-edge")


def build() -> dict:
    cluster = {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "Opaque",
        "metadata": {
            "name": "opsproof-cloud-cluster",
            "namespace": "argocd",
            "labels": {"argocd.argoproj.io/secret-type": "cluster"},
        },
        "stringData": {
            "name": "opsproof-cloud",
            "server": "https://kubernetes.default.svc",
            "namespaces": ",".join(NAMESPACES),
            "clusterResources": "false",
            "config": "{}",
        },
    }
    return {
        "apiVersion": "v1",
        "kind": "List",
        "items": [*permissions(NAMESPACES, cloud=True), cluster],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(build(), indent=2) + "\n", encoding="utf-8")
    print("NAMESPACED_ARGO_PERMISSIONS_RENDERED; no credentials or cluster write grants")


if __name__ == "__main__":
    main()
