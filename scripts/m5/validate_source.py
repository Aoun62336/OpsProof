"""Run source checks with separate logs, exit codes, and source provenance."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".runtime/m5/acceptance"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    checks = [
        (
            "demo-tests",
            ROOT,
            [
                "uv",
                "run",
                "--project",
                "apps/demo-workload",
                "--locked",
                "pytest",
                "apps/demo-workload/tests",
                "-q",
            ],
        ),
        (
            "control-tests",
            ROOT,
            [
                "uv",
                "run",
                "--project",
                "apps/control-plane",
                "--locked",
                "pytest",
                "apps/control-plane/tests",
                "-q",
            ],
        ),
        (
            "m5-tests",
            ROOT,
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "scripts/m5/tests",
                "-v",
            ],
        ),
        ("helm-contracts", ROOT, [sys.executable, "scripts/m5/validate_charts.py"]),
        *[
            (f"web-{task}", ROOT / "apps/web", [npm, "run", task])
            for task in ("lint", "test", "build")
        ],
        ("diff-check", ROOT, ["git", "diff", "--check"]),
    ]
    results = []
    for name, cwd, args in checks:
        log = OUT / f"{name}.log"
        started = datetime.now(UTC).isoformat()
        with log.open("w", encoding="utf-8") as handle:
            try:
                run = subprocess.run(
                    args,
                    cwd=cwd,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    timeout=300,
                    check=False,
                )
                code = run.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                handle.write(type(exc).__name__ + "\n")
                code = -1
        results.append(
            {
                "check": name,
                "command": args,
                "exit_code": code,
                "started_utc": started,
                "log": log.name,
            }
        )
        print(f"{name}: exit={code}", flush=True)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(set(paths))
        if name and (ROOT / name).is_file()
    }
    record = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "base_commit": head,
        "working_tree": "local; file hashes identify tested source",
        "file_sha256": hashes,
        "checks": results,
        "passed": all(row["exit_code"] == 0 for row in results),
        "scope": "source checks only; no browser, cluster, CI-hosted or live milestone acceptance",
    }
    (OUT / "source-validation.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
