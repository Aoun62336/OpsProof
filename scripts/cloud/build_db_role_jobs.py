"""Emit two private-identity, single-use EKS Jobs (bootstrap + verify).

All credentials are SecretKeyRefs. The only master user consumer is the bootstrap
Job. Image must be a real signed-off immutable control image digest.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

IMAGE_RE = re.compile(r"^ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.\-/]+@sha256:[0-9a-f]{64}$")


def build(image: str, mode: str) -> dict:
    if not IMAGE_RE.fullmatch(image):
        raise ValueError("immutable GHCR image required")
    if mode not in ("bootstrap", "verify"):
        raise ValueError("mode must be bootstrap/verify")
    name = f"opsproof-cloud-rds-{mode}"
    secret = (
        "opsproof-control-rds-bootstrap"
        if mode == "bootstrap"
        else "opsproof-control-rds-role-verifier"
    )
    container = {
        "name": "roles",
        "image": image,
        "imagePullPolicy": "IfNotPresent",
        "command": ["python", "-m", "opsproof_control.db_bootstrap"],
        "args": ["--mode", mode],
        "envFrom": [{"secretRef": {"name": secret}}],
        "volumeMounts": [
            {"name": "rds-ca", "mountPath": "/etc/opsproof/rds-ca", "readOnly": True},
            {"name": "tmp", "mountPath": "/tmp"},
        ],
        "securityContext": {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
        "resources": {
            "requests": {"cpu": "50m", "memory": "64Mi"},
            "limits": {"cpu": "250m", "memory": "256Mi"},
        },
    }
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": "opsproof-control",
            "labels": {
                "app.kubernetes.io/part-of": "opsproof",
                "opsproof.io/role": "database-bootstrap",
            },
        },
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": 180,
            "ttlSecondsAfterFinished": 1800,
            "template": {
                "metadata": {"labels": {"opsproof.io/role": "database-bootstrap"}},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    "containers": [container],
                    "volumes": [
                        {"name": "rds-ca", "configMap": {"name": "opsproof-rds-ca"}},
                        {"name": "tmp", "emptyDir": {"sizeLimit": "16Mi"}},
                    ],
                },
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--mode", choices=["bootstrap", "verify"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    obj = build(args.image, args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    print(f"CREATED_JOB_{args.mode.upper()} (no credentials embedded)")


if __name__ == "__main__":
    main()
