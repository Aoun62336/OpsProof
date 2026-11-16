"""Install namespace-scoped Argo CD locally; does not publish or adopt releases."""

import json
import subprocess

import yaml
from gitops_permissions import permissions as scoped_permissions
from local_cluster import helm_prefix, kubectl_prefix
from preflight import ROOT

NAMESPACES = ("opsproof-demo", "opsproof-control", "opsproof-ui")


def permissions():
    return scoped_permissions(NAMESPACES)


def main():
    kube = kubectl_prefix()
    helm = helm_prefix()
    directory = ROOT / ".runtime/m5"
    flags = [
        "--repository-config",
        str(directory / "helm/repositories.yaml"),
        "--repository-cache",
        str(directory / "helm/cache"),
    ]
    subprocess.run(
        ["helm", "repo", "add", "argo", "https://argoproj.github.io/argo-helm", *flags],
        check=True,
    )
    values = str(ROOT / "infra/k8s/argocd/values-local.yaml")
    rendered = subprocess.check_output(
        [
            "helm",
            "template",
            "argocd",
            "argo/argo-cd",
            "--version",
            "10.14.0",
            "-n",
            "argocd",
            "-f",
            values,
            *flags,
        ],
        text=True,
    )
    objects = [obj for obj in yaml.safe_load_all(rendered) if obj]
    if any(obj["kind"] in ("ClusterRole", "ClusterRoleBinding") for obj in objects):
        raise RuntimeError("Unexpected cluster-wide Argo permission")
    namespace = {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {
            "name": "argocd",
            "labels": {"pod-security.kubernetes.io/enforce": "restricted"},
        },
    }
    subprocess.run([*kube, "apply", "-f", "-"], input=json.dumps(namespace), text=True, check=True)
    # No bearer token is stored: in-cluster ServiceAccount authentication is used.
    cluster = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "opsproof-local-cluster",
            "namespace": "argocd",
            "labels": {"argocd.argoproj.io/secret-type": "cluster"},
        },
        "type": "Opaque",
        "stringData": {
            "name": "opsproof-local",
            "server": "https://kubernetes.default.svc",
            "namespaces": ",".join(NAMESPACES),
            "clusterResources": "false",
            "config": "{}",
        },
    }
    subprocess.run(
        [*kube, "apply", "-f", "-"],
        input=json.dumps({"apiVersion": "v1", "kind": "List", "items": [*permissions(), cluster]}),
        text=True,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            *helm,
            "upgrade",
            "--install",
            "argocd",
            "argo/argo-cd",
            "--version",
            "10.14.0",
            "-n",
            "argocd",
            "-f",
            values,
            *flags,
            "--wait",
            "--timeout",
            "8m",
        ],
        check=True,
    )
    print("Argo CD installed with scoped namespace permissions; source adoption still required")


if __name__ == "__main__":
    main()
