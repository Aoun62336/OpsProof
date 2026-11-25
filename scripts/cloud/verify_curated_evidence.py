"""Bind six sanitized public records to accepted private local trial receipts.

This checks lineage and recorded status, not the truth of arbitrary prose or
permission to publish. A separate human privacy/claims review remains required.
"""

import argparse
import hashlib
import json
from pathlib import Path

from scripts.cloud.build_public_replay import build
from scripts.paths import archive_root, read_artifact

ROOT = Path(__file__).resolve().parents[2]


def verify(cases: list[dict], bindings: dict, *, root: Path = ROOT) -> dict:
    build(cases, require_all=True)
    if set(bindings) != {case["id"] for case in cases}:
        raise ValueError("One exact private trial binding per public case required")
    root = root.resolve()
    bounds = [root / ".runtime" / area / "trials" for area in ("m6", "reliability")]
    if root == ROOT:
        bounds.append(archive_root().resolve() / "m6/trials")
    checked = []
    seen = set()
    for case in cases:
        directory = read_artifact(bindings[case["id"]], root=root).resolve()
        if not any(directory.is_relative_to(bound) for bound in bounds) or directory in seen:
            raise ValueError(
                "Private trial directory must be unique and inside owned trial evidence"
            )
        seen.add(directory)
        source = json.loads((directory / "source.json").read_text(encoding="utf-8"))
        result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        payload = (directory / "independent-result.json").read_bytes()
        proof = json.loads(payload)
        if hashlib.sha256(payload).hexdigest() != case["source_evidence_sha256"]:
            raise ValueError("Public evidence digest differs from the actual independent receipt")
        if (
            source["head"] != case["source_commit"]
            or source["tree_sha256"] != case["source_tree_sha256"]
            or source["dirty"] is not case["source_dirty"]
        ):
            raise ValueError("Public tested-source identity differs from recorded trial identity")
        if (
            case["environment"] != "local-k3d"
            or case["status"] != "succeeded"
            or result["status"] != "SUCCEEDED"
            or result["scenario"] != case["scenario"]
        ):
            raise ValueError("Public scenario, environment or status differs from accepted trial")
        required = ("current_health", "exact_jobs", "original_configuration", "observer_identity")
        receipt = proof.get("verification_receipt", {})
        if (
            proof.get("cleanup_verified") is not True
            or proof.get("hypothesis_verified") is not True
            or any(receipt.get("checks", {}).get(key) is not True for key in required)
        ):
            raise ValueError("Trial lacks complete independent hypothesis/cleanup verification")
        checked.append(
            {
                "id": case["id"],
                "scenario": case["scenario"],
                "evidence_sha256": case["source_evidence_sha256"],
            }
        )
    return {"status": "PRIVATE_LINEAGE_VERIFIED_PUBLIC_REVIEW_REQUIRED", "cases": checked}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--curated-input", type=Path, required=True)
    parser.add_argument("--private-bindings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(
        json.loads(args.curated_input.read_text(encoding="utf-8")),
        json.loads(args.private_bindings.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["status"], len(result["cases"]), "cases")


if __name__ == "__main__":
    main()
