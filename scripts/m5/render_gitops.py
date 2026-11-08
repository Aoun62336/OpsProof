"""Render Argo CD project/applications from an explicitly approved, reachable Git revision.

Stdlib only. No network, push, merge or cluster modification.
"""

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import urlparse


def default_repo():
    proc = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


LOCAL_REPO = "http://opsproof-git.opsproof-git.svc.cluster.local:8080/repo.git"


def git_url(text, allow_local=False):
    if allow_local and text == LOCAL_REPO:
        return text
    if text.startswith("git@github.com:"):
        text = "https://github.com/" + text.removeprefix("git@github.com:")
    parsed = urlparse(text)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError(
            "Only an explicit HTTPS GitHub remote is supported in this local profile"
        )
    if not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", parsed.path):
        raise ValueError("Invalid GitHub repository URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Repository URL must not contain credentials or query strings")
    return text


def application(name, namespace, path, value_files, revision, url, tag, wave):
    result = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": name,
            "namespace": "argocd",
            "annotations": {"argocd.argoproj.io/sync-wave": str(wave)},
        },
        "spec": {
            "project": "opsproof",
            "source": {
                "repoURL": url,
                "targetRevision": revision,
                "path": path,
                "helm": {
                    "valueFiles": value_files,
                    "parameters": [{"name": "image.tag", "value": tag}],
                }
                if name in ("demo", "control", "web")
                else {"valueFiles": value_files},
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": namespace,
            },
            "syncPolicy": {
                "automated": {"prune": False, "selfHeal": True},
                "syncOptions": ["CreateNamespace=false"],
            },
        },
    }
    if name == "demo":
        result["spec"]["syncPolicy"]["syncOptions"].append(
            "RespectIgnoreDifferences=true"
        )
        result["spec"]["ignoreDifferences"] = [
            {
                "group": "gateway.networking.k8s.io",
                "kind": "HTTPRoute",
                "name": "demo-release",
                "namespace": namespace,
                "jsonPointers": [
                    "/spec/rules/0/backendRefs/0/weight",
                    "/spec/rules/0/backendRefs/1/weight",
                ],
            },
            *[
                {
                    "group": "",
                    "kind": "Service",
                    "name": service,
                    "namespace": namespace,
                    "jsonPointers": ["/spec/selector/rollouts-pod-template-hash"],
                }
                for service in ("demo-api", "demo-api-canary")
            ],
        ]
    return result


def render(repo, revision, tag, allow_local=False):
    repo = git_url(repo, allow_local)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError(
            "Use a full 40-character Git SHA already present on the remote"
        )
    if not re.fullmatch(r"m5-[0-9a-f]{12,40}", tag):
        raise ValueError("Provide a traceable immutable M5 image tag")
    project = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {"name": "opsproof", "namespace": "argocd"},
        "spec": {
            "description": "Local-only OpsProof GitOps app boundary",
            "sourceRepos": [repo],
            "destinations": [
                {"server": "https://kubernetes.default.svc", "namespace": ns}
                for ns in ("opsproof-demo", "opsproof-control", "opsproof-ui")
            ],
            "clusterResourceWhitelist": [],
            "namespaceResourceWhitelist": [
                {"group": group, "kind": kind}
                for group, kind in (
                    ("", "Service"),
                    ("", "ServiceAccount"),
                    ("", "PersistentVolumeClaim"),
                    ("apps", "Deployment"),
                    ("apps", "StatefulSet"),
                    ("batch", "Job"),
                    ("autoscaling", "HorizontalPodAutoscaler"),
                    ("keda.sh", "ScaledObject"),
                    ("argoproj.io", "Rollout"),
                    ("argoproj.io", "AnalysisTemplate"),
                    ("gateway.networking.k8s.io", "HTTPRoute"),
                )
            ],
        },
    }
    deps = "infra/helm/opsproof-dependencies"
    apps = "infra/helm/opsproof-services"
    entries = [
        application(
            "demo-deps", "opsproof-demo", deps, ["values.yaml"], revision, repo, tag, 0
        ),
        application(
            "control-deps",
            "opsproof-control",
            deps,
            ["values.yaml"],
            revision,
            repo,
            tag,
            0,
        ),
        application(
            "demo",
            "opsproof-demo",
            apps,
            ["values.yaml", "values-demo.yaml"],
            revision,
            repo,
            tag,
            1,
        ),
        application(
            "control",
            "opsproof-control",
            apps,
            ["values.yaml", "values-control.yaml"],
            revision,
            repo,
            tag,
            1,
        ),
        application(
            "web",
            "opsproof-ui",
            "infra/helm/opsproof-web",
            ["values.yaml"],
            revision,
            repo,
            tag,
            2,
        ),
    ]
    # No route drift exclusions until a specific Rollout-managed route exists.
    return {"apiVersion": "v1", "kind": "List", "items": [project, *entries]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-url", default=default_repo())
    parser.add_argument(
        "--local",
        action="store_true",
        help="use only the fixed in-cluster read-only Git server",
    )
    parser.add_argument("--revision", required=True, help="full remote Git SHA")
    parser.add_argument(
        "--tag", required=True, help="published or locally resolvable image tag"
    )
    args = parser.parse_args()
    try:
        output = render(
            LOCAL_REPO if args.local else args.repo_url,
            args.revision,
            args.tag,
            allow_local=args.local,
        )
    except ValueError as exc:
        print(f"GitOps manifest rejected: {exc}", file=sys.stderr)
        sys.exit(2)
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
