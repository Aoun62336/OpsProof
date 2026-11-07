"""Actual Helm rendering and offline security/ownership contract checks.

Requires Helm and PyYAML. This is not API-server schema or live policy validation.
"""

import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(objects):
    for obj in objects:
        kind = obj["kind"]
        name = obj["metadata"]["name"]
        require(
            kind
            not in (
                "Secret",
                "ClusterRole",
                "ClusterRoleBinding",
                "Role",
                "RoleBinding",
            ),
            f"Unexpected credential or permission resource: {name}",
        )
        if kind == "Service":
            require(
                obj["spec"].get("type", "ClusterIP") == "ClusterIP",
                f"Public service: {name}",
            )
        if kind not in ("Deployment", "StatefulSet", "Job"):
            continue
        pod = obj["spec"]["template"]["spec"]
        require(
            pod.get("automountServiceAccountToken") is False,
            f"API token mounted: {name}",
        )
        security = pod["securityContext"]
        require(
            security["runAsNonRoot"] and security["runAsUser"] > 0, f"Root Pod: {name}"
        )
        require(
            security["seccompProfile"]["type"] == "RuntimeDefault",
            f"Seccomp missing: {name}",
        )
        for container in pod["containers"]:
            sec = container["securityContext"]
            require(
                sec["allowPrivilegeEscalation"] is False
                and "ALL" in sec["capabilities"]["drop"],
                f"Container privileges: {name}",
            )
            require(
                container["resources"].get("requests")
                and container["resources"].get("limits"),
                f"Unbounded resources: {name}",
            )
            require(
                not container["image"].endswith(":latest"),
                f"Mutable latest image: {name}",
            )
            refs = {item["secretRef"]["name"] for item in container.get("envFrom", [])}
            if name.endswith(("-dispatch", "-worker", "-migrate")):
                require(
                    not any(
                        ref.endswith(
                            ("-operator", "-inspection", "-recovery", "-alert")
                        )
                        for ref in refs
                    ),
                    f"Excess role credentials: {name}",
                )


def main():
    tag = ["--set-string", "image.tag=m5-000000000000"]
    services = "infra/helm/opsproof-services"
    scenarios = [
        ("demo-deps", "infra/helm/opsproof-dependencies", []),
        ("control-deps", "infra/helm/opsproof-dependencies", []),
        ("demo", services, ["-f", services + "/values-demo.yaml", *tag]),
        ("control", services, ["-f", services + "/values-control.yaml", *tag]),
        ("web", "infra/helm/opsproof-web", tag),
        (
            "demo",
            services,
            [
                "-f",
                services + "/values-demo.yaml",
                *tag,
                "--set",
                "autoscaling.hpa.enabled=true,autoscaling.keda.enabled=true",
            ],
        ),
        (
            "control",
            services,
            [
                "-f",
                services + "/values-control.yaml",
                *tag,
                "--set",
                "telemetry.enabled=true,recoveryEnabled=true",
            ],
        ),
    ]
    summaries = []
    for name, chart, args in scenarios:
        subprocess.run(["helm", "lint", chart, *args], cwd=ROOT, check=True)
        result = subprocess.run(
            ["helm", "template", name, chart, *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        objects = [obj for obj in yaml.safe_load_all(result.stdout) if obj]
        validate(objects)
        if any(obj["kind"] == "ScaledObject" for obj in objects):
            deployments = {
                obj["metadata"]["name"]: obj
                for obj in objects
                if obj["kind"] == "Deployment"
            }
            for role in ("api", "worker"):
                require(
                    "replicas" not in deployments[f"demo-{role}"]["spec"],
                    "Autoscaler ownership conflict",
                )
            scaled = next(obj for obj in objects if obj["kind"] == "ScaledObject")
            metrics = [trigger["metadata"] for trigger in scaled["spec"]["triggers"]]
            require(
                any("lagCount" in metric for metric in metrics)
                and any("pendingEntriesCount" in metric for metric in metrics),
                "Missing queue metric",
            )
        summaries.append(
            {
                "release": name,
                "arguments": args,
                "objects": len(objects),
                "passed": True,
            }
        )
    output = ROOT / ".runtime/m5/acceptance/chart-contracts.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
    print(
        f"PASS: {len(scenarios)} render configurations; {sum(s['objects'] for s in summaries)} objects"
    )


if __name__ == "__main__":
    main()
