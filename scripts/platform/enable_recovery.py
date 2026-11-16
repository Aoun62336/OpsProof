"""Explicitly enable fixed-target recovery after tested image import and migration."""

import argparse
import json
import subprocess

from gitops_config import configure
from local_cluster import kubectl_prefix
from preflight import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--image-revision")
    args = parser.parse_args()
    image_revision = args.image_revision or args.revision
    kube = kubectl_prefix()

    def get(kind, name, ns):
        return json.loads(
            subprocess.check_output([*kube, "get", kind, name, "-n", ns, "-o", "json"], text=True)
        )

    subprocess.run([*kube, "apply", "-f", str(ROOT / "infra/k8s/recovery-rbac.yaml")], check=True)
    endpoint = get("endpoints", "kubernetes", "default")["subsets"][0]
    api = get("svc", "kubernetes", "default")["spec"]["clusterIP"]
    policy = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": "restricted-worker-kubernetes",
            "namespace": "opsproof-control",
        },
        "spec": {
            "podSelector": {
                "matchLabels": {"app.kubernetes.io/instance": "control"},
                "matchExpressions": [
                    {
                        "key": "opsproof.io/role",
                        "operator": "In",
                        "values": ["action", "evidence"],
                    }
                ],
            },
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
                }
            ],
        },
    }
    subprocess.run([*kube, "apply", "-f", "-"], input=json.dumps(policy), text=True, check=True)
    app = get("application", "demo", "argocd")
    ignores = [
        r for r in app["spec"].get("ignoreDifferences", []) if r.get("name") != "demo-worker"
    ]
    ignores.append(
        {
            "group": "apps",
            "kind": "Deployment",
            "namespace": "opsproof-demo",
            "name": "demo-worker",
            "jsonPointers": [
                "/spec/replicas",
                "/metadata/annotations/opsproof.io~1recovery-id",
            ],
        }
    )
    configure(
        "demo",
        {"worker.recoveryManaged": True, "autoscaling.keda.enabled": False},
        revision=args.revision,
        extra_spec={"ignoreDifferences": ignores},
    )
    configure(
        "control",
        {
            "image.tag": "m5-" + image_revision[:12],
            "kubernetesRecoveryEnabled": True,
            "telemetry.enabled": True,
            "recoveryEnabled": True,
        },
        revision=args.revision,
    )
    configure("web", {"image.tag": "m5-" + image_revision[:12]}, revision=args.revision)


if __name__ == "__main__":
    main()
