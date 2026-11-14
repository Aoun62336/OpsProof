"""Locked app regressions and source-only security checks; never injects faults."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from uuid import uuid4

from scripts.m5.preflight import ROOT
from scripts.m6.local_environment import source_identity, utc, write_json


def secret_scan(output):
    tools = ROOT / ".runtime/m5/security-tools"
    archive = tools / "gitleaks_8.30.1_windows_x64.zip"
    executable = tools / "gitleaks.exe"
    if os.name != "nt":
        raise RuntimeError("Use the pinned CI secret scanner on non-Windows hosts")
    expected = "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise RuntimeError("Pinned scanner archive checksum mismatch")
    with zipfile.ZipFile(archive) as package:
        if package.read("gitleaks.exe") != executable.read_bytes():
            raise RuntimeError("Installed scanner differs from its verified archive")
    names = (
        subprocess.check_output(
            [
                "git",
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    with tempfile.TemporaryDirectory(prefix="source-scan-", dir=ROOT / ".runtime/m6") as temporary:
        from pathlib import Path

        directory = Path(temporary).resolve()
        assert directory.is_relative_to((ROOT / ".runtime/m6").resolve())
        for name in set(names) - {""}:
            source = (ROOT / name).resolve(strict=True)
            if not source.is_relative_to(ROOT) or source.is_symlink():
                raise ValueError("Source scan refuses external or symlinked files")
            destination = directory / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
        with (output / "secret-scan.log").open("x", encoding="utf-8") as log:
            run = subprocess.run(
                [
                    str(executable),
                    "dir",
                    str(directory),
                    "--redact",
                    "--no-banner",
                    "--report-format",
                    "json",
                    "--report-path",
                    str(output / "secret-scan.json"),
                ],
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=120,
                check=False,
            )
        return run.returncode


def main():
    output = ROOT / ".runtime/m6/acceptance/source" / ("checks-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    identity = source_identity()
    write_json(output / "source-before.json", identity)
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    control = ["uv", "run", "--project", "apps/control-plane", "--locked"]
    demo = ["uv", "run", "--project", "apps/demo-workload", "--locked"]
    checks = [
        (
            "m6-lint",
            [
                *control,
                "ruff",
                "check",
                "--config",
                "apps/control-plane/pyproject.toml",
                "scripts/m6",
            ],
        ),
        (
            "m6-format",
            [
                *control,
                "ruff",
                "format",
                "--check",
                "--config",
                "apps/control-plane/pyproject.toml",
                "scripts/m6",
            ],
        ),
        ("control-lint", [*control, "ruff", "check", "apps/control-plane"]),
        (
            "control-format",
            [*control, "ruff", "format", "--check", "apps/control-plane"],
        ),
        (
            "python-regression",
            [
                *control,
                "python",
                "-m",
                "pytest",
                "apps/control-plane/tests",
                "scripts/m5/tests",
                "scripts/m6/tests",
                "scripts/m7/tests",
                "-q",
            ],
        ),
        ("demo-lint", [*demo, "ruff", "check", "apps/demo-workload"]),
        ("demo-format", [*demo, "ruff", "format", "--check", "apps/demo-workload"]),
        (
            "demo-tests",
            [*demo, "python", "-m", "pytest", "apps/demo-workload/tests", "-q"],
        ),
        ("web-lint", ["npm.cmd", "--prefix", "apps/web", "run", "lint"]),
        ("web-unit", ["npm.cmd", "--prefix", "apps/web", "run", "test"]),
        ("web-build", ["npm.cmd", "--prefix", "apps/web", "run", "build"]),
        ("helm", [shutil.which("python"), "-m", "scripts.m6.validate_charts"]),
        ("k6-syntax", ["node", "--check", "benchmarks/k6/jobs.js"]),
        ("whitespace", ["git", "diff", "--check"]),
    ]
    results = []
    for label, command in checks:
        started = time.monotonic()
        with (output / f"{label}.log").open("x", encoding="utf-8") as log:
            run = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=300,
                check=False,
            )
        results.append(
            {
                "check": label,
                "exit_code": run.returncode,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
        print(label, "PASS" if run.returncode == 0 else "FAIL", flush=True)
    results.append({"check": "source-secret-scan", "exit_code": secret_scan(output)})
    after = source_identity()
    write_json(output / "source-after.json", after)
    same = identity["tree_sha256"] == after["tree_sha256"]
    report = {
        "checked_at": utc(),
        "python": sys.version,
        "results": results,
        "source_unchanged_during_checks": same,
        "passed": same and all(item["exit_code"] == 0 for item in results),
        "scope": (
            "Source/offline gates. SQL skips are verified by the disposable database runner."
        ),
    }
    write_json(output / "result.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
