"""Read-only, bounded collection of real demo queue and deployment state.

Uses explicit local k3d kubeconfig and exact known resources. Captures
multiple non-atomic observations with UTC timestamps; missing metrics are
errors, not healthy zeros. Does not inject faults or authorize recovery.
"""

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

if __package__:
    from .contracts import assert_isolated_k3d_api, assert_local_scope
else:
    from contracts import assert_isolated_k3d_api, assert_local_scope

DEMO_STATS_URL = "http://127.0.0.1:18088/api/v1/stats"
GROUP = "opsproof-workers"
STREAM = "opsproof:jobs"


def parse_group(raw: object) -> dict:
    if not isinstance(raw, list):
        raise ValueError("Redis XINFO GROUPS must return a JSON array")
    entries = [row for row in raw if isinstance(row, dict) and row.get("name") == GROUP]
    if len(entries) != 1:
        raise ValueError("Expected exactly one configured consumer group")
    row = entries[0]
    lag, pending = row.get("lag"), row.get("pending")
    # Redis may return null lag if it cannot calculate lag. That is UNKNOWN.
    if (
        lag is not None
        and (type(lag) is not int or lag < 0)
        or type(pending) is not int
        or pending < 0
    ):
        raise ValueError("Missing or invalid Redis queue metrics")
    return {
        "stream": STREAM,
        "group": GROUP,
        "lag": lag,
        "pending": pending,
        "consumers": row.get("consumers"),
        "lag_known": lag is not None,
    }


def collect(kubeconfig: Path) -> dict:
    kubeconfig = kubeconfig.resolve(strict=True)
    prefix = ["kubectl", "--kubeconfig", str(kubeconfig), "--context", "k3d-opsproof"]

    def kubectl(arguments):
        proc = subprocess.run(
            [*prefix, *arguments],
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        if proc.returncode:
            raise RuntimeError("Read-only Kubernetes query failed")
        return json.loads(proc.stdout)

    # Read the effective kubeconfig before issuing any workload-level query.
    local_config = kubectl(["config", "view", "--minify", "-o", "json"])
    assert_isolated_k3d_api(local_config["clusters"][0]["cluster"]["server"])
    start = datetime.now(UTC)
    groups = kubectl(
        [
            "exec",
            "-n",
            "opsproof-demo",
            "demo-deps-redis-0",
            "--",
            "redis-cli",
            "--json",
            "XINFO",
            "GROUPS",
            STREAM,
        ]
    )
    queue = parse_group(groups)
    worker = kubectl(["get", "deployment", "demo-worker", "-n", "opsproof-demo", "-o", "json"])
    deployments = kubectl(["get", "deployments", "-n", "opsproof-demo", "-o", "json"])
    apis = [item for item in deployments["items"] if item["metadata"]["name"] == "demo-api"]
    if len(apis) > 1:
        raise ValueError("Ambiguous demo API Deployment")
    api_kind = "Deployment" if apis else "Rollout"
    api = (
        apis[0]
        if apis
        else kubectl(["get", "rollout", "demo-api", "-n", "opsproof-demo", "-o", "json"])
    )
    with urlopen(DEMO_STATS_URL, timeout=5) as resp:
        if resp.status != 200:
            raise RuntimeError("Demo state API unavailable")
        stats = json.load(resp)
    for state in ("queued", "processing", "completed", "failed"):
        if type(stats.get(state)) is not int or stats[state] < 0:
            raise ValueError(f"Missing or invalid durable state: {state}")
    end = datetime.now(UTC)
    return {
        "observed_from_utc": start.isoformat(),
        "observed_until_utc": end.isoformat(),
        "observation_span_seconds": round((end - start).total_seconds(), 3),
        "local_kubernetes_context": "k3d-opsproof",
        "queue": queue,
        "replicas": {
            "api_kind": api_kind,
            "worker_desired": worker["spec"]["replicas"],
            "worker_ready": worker["status"].get("readyReplicas", 0),
            "api_desired": api["spec"]["replicas"],
            "api_ready": api["status"].get("readyReplicas", 0),
        },
        "durable_jobs": {k: stats[k] for k in ("queued", "processing", "completed", "failed")},
        "limitations": (
            "Sequential non-atomic observations; corroborate timestamps "
            "and telemetry before diagnosis"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kubeconfig", type=Path, default=Path(".runtime/platform/kubeconfig.yaml")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert_local_scope(kubeconfig=args.kubeconfig, context="k3d-opsproof", mutation=False)
    report = collect(args.kubeconfig)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
