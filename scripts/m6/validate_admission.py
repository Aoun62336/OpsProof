"""Actual local RBAC/admission dry-runs. No fault or application patch is persisted."""

import argparse
import json
from uuid import uuid4

from scripts.m6.local_environment import (
    ROOT,
    resource_preflight,
    source_identity,
    write_json,
)
from scripts.m6.restricted_access import RestrictedAccess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        choices=(
            "worker_saturation",
            "worker_failure",
            "database_connectivity",
            "faulty_release",
            "downstream_latency",
        ),
        required=True,
    )
    parser.add_argument("--capacity-mode", choices=("fixed", "hpa", "keda"))
    args = parser.parse_args()
    directory = ROOT / ".runtime/m6/acceptance/permissions" / ("checks-" + uuid4().hex)
    directory.mkdir(parents=True)
    resources = resource_preflight()
    write_json(directory / "resources.json", resources)
    write_json(directory / "source.json", source_identity())
    result = {
        "passed": False,
        "scenario": args.scenario,
        "capacity_mode": args.capacity_mode,
        "actual_faults_sent": 0,
    }
    if not resources["passed"]:
        result["blockers"] = resources["blockers"]
        write_json(directory / "result.json", result)
        print(json.dumps(result, indent=2))
        return 2
    access = RestrictedAccess(directory, args.scenario, args.capacity_mode)
    try:
        access.setup_kubernetes()
        decisions = access.verify_kubernetes_permissions()
        result.update(
            passed=True,
            kubernetes_decisions=decisions,
            policies=[value["name"] for value in access.boundaries],
        )
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    finally:
        try:
            access.close()
        except Exception as exc:
            result.update(passed=False, cleanup_error=type(exc).__name__)
    write_json(directory / "result.json", result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
