"""Prepare immutable cloud Applications; no publication, sync or cluster writes.

Initial sync is manual and ordered. Enable automated reconciliation only after
dependency/bootstrap/migration checks; never keep a second Helm CLI reconciler.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from scripts.cloud.verify_release_manifest import validate
from scripts.platform.render_gitops import application, git_url


def render(record: dict, repo: str, alb_security_group: str, *, reconcile: bool = False) -> dict:
    validate(record)
    repo = git_url(repo)
    expected = "/" + record["repository"]
    if urlparse(repo).path.removesuffix(".git").lower() != expected:
        raise ValueError("Release repository and GitOps source must match")
    if not re.fullmatch(r"sg-[0-9a-f]{8,17}", alb_security_group):
        raise ValueError("Actual platform ALB security group required")
    project = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "AppProject",
        "metadata": {"name": "opsproof-cloud", "namespace": "argocd"},
        "spec": {
            "description": "Private OpsProof workloads; no secret or permission management",
            "sourceRepos": [repo],
            "destinations": [
                {"server": "https://kubernetes.default.svc", "namespace": namespace}
                for namespace in (
                    "opsproof-demo",
                    "opsproof-control",
                    "opsproof-ui",
                    "opsproof-edge",
                )
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
                    ("networking.k8s.io", "NetworkPolicy"),
                    ("networking.k8s.io", "Ingress"),
                    ("keda.sh", "ScaledObject"),
                    ("keda.sh", "TriggerAuthentication"),
                )
            ],
        },
    }
    entries = []
    for name, namespace, chart, files, role, wave in (
        (
            "demo-deps",
            "opsproof-demo",
            "opsproof-dependencies",
            ["values.yaml", "values-demo-eks.yaml"],
            None,
            0,
        ),
        (
            "control-deps",
            "opsproof-control",
            "opsproof-dependencies",
            ["values.yaml", "values-control-eks.yaml"],
            None,
            0,
        ),
        (
            "demo",
            "opsproof-demo",
            "opsproof-services",
            ["values.yaml", "values-demo.yaml", "values-demo-eks.yaml"],
            "demo",
            1,
        ),
        (
            "control",
            "opsproof-control",
            "opsproof-services",
            ["values.yaml", "values-control.yaml", "values-control-eks.yaml"],
            "control",
            1,
        ),
        ("web", "opsproof-ui", "opsproof-web", ["values.yaml", "values-eks.yaml"], "web", 2),
        ("opsproof-edge", "opsproof-edge", "opsproof-edge", ["values.yaml"], "edge", 2),
    ):
        app = application(
            name, namespace, "infra/helm/" + chart, files, record["source_sha"], repo, "", wave
        )
        spec = app["spec"]
        spec["project"] = "opsproof-cloud"
        spec.pop("ignoreDifferences", None)
        spec["syncPolicy"] = {"syncOptions": ["CreateNamespace=false"]}
        if reconcile:
            spec["syncPolicy"]["automated"] = {"prune": False, "selfHeal": True}
        helm = {"releaseName": name, "valueFiles": files, "parameters": []}
        if role:
            repository, digest = record["images"][role].split("@", 1)
            helm["parameters"] = [
                {"name": "image.repository", "value": repository},
                {"name": "image.digest", "value": digest},
            ]
        if role == "edge":
            helm["parameters"] += [
                {"name": "albEnabled", "value": "true"},
                {"name": "albSecurityGroupId", "value": alb_security_group},
            ]
        spec["source"]["helm"] = helm
        entries.append(app)
    return {"apiVersion": "v1", "kind": "List", "items": [project, *entries]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--alb-security-group", required=True)
    parser.add_argument("--enable-reconciliation", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = render(
        json.loads(args.release.read_text(encoding="utf-8")),
        args.repo_url,
        args.alb_security_group,
        reconcile=args.enable_reconciliation,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        "CLOUD_APPLICATIONS_RENDERED; source reachability and registry trust remain release gates"
    )


if __name__ == "__main__":
    main()
