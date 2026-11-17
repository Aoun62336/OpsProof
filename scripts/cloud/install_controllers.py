"""Version-locked Helm chart acquisition, integrity reconciliation and install.

Two explicit operations: `lock` downloads reviewed exact VERSION chart archives and
writes a local SHA256 lock (source-review required); `verify`/`install` consume ONLY
these identical archives, never fetch mutable charts at deploy time. No cluster
mutation without --execute and exact kube-context validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
VERSION_SOURCE = ROOT / "infra/k8s/cloud/controller-versions.json"
CHARTS = ROOT / ".runtime/cloud/charts"
LOCK = ROOT / "infra/k8s/cloud/controller-charts.lock.json"


def run(*args: str) -> str:
    result = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        timeout=720,
        env={
            **os.environ,
            "HELM_REPOSITORY_CACHE": str(CHARTS / "repository-cache"),
            "HELM_REPOSITORY_CONFIG": str(CHARTS / "repositories.yaml"),
        },
    )
    return result.stdout.strip()


def loaded() -> list[dict]:
    d = json.loads(VERSION_SOURCE.read_text(encoding="utf-8"))
    if (
        d.get("cluster") != "opsproof-cloud"
        or d.get("region") != "ap-south-1"
        or len(d.get("controllers", [])) != 5
    ):
        raise ValueError("Unexpected controller target or catalog size")
    if len({row["name"] for row in d["controllers"]}) != 5:
        raise ValueError("Duplicate controller identity")
    return d["controllers"]


def filename(item: dict) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", item["chart"]) or not re.fullmatch(
        r"\d+\.\d+\.\d+", item["version"]
    ):
        raise ValueError("malformed pinned chart")
    return CHARTS / f"{item['chart']}-{item['version']}.tgz"


def chart_metadata(item: dict) -> list[dict]:
    """Read one root chart and safe packaged dependencies without extraction."""
    file = filename(item)
    if file.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Chart archive exceeds the reviewed size limit")
    root_name = item["chart"]
    charts = []
    names = set()
    with tarfile.open(file, "r:gz") as archive:
        for entry in archive.getmembers():
            path = PurePosixPath(entry.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in entry.name
                or not path.parts
                or path.parts[0] != root_name
                or entry.issym()
                or entry.islnk()
                or entry.name in names
            ):
                raise ValueError("Unsafe or duplicate chart archive member")
            names.add(entry.name)
            if path.name != "Chart.yaml":
                continue
            if not entry.isfile() or entry.size > 64 * 1024:
                raise ValueError("Invalid chart metadata member")
            stream = archive.extractfile(entry)
            if stream is None:
                raise ValueError("Unreadable chart metadata")
            payload = stream.read()
            fields = re.findall(
                r"^(name|version|apiVersion):\s*['\"]?([^\s'\"]+)",
                payload.decode("utf-8"),
                flags=re.MULTILINE,
            )
            properties = dict(fields)
            if len(fields) != 3 or set(properties) != {"name", "version", "apiVersion"}:
                raise ValueError("Ambiguous or incomplete chart metadata")
            if properties["apiVersion"] not in ("v1", "v2"):
                raise ValueError("Unsupported chart API")
            charts.append(
                {
                    "path": entry.name,
                    **properties,
                    "metadata_sha256": hashlib.sha256(payload).hexdigest(),
                    "app_version": (
                        re.search(
                            r"(?m)^appVersion:\s*[\"\']?([^\s\"\']+)", payload.decode("utf-8")
                        ).group(1)
                        if re.search(
                            r"(?m)^appVersion:\s*[\"\']?([^\s\"\']+)", payload.decode("utf-8")
                        )
                        else None
                    ),
                }
            )
    roots = [record for record in charts if record["path"] == root_name + "/Chart.yaml"]
    if len(roots) != 1 or roots[0]["name"] != root_name or roots[0]["version"] != item["version"]:
        raise ValueError("Chart root identity mismatch")
    return charts


def chart_sha(item: dict) -> str:
    chart_metadata(item)
    return hashlib.sha256(filename(item).read_bytes()).hexdigest()


def lock_charts() -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    for row in loaded():
        if filename(row).exists():
            chart_sha(row)
            continue
        run(
            "helm",
            "pull",
            row["chart"],
            "--repo",
            row["repo_url"],
            "--version",
            row["version"],
            "--destination",
            str(CHARTS),
        )
    if LOCK.exists():
        verify()
        return
    d = {
        "schema": 2,
        "note": (
            "Exact official HTTPS downloads and archive metadata reviewed; "
            "hashes are integrity pins, not publisher signatures"
        ),
        "charts": [
            {
                "name": row["name"],
                "file": filename(row).name,
                "version": row["version"],
                "sha256": chart_sha(row),
                "repository_url": row["repo_url"],
                "metadata": chart_metadata(row),
            }
            for row in loaded()
        ],
    }
    LOCK.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    print("CHARTS_FETCHED_AND_HASHED; REVIEW UPSTREAM PROVENANCE BEFORE APPROVAL")


def verify() -> None:
    d = json.loads(LOCK.read_text(encoding="utf-8"))
    if d.get("schema") != 2 or len(d.get("charts", [])) != 5:
        raise ValueError("Expected complete controller lock schema 2")
    expected = {i["name"]: i for i in d["charts"]}
    if set(expected) != {row["name"] for row in loaded()}:
        raise ValueError("Controller lock contains missing or duplicate identities")
    for row in loaded():
        locked = expected[row["name"]]
        if locked["version"] != row["version"] or locked["file"] != filename(row).name:
            raise ValueError(f"wrong chart identity {row['name']}")
        if locked.get("repository_url") != row["repo_url"] or locked.get(
            "metadata"
        ) != chart_metadata(row):
            raise ValueError("Chart origin or packaged dependency metadata mismatch")
        if locked["sha256"] != chart_sha(row):
            raise ValueError(f"chart SHA256 mismatch: {row['name']}")
    print("FIVE_CONTROLLER_CHARTS_MATCH_LOCAL_LOCK; UPSTREAM REVIEW IS SEPARATE")


def assert_cluster(kubeconfig: Path, account: str, profile: str) -> str:
    if not re.fullmatch(r"[0-9]{12}", account):
        raise ValueError("Exact expected AWS account required")
    owned = (ROOT / ".runtime/cloud").resolve()
    if not kubeconfig.resolve().is_relative_to(owned):
        raise ValueError("Use a dedicated kubeconfig under .runtime/cloud")
    caller = json.loads(
        run("aws", "sts", "get-caller-identity", "--profile", profile, "--output", "json")
    )
    if caller.get("Account") != account:
        raise ValueError("AWS account mismatch")
    cluster = json.loads(
        run(
            "aws",
            "eks",
            "describe-cluster",
            "--profile",
            profile,
            "--region",
            "ap-south-1",
            "--name",
            "opsproof-cloud",
            "--output",
            "json",
        )
    )["cluster"]
    if cluster.get("arn") != f"arn:aws:eks:ap-south-1:{account}:cluster/opsproof-cloud":
        raise ValueError("Unexpected EKS identity")
    config = json.loads(
        run(
            "kubectl",
            "--kubeconfig",
            str(kubeconfig),
            "--context",
            "opsproof-cloud-temporary",
            "config",
            "view",
            "--raw",
            "--minify",
            "-o",
            "json",
        )
    )
    endpoint = config["clusters"][0]["cluster"]
    if (
        endpoint.get("server") != cluster.get("endpoint")
        or endpoint.get("certificate-authority-data")
        != cluster.get("certificateAuthority", {}).get("data")
        or endpoint.get("insecure-skip-tls-verify", False)
        or cluster.get("status") != "ACTIVE"
    ):
        raise ValueError("Kubeconfig endpoint, CA or active EKS identity mismatch")
    auth = config["users"][0]["user"]
    exec_auth = auth.get("exec", {})
    if exec_auth.get("command") != "aws" or "get-token" not in exec_auth.get("args", []):
        raise ValueError("Expected AWS EKS token authentication in the dedicated kubeconfig")

    vpc_id = cluster.get("resourcesVpcConfig", {}).get("vpcId", "")
    if not re.fullmatch(r"vpc-(?:[0-9a-f]{8}|[0-9a-f]{17})", vpc_id):
        raise ValueError("Expected the verified cluster VPC identity")
    return vpc_id


def install(kubeconfig: Path, account: str, profile: str) -> None:
    verify()
    vpc_id = assert_cluster(kubeconfig, account, profile)
    overrides = {
        "aws-load-balancer-controller": [
            "--set",
            "clusterName=opsproof-cloud",
            "--set",
            "serviceAccount.create=true",
            "--set",
            "serviceAccount.name=aws-load-balancer-controller",
            "--set",
            "region=ap-south-1",
            "--set-string",
            "vpcId=" + vpc_id,
        ],
        "external-secrets": [
            "--set",
            "installCRDs=true",
            "--set",
            "serviceAccount.name=external-secrets",
        ],
        "argo-cd": ["--set", "server.service.type=ClusterIP"],
        "argo-rollouts": [],
        "keda": [],
    }
    # After resource deployment, verify Pod Identity bindings match SA names.
    for row in loaded():
        run(
            "helm",
            "upgrade",
            "--install",
            row["release"],
            str(filename(row)),
            "--values",
            str(ROOT / "infra/k8s/cloud/controllers" / (row["name"] + ".yaml")),
            "--namespace",
            row["namespace"],
            "--kubeconfig",
            str(kubeconfig),
            "--kube-context",
            "opsproof-cloud-temporary",
            "--create-namespace",
            "--wait",
            "--timeout",
            "10m",
            *overrides[row["name"]],
        )
        print(f"INSTALLED_AND_WAITED {row['name']} {row['version']}")
    for crd in (
        "externalsecrets.external-secrets.io",
        "scaledobjects.keda.sh",
        "rollouts.argoproj.io",
        "targetgroupbindings.elbv2.k8s.aws",
    ):
        run(
            "kubectl",
            "--kubeconfig",
            str(kubeconfig),
            "--context",
            "opsproof-cloud-temporary",
            "get",
            "crd",
            crd,
        )
    print("ALL_FIVE_CONTROLLERS_INSTALLED_AND_REQUIRED_CRDS_PRESENT; runtime tests still required")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("lock", "verify", "install"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--kubeconfig", type=Path)
    parser.add_argument("--expected-account")
    parser.add_argument("--profile", default="opsproof-cloud")
    args = parser.parse_args()
    if args.operation == "lock":
        if not args.execute:
            parser.error("lock requires --execute to download version-pinned charts")
        lock_charts()
    elif args.operation == "verify":
        verify()
    else:
        if not args.execute:
            parser.error("install requires --execute")
        if not args.kubeconfig or not args.expected_account:
            parser.error("install requires --kubeconfig and --expected-account")
        install(args.kubeconfig, args.expected_account, args.profile)


if __name__ == "__main__":
    main()
