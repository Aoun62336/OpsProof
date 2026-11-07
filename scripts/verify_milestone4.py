"""Check recorded successful recovery and preserve its authenticated API evidence."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from verify_control import request

OUTPUT = Path(".runtime/milestone4-verification.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-id", type=UUID)
    args = parser.parse_args()
    code, records = request("GET", "/api/v1/recoveries")
    assert code == 200 and isinstance(records, list), "Recovery API unavailable"
    succeeded = [
        r
        for r in records
        if r["status"] == "succeeded"
        and (args.recovery_id is None or r["id"] == str(args.recovery_id))
    ]
    if not succeeded:
        raise RuntimeError("No independently verified successful recovery recorded")
    recovery = succeeded[0]
    code, events = request("GET", f"/api/v1/recoveries/{recovery['id']}/events")
    assert code == 200
    required = [
        "proposed",
        "approved",
        "attempt_started",
        "action_acknowledged",
        "succeeded",
    ]
    positions = [
        next(i for i, e in enumerate(events) if e["type"] == kind) for kind in required
    ]
    assert positions == sorted(positions), "Recovery audit sequence invalid"
    result = recovery["result"]
    assert result["actuator"] in ("applied", "replayed")
    assert result["worker_hold_cleared"] is True
    assert result["job_ids"] and len(result["job_ids"]) == len(result["job_statuses"])
    assert all(status == "completed" for status in result["job_statuses"])
    assert result["experiment_status"] == "succeeded"
    assert result["incident_status"] == "resolved"
    code, experiment = request("GET", f"/api/v1/experiments/{recovery['run_id']}")
    assert code == 200 and experiment["status"] == "succeeded"
    assert set(experiment["result"]["job_ids"]) == set(result["job_ids"])
    code, incident_events = request(
        "GET", f"/api/v1/incidents/{recovery['incident_fingerprint']}/events"
    )
    assert code == 200 and any(e["status"] == "resolved" for e in incident_events)
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "verified_at": datetime.now(UTC).isoformat(),
                "recovery": recovery,
                "events": events,
                "experiment": experiment,
                "incident_events": incident_events,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"PASS: recorded recovery, exact jobs, experiment and audit trail; evidence: {OUTPUT}"
    )


if __name__ == "__main__":
    main()
