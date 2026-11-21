"""Checksum-pinned secret scan and strict built-in Kubernetes schema validation."""

import shutil
import subprocess

import yaml

from scripts.platform.preflight import ROOT
from scripts.security_tools import binary


def main():
    output = ROOT / ".runtime/platform/acceptance"
    output.mkdir(parents=True, exist_ok=True)
    # A fresh directory avoids stale copied files; never scan ignored credentials.
    import tempfile

    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    with tempfile.TemporaryDirectory(prefix="opsproof-source-") as temporary:
        from pathlib import Path

        for filename in set(files) - {""}:
            source = ROOT / filename
            if source.is_file():
                target = Path(temporary) / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        subprocess.run(
            [
                binary("gitleaks"),
                "dir",
                temporary,
                "--redact",
                "--no-banner",
                "--report-format",
                "json",
                "--report-path",
                str(output / "secret-scan.json"),
            ],
            check=True,
        )
    manifests = []
    for release, chart, flags in [
        ("demo-deps", "opsproof-dependencies", []),
        (
            "demo",
            "opsproof-services",
            [
                "-f",
                "infra/helm/opsproof-services/values-demo.yaml",
                "--set",
                "image.tag=m5-schema,rollout.enabled=true,rollout.image=opsproof-demo:m5-schema",
            ],
        ),
        (
            "control",
            "opsproof-services",
            [
                "-f",
                "infra/helm/opsproof-services/values-control.yaml",
                "--set",
                "image.tag=m5-schema,kubernetesRecoveryEnabled=true",
            ],
        ),
        ("web", "opsproof-web", ["--set", "image.tag=m5-schema"]),
    ]:
        rendered = subprocess.check_output(
            ["helm", "template", release, "infra/helm/" + chart, *flags],
            cwd=ROOT,
            text=True,
        )
        manifests.extend(
            obj
            for obj in yaml.safe_load_all(rendered)
            if obj and obj["apiVersion"] in ("v1", "apps/v1", "batch/v1", "autoscaling/v2")
        )
    checked = subprocess.run(
        [
            binary("kubeconform"),
            "-strict",
            "-summary",
            "-kubernetes-version",
            "1.35.0",
            "-output",
            "json",
        ],
        input=yaml.safe_dump_all(manifests),
        text=True,
        capture_output=True,
        check=False,
    )
    (output / "schema-check.json").write_text(checked.stdout)
    if checked.returncode:
        raise RuntimeError("Kubernetes schema validation failed; see schema-check.json")
    print(
        "PASS: current nonignored source secret scan and",
        len(manifests),
        "strict built-in resource schemas",
    )
    print("Custom resources are checked against installed API-server CRDs during live acceptance.")


if __name__ == "__main__":
    main()
