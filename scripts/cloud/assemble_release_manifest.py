"""Assemble five image receipts from one approved GitHub Actions release run.

Offline consistency checks do not establish registry existence or signature trust.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.cloud.verify_release_manifest import DIGEST, NAMES, validate


def assemble(receipts: list[dict], *, source_sha: str, repository: str, run_id: int) -> dict:
    images: dict[str, str] = {}
    if len(receipts) != len(NAMES):
        raise ValueError("Exactly five image receipts required")
    for receipt in receipts:
        if not isinstance(receipt, dict) or set(receipt) != {
            "role",
            "source_sha",
            "repository",
            "workflow_run_id",
            "digest",
        }:
            raise ValueError("Malformed image receipt")
        role = receipt["role"]
        if role not in NAMES or role in images:
            raise ValueError("Unknown or duplicated image role")
        if (
            receipt["source_sha"] != source_sha
            or receipt["repository"] != repository
            or receipt["workflow_run_id"] != run_id
            or type(receipt["workflow_run_id"]) is not int
        ):
            raise ValueError("Image receipts must come from the same reviewed commit and run")
        digest = receipt["digest"]
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise ValueError("Malformed image digest")
        images[role] = f"ghcr.io/{repository}/opsproof-{role}@{digest}"
    record = {
        "source_sha": source_sha,
        "repository": repository,
        "workflow_run_id": run_id,
        "images": images,
    }
    validate(record)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = sorted(args.receipts.glob("release-*/release-evidence.json"))
    record = assemble(
        [json.loads(path.read_text(encoding="utf-8")) for path in paths],
        source_sha=args.source_sha,
        repository=args.repository.lower(),
        run_id=args.run_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("FIVE_IMAGE_MANIFEST_ASSEMBLED; registry and attestation verification still required")


if __name__ == "__main__":
    main()
