"""Checksum-pinned secret scan and strict built-in Kubernetes schema validation."""

import hashlib
import os
import shutil
import subprocess
import tarfile
import zipfile
from urllib.request import urlopen

import yaml
from preflight import ROOT

ASSETS = {
    "gitleaks": {
        "windows": (
            "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_windows_x64.zip",
            "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
        ),
        "linux": (
            "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz",
            "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
        ),
    },
    "kubeconform": {
        "windows": (
            "https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-windows-amd64.zip",
            "e3f56102bcf4f50b034a567e2482a1c5330799983ddd655952310211aef73d93",
        ),
        "linux": (
            "https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-linux-amd64.tar.gz",
            "9bc2bffbf71f261128533edaf912153948b7ff238f9a531ae6d34466ec287883",
        ),
    },
}


def binary(name):
    platform = "windows" if os.name == "nt" else "linux"
    url, digest = ASSETS[name][platform]
    directory = ROOT / ".runtime/m5/security-tools"
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / url.rsplit("/", 1)[1]
    if not archive.exists():
        with urlopen(url, timeout=90) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Tool checksum mismatch: " + name)
    filename = name + (".exe" if os.name == "nt" else "")
    if os.name == "nt":
        with zipfile.ZipFile(archive) as package:
            data = package.read(filename)
    else:
        with tarfile.open(archive) as package:
            data = package.extractfile(filename).read()
    target = directory / filename
    target.write_bytes(data)
    target.chmod(0o755)
    return str(target)


def main():
    output = ROOT / ".runtime/m5/acceptance"
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
            if obj
            and obj["apiVersion"] in ("v1", "apps/v1", "batch/v1", "autoscaling/v2")
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
    print(
        "Custom resources are checked against installed API-server CRDs during live acceptance."
    )


if __name__ == "__main__":
    main()
