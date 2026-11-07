"""Read-only resource gate. Never contacts the active Kubernetes cluster."""

import ctypes
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GIB = 1024**3


def command(args):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=30, check=False
        )
        return {
            "exit_code": result.returncode,
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exit_code": -1, "output": "", "error": type(exc).__name__}


def memory_available():
    if os.name == "nt":

        class Memory(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong)
                for name in (
                    "total",
                    "available",
                    "page",
                    "page_available",
                    "virtual",
                    "virtual_available",
                    "extended",
                )
            ]

        memory = Memory()
        memory.length = ctypes.sizeof(memory)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
            raise OSError("Memory measurement failed")
        return memory.available
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    raise OSError("Available memory unavailable")


def blockers(memory, disk, docker_memory, running):
    reasons = []
    if memory < 5 * GIB:
        reasons.append("Host free RAM below 5 GiB")
    if disk < 15 * GIB:
        reasons.append("Workspace disk free below 15 GiB")
    if docker_memory < 5 * GIB:
        reasons.append("Docker memory below 5 GiB or unavailable")
    if any(
        "opsproof" in name.lower() and not name.startswith("k3d-") for name in running
    ):
        reasons.append(
            "OpsProof containers already running; inspect Compose before migration"
        )
    return reasons


def collect():
    checks = {
        name: command(args)
        for name, args in {
            "source": ["git", "rev-parse", "HEAD"],
            "dirty": ["git", "status", "--short"],
            "docker_version": ["docker", "--version"],
            "docker_memory": ["docker", "info", "--format", "{{.MemTotal}}"],
            "containers": ["docker", "ps", "--format", "{{.Names}}"],
            "docker_disk": ["docker", "system", "df"],
            "k3d_version": ["k3d", "version"],
            "clusters": ["k3d", "cluster", "list", "-o", "json"],
            "kubectl_version": ["kubectl", "version", "--client", "-o", "json"],
            "helm_version": ["helm", "version", "--short"],
        }.items()
    }
    memory = memory_available()
    disk = shutil.disk_usage(ROOT).free
    docker_memory = checks["docker_memory"]["output"]
    reasons = blockers(
        memory,
        disk,
        int(docker_memory) if docker_memory.isdigit() else 0,
        checks["containers"]["output"].splitlines(),
    )
    reasons.extend(
        f"Command failed: {name}"
        for name, value in checks.items()
        if value["exit_code"] != 0
    )
    return {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "host_free_bytes": memory,
        "disk_free_bytes": disk,
        "minimum_host_free_bytes": 5 * GIB,
        "minimum_disk_free_bytes": 15 * GIB,
        "checks": checks,
        "blockers": reasons,
        "passed": not reasons,
    }


def main():
    record = collect()
    target = ROOT / ".runtime/m5/acceptance/preflight.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in record.items() if key != "checks"}, indent=2
        )
    )
    print(f"Evidence: {target}")
    return 0 if record["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
