"""Live fixed-target RBAC and projected credential boundary checks."""

import json
import subprocess

from scripts.platform.local_cluster import kubectl_prefix
from scripts.platform.preflight import ROOT


def main():
    kube = kubectl_prefix()
    checks = []
    for role, verb, resource, expected in [
        ("action", "get", "deployment/demo-worker", True),
        ("action", "patch", "deployment/demo-worker", True),
        ("action", "patch", "deployment/demo-api", False),
        ("evidence", "get", "deployment/demo-worker", True),
        ("evidence", "patch", "deployment/demo-worker", False),
        ("api", "get", "deployment/demo-worker", False),
        ("api", "patch", "deployment/demo-worker", False),
        *[
            (role, verb, resource, False)
            for role in ("api", "action", "evidence")
            for verb, resource in (
                ("get", "secrets"),
                ("create", "pods/exec"),
                ("create", "jobs"),
                ("create", "rolebindings"),
            )
        ],
    ]:
        command = [
            *kube,
            "auth",
            "can-i",
            verb,
            resource,
            "-n",
            "opsproof-demo",
            "--as",
            "system:serviceaccount:opsproof-control:control-" + role,
        ]
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        actual = result.stdout.strip() == "yes"
        checks.append(
            {
                "role": role,
                "verb": verb,
                "resource": resource,
                "expected": expected,
                "actual": actual,
            }
        )
        if actual != expected or result.returncode not in (0, 1):
            raise RuntimeError("RBAC boundary failed: " + str(checks[-1]))
    for role in ("api", "action", "evidence", "dispatch"):
        obj = json.loads(
            subprocess.check_output(
                [
                    *kube,
                    "get",
                    "deployment",
                    "control-" + role,
                    "-n",
                    "opsproof-control",
                    "-o",
                    "json",
                ],
                text=True,
            )
        )
        pod = obj["spec"]["template"]["spec"]
        mounted = any(v["name"] == "kubernetes-identity" for v in pod.get("volumes", []))
        if (
            mounted != (role in ("action", "evidence"))
            or pod.get("automountServiceAccountToken") is not False
        ):
            raise RuntimeError("Credential mounting boundary failed")
        checks.append({"role": role, "projected_token": mounted, "automount": False})
    (ROOT / ".runtime/platform/acceptance/kubernetes-rbac.json").write_text(
        json.dumps({"passed": True, "checks": checks}, indent=2)
    )
    print("PASS:", len(checks), "live RBAC and credential boundary checks")


if __name__ == "__main__":
    main()
