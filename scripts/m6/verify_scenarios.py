"""Fail-closed audit of six independent scenario evidence records.

Checks completeness and linkage; cannot substitute for inspecting real cluster
logs, source revision, Prometheus/Tempo/Loki artifacts or outcomes themselves.
"""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

if __package__:
    from .contracts import CATALOG, Scenario
else:
    from contracts import CATALOG, Scenario

REQUIRED_FIELDS = (
    "scenario", "source_revision", "image_digest", "run_id", "environment",
    "injected_at_utc", "verified_at_utc", "injection_mechanism",
    "independent_verification", "cleanup_verified", "evidence_files",
)


def validate(records: list[dict]) -> dict:
    if len(records) != len(CATALOG):
        raise ValueError("Exactly six distinct scenario records required")
    seen = set()
    failures = []
    for record in records:
        for field in REQUIRED_FIELDS:
            if field not in record:
                raise ValueError(f"Missing scenario evidence field: {field}")
        try:
            scenario = Scenario(record["scenario"])
        except ValueError as exc:
            raise ValueError("Unknown scenario ID") from exc
        if scenario in seen:
            raise ValueError("Duplicate scenario record")
        seen.add(scenario)
        if record.get("environment") != "k3d-opsproof":
            failures.append(f"{scenario}: not local scoped evidence")
        if not isinstance(record.get("source_revision"), str) or not re.fullmatch(
            r"[a-f0-9]{40}", record["source_revision"]
        ):
            failures.append(f"{scenario}: invalid source Git SHA")
        if not isinstance(record.get("image_digest"), str) or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", record["image_digest"]
        ):
            failures.append(f"{scenario}: invalid image digest")
        if not isinstance(record.get("run_id"), str) or not record["run_id"].strip():
            failures.append(f"{scenario}: missing run ID")
        if record.get("independent_verification") is not True:
            failures.append(f"{scenario}: independent verification not passed")
        if record.get("cleanup_verified") is not True:
            failures.append(f"{scenario}: cleanup not proven")
        evidence_files = record.get("evidence_files")
        if (not isinstance(evidence_files, list) or len(evidence_files) < 2
                or any(not isinstance(item, str) or not item.strip() for item in evidence_files)):
            failures.append(f"{scenario}: insufficient raw evidence references")
        try:
            started = datetime.fromisoformat(record["injected_at_utc"].replace("Z", "+00:00"))
            verified = datetime.fromisoformat(record["verified_at_utc"].replace("Z", "+00:00"))
            if started.tzinfo is None or verified.tzinfo is None or verified <= started:
                raise ValueError("Wrong time order")
        except (TypeError, ValueError):
            failures.append(f"{scenario}: timestamps invalid")
        if record["injection_mechanism"] != CATALOG[scenario].mechanism:
            failures.append(f"{scenario}: injection mechanism inconsistent with catalog")
    if seen != set(CATALOG):
        raise ValueError("Scenario catalog coverage incomplete")
    return {"metadata_consistent": not failures,
            "independent_runtime_acceptance": "NOT_VERIFIED_BY_THIS_SCRIPT",
            "covered": sorted(str(x) for x in seen),
            "failures": failures,
            "limitations": (
                "Checks self-reported metadata only. "
                "Independent manual/live evidence audit mandatory."
            )}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = json.loads(args.input.read_text(encoding="utf-8"))
    report = validate(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["metadata_consistent"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
