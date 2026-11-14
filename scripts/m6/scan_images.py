"""Checksum-verified native Trivy scan of local image archives; no Docker socket.

The scanner receives no provider/AWS credentials and scans only exported local
images. Vulnerabilities are retained for review; findings are not waived by an
ignore-unfixed flag or an allowlist. No image is pushed or resource provisioned.
"""

import hashlib
import json
import os
import subprocess
import zipfile
from urllib.request import urlopen
from uuid import uuid4

from scripts.m5.preflight import GIB, ROOT, memory_available
from scripts.m6.local_environment import utc, write_json

VERSION = "0.76.2"
BASE = f"https://github.com/aquasecurity/trivy/releases/download/v{VERSION}"
ASSET = f"trivy_{VERSION}_windows-64bit.zip"
ARCHIVE_SHA256 = "691f737a7e5566a673c3a74dab9160552ec32101e953b659e5c77443d16dddb6"


def prepare_tool():
    directory = ROOT / ".runtime/m6/security-tools" / VERSION
    directory.mkdir(parents=True, exist_ok=True)
    checksums = directory / "checksums.txt"
    if not checksums.exists():
        with urlopen(BASE + f"/trivy_{VERSION}_checksums.txt", timeout=60) as response:
            checksums.write_bytes(response.read(100_000))
    expected = next(
        line.split()[0] for line in checksums.read_text().splitlines() if line.split()[-1] == ASSET
    )
    if expected != ARCHIVE_SHA256:
        raise ValueError("Publisher checksum differs from the reviewed pinned scanner digest")
    archive = directory / ASSET
    if not archive.exists():
        with (
            urlopen(BASE + "/" + ASSET, timeout=60) as response,
            archive.open("xb") as stream,
        ):
            total = 0
            for data in iter(lambda: response.read(1024 * 1024), b""):
                total += len(data)
                if total > 150 * 1024 * 1024:
                    raise ValueError("Scanner archive exceeds bound")
                stream.write(data)
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise ValueError("Scanner archive checksum mismatch")
    executable = directory / "trivy.exe"
    with zipfile.ZipFile(archive) as package:
        data = package.read("trivy.exe")
        if not executable.exists() or executable.read_bytes() != data:
            executable.write_bytes(data)
    return executable, {
        "version": VERSION,
        "release_url": BASE,
        "archive_sha256": actual,
        "executable_sha256": hashlib.sha256(data).hexdigest(),
    }


def main():
    if memory_available() < 2 * GIB:
        raise RuntimeError("Image scan requires 2 GiB free RAM")
    directory = ROOT / ".runtime/m6/acceptance/images" / ("scan-" + uuid4().hex)
    directory.mkdir(parents=True, exist_ok=False)
    executable, identity = prepare_tool()
    report = {
        "scanned_at": utc(),
        "tool": identity,
        "images": {},
        "findings_review_required": True,
    }
    images = json.loads((ROOT / ".runtime/m6/acceptance/image-provenance.json").read_text())
    scanner_env = {
        name: value
        for name, value in os.environ.items()
        if name.upper()
        in {
            "SYSTEMROOT",
            "WINDIR",
            "PATH",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "LOCALAPPDATA",
            "APPDATA",
            "PROGRAMDATA",
        }
    }
    scanner_env["DOCKER_CONFIG"] = str(directory / "empty-docker-config")
    (directory / "empty-docker-config").mkdir()
    for component in ("demo", "control", "web"):
        image = images[component]
        archive = directory / (component + ".tar")
        subprocess.run(
            ["docker", "image", "save", image["local_image_id"], "-o", str(archive)],
            check=True,
            timeout=180,
        )
        with (directory / (component + ".log")).open("x", encoding="utf-8") as log:
            run = subprocess.run(
                [
                    str(executable),
                    "image",
                    "--input",
                    str(archive),
                    "--scanners",
                    "vuln",
                    "--cache-dir",
                    str(ROOT / ".runtime/m6/security-tools/cache"),
                    "--skip-check-update",
                    "--format",
                    "json",
                    "--output",
                    str(directory / (component + ".json")),
                    "--timeout",
                    "5m",
                ],
                cwd=ROOT,
                env=scanner_env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=330,
                check=False,
            )
        item = {
            "image_id": image["local_image_id"],
            "scanner_exit_code": run.returncode,
        }
        if run.returncode == 0:
            data = json.loads((directory / (component + ".json")).read_text(encoding="utf-8"))
            findings = [
                v for result in data.get("Results", []) for v in result.get("Vulnerabilities", [])
            ]
            item["by_severity"] = {
                level: sum(v.get("Severity") == level for v in findings)
                for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
            }
            item["fixable_high_or_critical"] = [
                {
                    "id": v["VulnerabilityID"],
                    "package": v["PkgName"],
                    "installed": v["InstalledVersion"],
                    "fixed": v["FixedVersion"],
                }
                for v in findings
                if v.get("FixedVersion") and v.get("Severity") in ("HIGH", "CRITICAL")
            ]
        report["images"][component] = item
        write_json(directory / (component + "-summary.json"), item)
        print(component, json.dumps(item), flush=True)
    write_json(directory / "result.json", report)
    return 0 if all(item["scanner_exit_code"] == 0 for item in report["images"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
