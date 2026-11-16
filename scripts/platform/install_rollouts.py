"""Install pinned namespaced Rollouts with a checksum-verified offline plugin."""

import hashlib
import json
import subprocess
from urllib.request import urlopen

import yaml
from local_cluster import kubectl_prefix
from preflight import ROOT

NS = "opsproof-demo"
VERSION = "v1.10.2"
PLUGIN = "v0.17.0"
ASSETS = {
    "install.yaml": (
        f"https://github.com/argoproj/argo-rollouts/releases/download/{VERSION}/install.yaml",
        "b8280994791eaee7eb91c8b84450efcc6e0292fca5aafc18c1b0ebc5d18dbefe",
    ),
    "namespace-install.yaml": (
        f"https://github.com/argoproj/argo-rollouts/releases/download/{VERSION}/namespace-install.yaml",
        "bb14ecec25afb7880500c58cf51ac8b15f513305d2756e21e63d03be9cb9906c",
    ),
    "gatewayapi-plugin-linux-amd64": (
        f"https://github.com/argoproj-labs/rollouts-plugin-trafficrouter-gatewayapi/releases/download/{PLUGIN}/gatewayapi-plugin-linux-amd64",
        "1904ca787d33107c140521899d61fff030ee75d99908bd175fca5a4647759061",
    ),
}


def main():
    kube = kubectl_prefix()
    directory = ROOT / ".runtime/m5/rollouts"
    directory.mkdir(parents=True, exist_ok=True)
    for filename, (url, digest) in ASSETS.items():
        path = directory / filename
        if not path.exists():
            with urlopen(url, timeout=90) as response:
                path.write_bytes(response.read())
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Untrusted controller/plugin download: " + filename)
    subprocess.run(["docker", "pull", f"quay.io/argoproj/argo-rollouts:{VERSION}"], check=True)
    base = json.loads(
        subprocess.check_output(
            [
                "docker",
                "image",
                "inspect",
                f"quay.io/argoproj/argo-rollouts:{VERSION}",
                "--format",
                "{{json .RepoDigests}}",
            ],
            text=True,
        )
    )[0]
    (directory / "Dockerfile").write_text(
        f"FROM {base}\n"
        "COPY --chmod=0555 gatewayapi-plugin-linux-amd64 /opt/opsproof/gatewayapi-plugin\n"
    )
    image = f"opsproof-rollouts:{VERSION}-{PLUGIN}"
    subprocess.run(["docker", "build", "-t", image, str(directory)], check=True)
    subprocess.run(["k3d", "image", "import", image, "-c", "opsproof"], check=True)
    crds = [
        obj
        for obj in yaml.safe_load_all((directory / "install.yaml").read_text())
        if obj and obj["kind"] == "CustomResourceDefinition"
    ]
    subprocess.run(
        [*kube, "apply", "--server-side", "-f", "-"],
        input=yaml.safe_dump_all(crds),
        text=True,
        check=True,
    )
    objects = []
    for obj in yaml.safe_load_all((directory / "namespace-install.yaml").read_text()):
        if not obj or obj["kind"] in ("ClusterRole", "ClusterRoleBinding"):
            continue
        obj["metadata"]["namespace"] = NS
        if obj["kind"] == "Role":
            # Keep only core namespaced controller APIs; no cloud/router grants.
            obj["rules"] = [
                rule
                for rule in obj["rules"]
                if set(rule["apiGroups"])
                <= {"", "apps", "argoproj.io", "coordination.k8s.io", "batch"}
            ]
            obj["rules"].append(
                {
                    "apiGroups": ["networking.k8s.io"],
                    "resources": ["ingresses"],
                    "verbs": ["get", "list", "watch"],
                }
            )
            obj["rules"].append(
                {
                    "apiGroups": ["gateway.networking.k8s.io"],
                    "resources": ["httproutes"],
                    "resourceNames": ["demo-release"],
                    "verbs": ["get", "update", "patch"],
                }
            )
        if obj["kind"] == "RoleBinding":
            for subject in obj["subjects"]:
                subject["namespace"] = NS
        if obj["kind"] == "ConfigMap":
            obj["data"] = {
                "trafficRouterPlugins": yaml.safe_dump(
                    [
                        {
                            "name": "argoproj-labs/gatewayAPI",
                            "location": "file:///opt/opsproof/gatewayapi-plugin",
                            "sha256": ASSETS["gatewayapi-plugin-linux-amd64"][1],
                        }
                    ]
                )
            }
        if obj["kind"] == "Deployment":
            pod = obj["spec"]["template"]["spec"]
            pod["securityContext"].update({"runAsUser": 999, "runAsGroup": 999, "fsGroup": 999})
            c = pod["containers"][0]
            c["image"] = image
            c["imagePullPolicy"] = "IfNotPresent"
            c["resources"] = {
                "requests": {"cpu": "25m", "memory": "96Mi"},
                "limits": {"cpu": "500m", "memory": "256Mi"},
            }
        objects.append(obj)
    endpoint = json.loads(
        subprocess.check_output(
            [*kube, "get", "endpoints", "kubernetes", "-n", "default", "-o", "json"],
            text=True,
        )
    )["subsets"][0]
    api = json.loads(
        subprocess.check_output(
            [*kube, "get", "svc", "kubernetes", "-n", "default", "-o", "json"],
            text=True,
        )
    )["spec"]["clusterIP"]
    objects.append(
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "rollouts-controller-egress", "namespace": NS},
            "spec": {
                "podSelector": {"matchLabels": {"app.kubernetes.io/name": "argo-rollouts"}},
                "policyTypes": ["Egress"],
                "egress": [
                    {
                        "to": [
                            {"ipBlock": {"cidr": ip + "/32"}}
                            for ip in [api, *[a["ip"] for a in endpoint["addresses"]]]
                        ],
                        "ports": [
                            {"port": p, "protocol": "TCP"}
                            for p in {443, *[p["port"] for p in endpoint["ports"]]}
                        ],
                    },
                    {
                        "to": [
                            {
                                "namespaceSelector": {
                                    "matchLabels": {
                                        "kubernetes.io/metadata.name": "opsproof-observability"
                                    }
                                }
                            }
                        ],
                        "ports": [{"port": 9090, "protocol": "TCP"}],
                    },
                ],
            },
        }
    )
    subprocess.run(
        [*kube, "apply", "-f", "-"],
        input=yaml.safe_dump_all(objects),
        text=True,
        check=True,
    )
    subprocess.run(
        [
            *kube,
            "rollout",
            "status",
            "deployment/argo-rollouts",
            "-n",
            NS,
            "--timeout=300s",
        ],
        check=True,
    )
    (ROOT / ".runtime/m5/acceptance/rollouts-install.json").write_text(
        json.dumps(
            {
                "controller_version": VERSION,
                "base_digest": base,
                "local_image": image,
                "plugin_version": PLUGIN,
                "plugin_sha256": ASSETS["gatewayapi-plugin-linux-amd64"][1],
                "namespace": NS,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
