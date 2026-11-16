"""Serve committed Git objects read-only inside k3d; no GitHub/registry push."""

import json
import shutil
import subprocess

from local_cluster import kubectl_prefix
from preflight import ROOT


def main():
    kube = kubectl_prefix()
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    context = ROOT / ".runtime/m5/git-server" / sha
    context.mkdir(parents=True, exist_ok=True)
    repo = context / "repo.git"
    if not repo.exists():
        subprocess.run(
            ["git", "clone", "--bare", "--no-hardlinks", str(ROOT), str(repo)],
            check=True,
        )
    subprocess.run(["git", "--git-dir", str(repo), "update-server-info"], check=True)
    shutil.copyfile(ROOT / "infra/k8s/git-server/nginx.conf", context / "nginx.conf")
    (context / "Dockerfile").write_text(
        (
            "FROM nginxinc/nginx-unprivileged:1.31.7-alpine3.24@sha256:b5"
            "047b9b76845eac124358373c6852377c52e4b05834a47647e955dd91cb8f1e\n"
        )
        + "COPY --chown=101:101 repo.git /usr/share/nginx/html/repo.git\n"
        "COPY --chown=101:101 nginx.conf /etc/nginx/nginx.conf\nUSER 101:101\n"
    )
    image = "opsproof-git:" + sha
    subprocess.run(["docker", "build", "-t", image, str(context)], check=True)
    subprocess.run(["k3d", "image", "import", image, "-c", "opsproof"], check=True)
    labels = {"app.kubernetes.io/name": "opsproof-git"}
    objects = [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": "opsproof-git",
                "labels": {"pod-security.kubernetes.io/enforce": "restricted"},
            },
        },
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "opsproof-git", "namespace": "opsproof-git"},
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": labels},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "automountServiceAccountToken": False,
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 101,
                            "runAsGroup": 101,
                            "fsGroup": 101,
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                        "containers": [
                            {
                                "name": "git",
                                "image": image,
                                "imagePullPolicy": "IfNotPresent",
                                "command": ["nginx", "-g", "daemon off;"],
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "readOnlyRootFilesystem": True,
                                    "capabilities": {"drop": ["ALL"]},
                                },
                                "resources": {
                                    "requests": {"cpu": "10m", "memory": "16Mi"},
                                    "limits": {"cpu": "150m", "memory": "64Mi"},
                                },
                                "ports": [{"containerPort": 8080}],
                                "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],
                                "readinessProbe": {"httpGet": {"path": "/healthz", "port": 8080}},
                            }
                        ],
                        "volumes": [{"name": "tmp", "emptyDir": {"sizeLimit": "16Mi"}}],
                    },
                },
            },
        },
        {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "opsproof-git", "namespace": "opsproof-git"},
            "spec": {
                "selector": labels,
                "ports": [{"port": 8080, "targetPort": 8080}],
                "type": "ClusterIP",
            },
        },
        {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": "argocd-read-only-git", "namespace": "opsproof-git"},
            "spec": {
                "podSelector": {"matchLabels": labels},
                "policyTypes": ["Ingress", "Egress"],
                "egress": [],
                "ingress": [
                    {
                        "from": [
                            {
                                "namespaceSelector": {
                                    "matchLabels": {"kubernetes.io/metadata.name": "argocd"}
                                }
                            }
                        ],
                        "ports": [{"port": 8080, "protocol": "TCP"}],
                    }
                ],
            },
        },
    ]
    subprocess.run(
        [*kube, "apply", "-f", "-"],
        input=json.dumps({"apiVersion": "v1", "kind": "List", "items": objects}),
        text=True,
        check=True,
    )
    subprocess.run(
        [
            *kube,
            "rollout",
            "status",
            "deployment/opsproof-git",
            "-n",
            "opsproof-git",
            "--timeout=120s",
        ],
        check=True,
    )
    print("Local-only Git revision available:", sha)


if __name__ == "__main__":
    main()
