"""Native cloud Helm lint/render and semantic safety checks; no cluster access."""

import json
import subprocess
from pathlib import Path
from uuid import uuid4

import yaml

from scripts.cloud.install_controllers import filename, loaded, verify
from scripts.platform.validate_charts import validate

ROOT = Path(__file__).resolve().parents[2]
DIGEST = "sha256:" + "a" * 64  # Explicit offline fixture, never a release identity.


def command(*args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True, timeout=90)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def main() -> None:
    output = ROOT / ".runtime/verification/cloud/helm" / uuid4().hex
    output.mkdir(parents=True, exist_ok=False)
    summaries = []
    for name, namespace, chart, files in (
        ("demo-deps", "opsproof-demo", "opsproof-dependencies", ["values-demo-eks.yaml"]),
        ("control-deps", "opsproof-control", "opsproof-dependencies", ["values-control-eks.yaml"]),
        (
            "demo",
            "opsproof-demo",
            "opsproof-services",
            ["values-demo.yaml", "values-demo-eks.yaml"],
        ),
        (
            "control",
            "opsproof-control",
            "opsproof-services",
            ["values-control.yaml", "values-control-eks.yaml"],
        ),
        ("web", "opsproof-ui", "opsproof-web", ["values-eks.yaml"]),
        ("opsproof-edge", "opsproof-edge", "opsproof-edge", []),
    ):
        path = "infra/helm/" + chart
        flags = [arg for value in files for arg in ("-f", path + "/" + value)]
        if not name.endswith("-deps"):
            flags += [
                "--set-string",
                "image.repository=ghcr.io/offline/fixture/opsproof-" + name,
                "--set-string",
                "image.digest=" + DIGEST,
            ]
        if name == "opsproof-edge":
            flags += ["--set", "albEnabled=true,albSecurityGroupId=sg-12345678"]
        command("helm", "lint", path, *flags)
        rendered = command("helm", "template", name, path, "-n", namespace, *flags).stdout
        rows = [row for row in yaml.safe_load_all(rendered) if row]
        validate(rows)
        (output / (name + ".yaml")).write_text(rendered, encoding="utf-8")
        if name == "control-deps":
            require(
                not any("postgres" in row["metadata"]["name"] for row in rows),
                "Control must use RDS",
            )
        if name == "control":
            for row in rows:
                if row["kind"] != "Deployment":
                    continue
                pod = row["spec"]["template"]["spec"]
                container = pod["containers"][0]
                env = {field["name"]: field["value"] for field in container.get("env", [])}
                for field in ("RECOVERY_ENABLED", "KUBERNETES_RECOVERY_ENABLED", "AI_ENABLED"):
                    require(
                        env["OPSPROOF_CONTROL_" + field] == "false",
                        "Cloud mutation/model gate leaked",
                    )
                require(
                    container["envFrom"][-1]["secretRef"]["name"]
                    == "opsproof-control-rds-app-connection",
                    "Application RDS identity must be last",
                )
                mounted = {volume["name"] for volume in pod.get("volumes", [])}
                require(
                    ("kubernetes-identity" in mounted)
                    == row["metadata"]["name"].endswith("-evidence"),
                    "Only observer may mount API token",
                )
        if name.endswith("-deps"):
            redis = next(
                row
                for row in rows
                if row["kind"] == "StatefulSet" and row["metadata"]["name"].endswith("-redis")
            )
            pod = redis["spec"]["template"]["spec"]
            config = next(volume for volume in pod["volumes"] if volume["name"] == "redis-config")
            require(
                config["emptyDir"]["medium"] == "Memory",
                "Redis credential config must be memory-only",
            )
        if name == "demo":
            hpa = next(row for row in rows if row["kind"] == "HorizontalPodAutoscaler")
            require(
                hpa["spec"]["scaleTargetRef"]["kind"] == "Deployment",
                "HPA target differs from actual cloud API controller",
            )
            auth = next(row for row in rows if row["kind"] == "TriggerAuthentication")
            require(
                {ref["parameter"] for ref in auth["spec"]["secretTargetRef"]}
                == {"tls", "password", "ca"},
                "KEDA TLS/auth contract incomplete",
            )
        if name == "web":
            require(
                not any(row["kind"] in {"Ingress", "HTTPRoute"} for row in rows),
                "Operator UI must remain private",
            )
        summaries.append({"profile": name, "objects": len(rows)})
    verify()
    for controller in loaded():
        values = ROOT / "infra/k8s/cloud/controllers" / (controller["name"] + ".yaml")
        command("helm", "lint", str(filename(controller)), "--values", str(values))
        rendered = command(
            "helm",
            "template",
            controller["release"],
            str(filename(controller)),
            "--namespace",
            controller["namespace"],
            "--values",
            str(values),
            "--include-crds",
        ).stdout
        rows = [row for row in yaml.safe_load_all(rendered) if row]
        if controller["name"] == "argo-cd":
            require(
                not any(row["kind"] in {"ClusterRole", "ClusterRoleBinding"} for row in rows),
                "Argo must stay namespace-scoped",
            )
        if controller["name"] == "external-secrets":
            for row in rows:
                if row["kind"] != "ClusterRole":
                    continue
                require(
                    not any(
                        "secrets" in rule.get("resources", []) for rule in row.get("rules", [])
                    ),
                    "ESO must not have cluster-wide application Secret access",
                )
        for row in rows:
            if (
                row["kind"] not in {"Deployment", "StatefulSet"}
                or row["spec"].get("replicas", 1) == 0
            ):
                continue
            for container in row["spec"]["template"]["spec"]["containers"]:
                resources = container.get("resources", {})
                require(
                    resources.get("requests") and resources.get("limits"),
                    "Unbounded controller: " + row["metadata"]["name"],
                )
        (output / (controller["name"] + ".yaml")).write_text(rendered, encoding="utf-8")
        summaries.append({"profile": controller["name"], "objects": len(rows)})
    result = {"status": "RENDER_VALIDATED_NOT_RUNTIME_ACCEPTED", "profiles": summaries}
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
