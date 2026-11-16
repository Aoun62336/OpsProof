"""Live local RBAC, restricted admission and NetworkPolicy boundary checks."""

import json
import subprocess
import time
from datetime import UTC, datetime

from local_cluster import kubectl_prefix
from preflight import ROOT


def main():
    kube = kubectl_prefix()
    results = []

    def run(args, **kwargs):
        return subprocess.run(
            [*kube, *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            **kwargs,
        )

    for namespace, accounts in (
        ("opsproof-demo", ("demo-api", "demo-dispatch", "demo-worker")),
        (
            "opsproof-control",
            ("control-api", "control-dispatch", "control-action", "control-evidence"),
        ),
    ):
        for account in accounts:
            for verb, resource in (
                ("get", "secrets"),
                ("patch", "deployments"),
                ("create", "jobs"),
            ):
                result = run(
                    [
                        "auth",
                        "can-i",
                        verb,
                        resource,
                        "-n",
                        namespace,
                        "--as",
                        f"system:serviceaccount:{namespace}:{account}",
                    ]
                )
                if result.returncode != 1 or result.stdout.strip() != "no":
                    raise RuntimeError(f"Expected RBAC denial for {account} {verb} {resource}")
                results.append(
                    {
                        "account": account,
                        "verb": verb,
                        "resource": resource,
                        "allowed": False,
                    }
                )
    invalid = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "m5-admission-negative", "namespace": "opsproof-demo"},
        "spec": {
            "containers": [
                {
                    "name": "invalid",
                    "image": "busybox:1.37",
                    "securityContext": {"privileged": True},
                }
            ]
        },
    }
    rejected = run(["apply", "--dry-run=server", "-f", "-"], input=json.dumps(invalid))
    if rejected.returncode == 0 or "violates PodSecurity" not in rejected.stderr:
        raise RuntimeError("Restricted Pod admission not proven")
    results.append({"check": "privileged Pod server-side dry-run", "rejected": True})

    def connection(host, port):
        code = (
            "import socket,json; "
            f"address=socket.gethostbyname({host!r}); "
            "sock=socket.socket(); sock.settimeout(3); "
            f"result=sock.connect_ex((address,{port})); "
            "print(json.dumps({'connected':result==0,'errno':result})); sock.close()"
        )
        result = run(
            [
                "exec",
                "-n",
                "opsproof-control",
                "deploy/control-api",
                "--",
                "python",
                "-c",
                code,
            ]
        )
        if result.returncode:
            raise RuntimeError("Network probe execution or DNS failed")
        return json.loads(result.stdout)

    foreign_db = "demo-deps-postgres.opsproof-demo.svc.cluster.local"
    before = connection(foreign_db, 5432)
    installed = run(["apply", "-f", str(ROOT / "infra/k8s/network-policies.yaml")])
    if installed.returncode:
        raise RuntimeError("NetworkPolicy install failed")
    deadline = time.monotonic() + 30
    while True:
        after = connection(foreign_db, 5432)
        if not after["connected"]:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("Cross-namespace PostgreSQL remained reachable")
        time.sleep(1)
    for host, port in (
        ("control-deps-postgres.opsproof-control.svc.cluster.local", 5432),
        ("control-deps-redis.opsproof-control.svc.cluster.local", 6379),
        ("demo-api.opsproof-demo.svc.cluster.local", 8080),
    ):
        if not connection(host, port)["connected"]:
            raise RuntimeError("Required application connection blocked")
        results.append({"host": host, "port": port, "connected": True})
    results.append(
        {
            "check": "foreign database denied",
            "before_policy": before,
            "after_policy": after,
        }
    )
    out = ROOT / ".runtime/m5/acceptance/k8s-foundation-security.json"
    out.write_text(
        json.dumps(
            {
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "passed": True,
                "scope": "foundation boundaries, not new Kubernetes recovery authorization",
                "checks": results,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"PASS: {len(results)} live foundation security checks")


if __name__ == "__main__":
    main()
