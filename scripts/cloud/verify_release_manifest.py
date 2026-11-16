"""Validate a reviewed immutable GHCR release record (offline).

This verifies *format and cross-field consistency*, not existence of OCI digests
or authenticity of GitHub attestations. Verify those online separately.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

SHA40 = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
REPO = re.compile(r"[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.-]*\Z")
IMAGE = re.compile(
    r"ghcr\.io/[a-z0-9][a-z0-9_.-]*/[a-z0-9][a-z0-9_.-]*/opsproof-(demo|control|web|edge)@sha256:[a-f0-9]{64}\Z"
)
NAMES = ("demo", "control", "web", "edge")


def validate(record: object) -> dict:
    if not isinstance(record, dict) or set(record) != {
        "source_sha",
        "repository",
        "workflow_run_id",
        "images",
    }:
        raise ValueError("Expected exactly source_sha, repository, workflow_run_id, images")
    if not isinstance(record["source_sha"], str) or not SHA40.fullmatch(record["source_sha"]):
        raise ValueError("Full reviewed source commit required")
    if not isinstance(record["repository"], str) or not REPO.fullmatch(record["repository"]):
        raise ValueError("Lowercase owner/repository required")
    if type(record["workflow_run_id"]) is not int or record["workflow_run_id"] <= 0:
        raise ValueError("Positive GitHub workflow run ID required")
    images = record["images"]
    if not isinstance(images, dict) or set(images) != set(NAMES):
        raise ValueError("Exactly demo/control/web/edge image identities required")
    for role in NAMES:
        uri = images[role]
        if not isinstance(uri, str) or not IMAGE.fullmatch(uri):
            raise ValueError(f"Invalid immutable GHCR image for {role}")
        owner, repo = record["repository"].split("/", 1)
        if not uri.startswith(f"ghcr.io/{owner}/{repo}/opsproof-{role}@"):
            raise ValueError(f"Image owner/repository mismatch for {role}")
        if not DIGEST.fullmatch(uri.split("@", 1)[1]):
            raise ValueError(f"Invalid SHA256 digest for {role}")
    if len(set(images.values())) != len(NAMES):
        raise ValueError("Duplicate image identity")
    return {
        "status": "FORMAT_VALIDATED_NOT_REGISTRY_VERIFIED",
        "source_sha": record["source_sha"],
        "images": images,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    args = p.parse_args()
    result = validate(json.loads(args.input.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
