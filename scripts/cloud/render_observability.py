"""Render the existing six telemetry services for private EKS storage; no apply."""

import argparse
import json
from pathlib import Path

from scripts.platform.observability import ROOT, render


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    images = json.loads((ROOT / "observability/images.lock.json").read_text(encoding="utf-8"))
    result = render(images, storage_class="opsproof-ebs-gp3", cloud_profile=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("PRIVATE_TELEMETRY_RENDERED; metrics, log and trace acceptance still required")


if __name__ == "__main__":
    main()
