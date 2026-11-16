"""Strong offline artifact checks, explicitly NOT a live six-scenario certification.

Requires source-linked named artifacts and verifies their bytes against a SHA256
inventory; cannot certify the truthfulness of the experiment's own assertions.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

REQUIRED = frozenset(
    {
        "worker_saturation",
        "faulty_release",
        "database_connectivity",
        "worker_failure",
        "downstream_latency",
        "misleading_evidence",
    }
)


def audit(document: dict, root: Path) -> dict:
    if not isinstance(document, dict) or set(document) != {"source_sha", "scenarios"}:
        raise ValueError("Expected exact source provenance and six scenario evidence records")
    if not isinstance(document["source_sha"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", document["source_sha"]
    ):
        raise ValueError("Full source SHA-1 required")
    records = document["scenarios"]
    if not isinstance(records, list) or len(records) != len(REQUIRED):
        raise ValueError("Six scenario records required")
    seen = set()
    used = set()
    reviewed = []
    root = root.resolve(strict=True)
    for item in records:
        if not isinstance(item, dict) or set(item) != {"scenario", "artifacts"}:
            raise ValueError("Invalid scenario manifest entry")
        scenario = item["scenario"]
        if scenario in seen or scenario not in REQUIRED:
            raise ValueError("Unknown or duplicate scenario")
        seen.add(scenario)
        refs = item["artifacts"]
        if not isinstance(refs, list) or len(refs) < 2:
            raise ValueError("At least two raw independently reviewable artifacts per scenario")
        matched = 0
        for artifact in refs:
            if not isinstance(artifact, dict) or set(artifact) != {"path", "sha256"}:
                raise ValueError("Invalid artifact descriptor")
            relative = artifact["path"]
            if not isinstance(relative, str) or not relative.startswith(".runtime/m6/"):
                raise ValueError("Artifacts must remain inside the ignored M6 runtime tree")
            candidate = root / relative
            if candidate.is_symlink() or any(
                parent.is_symlink() for parent in candidate.parents if parent != root
            ):
                raise ValueError("Symlinked evidence paths are forbidden")
            p = candidate.resolve(strict=True)
            if not p.is_relative_to(root / ".runtime" / "m6"):
                raise ValueError("Artifact path escapes bounded evidence tree")
            if p.is_symlink() or not p.is_file() or p.stat().st_size == 0:
                raise ValueError("Missing, symlinked or empty evidence file")
            if relative in used:
                raise ValueError("Cannot reuse one raw artifact across unrelated scenarios")
            used.add(relative)
            with p.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != artifact["sha256"]:
                raise ValueError(f"Hash mismatch for evidence in {scenario}")
            matched += 1
        reviewed.append({"scenario": scenario, "hashed_artifacts": matched})
    return {
        "artifact_integrity": "PASSED",
        "scenarios_with_artifacts": sorted(seen),
        "reviewed_artifacts": reviewed,
        "live_acceptance": "NOT_CERTIFIED_BY_OFFLINE_AUDIT",
        "operator_acceptance_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.input.read_text(encoding="utf-8")), args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Evidence hashes verified. Actual scenarios still require independent review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
