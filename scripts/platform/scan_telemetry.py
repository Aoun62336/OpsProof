"""Complete telemetry inventories and strict HIGH/CRITICAL gate, including unfixed CVEs."""

import argparse
import json
import subprocess
from pathlib import Path

from scripts.platform.telemetry_images import runtime_images
from scripts.platform.telemetry_security import verified_fixed

SCRATCH_COLLECTOR = (
    "otel/opentelemetry-collector-contrib@sha256:"
    "e40d61f10c9a617cca1ffd1be4d7e2b3a4b0f0001798ff07e58cabe82e618cea"
)


def require_inventory(report, image=None):
    """A supported OS feed and package list are mandatory, not just a green total."""
    metadata = report.get("Metadata", {})
    # The exact official Collector Dockerfile uses FROM scratch: certificates,
    # config and one static Go binary, with no distribution packages to scan.
    # https://github.com/open-telemetry/opentelemetry-collector-releases/blob/v0.165.0/distributions/otelcol-contrib/Dockerfile
    if (
        image == SCRATCH_COLLECTOR
        and image in metadata.get("RepoDigests", [])
        and metadata.get("OS") is None
        and any(
            r.get("Type") == "gobinary"
            and r.get("Target") == "otelcol-contrib"
            and r.get("Packages")
            for r in report.get("Results", [])
        )
    ):
        return
    if (metadata.get("OS") or {}).get("Family") in (None, "", "none", "unknown"):
        raise RuntimeError("Unsupported OS advisory feed; the image is not release-qualified")
    if not any(
        r.get("Class") == "os-pkgs" and r.get("Packages") for r in report.get("Results", [])
    ):
        raise RuntimeError("Missing OS package inventory")


def scan(output: Path, trivy: str, grafana_image: str, *, only_grafana=False):
    output.mkdir(parents=True, exist_ok=False)
    images = runtime_images(grafana_image)
    if only_grafana:
        images = {"grafana": grafana_image}
    outcomes = {}
    (output / "result.json").write_text(json.dumps({"passed": False, "images": outcomes}))
    for name, image in images.items():
        raw = output / f"{name}-raw.json"
        common = [
            trivy,
            "image",
            "--image-src",
            "docker" if name == "grafana" else "remote",
            "--scanners",
            "vuln",
            "--detection-priority",
            "comprehensive",
            "--list-all-pkgs",
            "--ignore-unfixed=false",
            "--timeout",
            "10m",
        ]
        with (output / f"{name}.log").open("w") as log:
            subprocess.run(
                [*common, "--format", "json", "--output", str(raw), image],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=660,
                check=True,
            )
        report = json.loads(raw.read_text())
        require_inventory(report, image)
        if not any(r.get("Packages") for r in report.get("Results", [])):
            raise RuntimeError("No package inventory: " + name)
        metadata = report.get("Metadata", {})
        identities = [
            metadata.get("ImageID"),
            *metadata.get("RepoDigests", []),
            *metadata.get("RepoTags", []),
        ]
        if image not in identities:
            raise RuntimeError("Scan identity mismatch: " + name)
        vex = []
        if name == "grafana":
            document, receipts = verified_fixed(report, image)
            path = output / "grafana-fixed.openvex.json"
            path.write_text(json.dumps(document, indent=2))
            path.with_suffix(".proof.json").write_text(json.dumps(receipts, indent=2))
            vex = ["--vex", str(path)]
        subprocess.run(
            [
                trivy,
                "convert",
                "--format",
                "cyclonedx",
                "--output",
                str(output / f"{name}.cdx.json"),
                str(raw),
            ],
            timeout=90,
            check=True,
        )
        with (output / f"{name}-gate.log").open("w") as log:
            gate = subprocess.run(
                [
                    *common,
                    *vex,
                    "--severity",
                    "HIGH,CRITICAL",
                    "--exit-code",
                    "1",
                    "--format",
                    "json",
                    "--output",
                    str(output / f"{name}-gate.json"),
                    image,
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=660,
                check=False,
            )
        outcomes[name] = {"image": image, "passed": gate.returncode == 0}
        complete = len(outcomes) == len(images) and all(
            item["passed"] for item in outcomes.values()
        )
        (output / "result.json").write_text(
            json.dumps({"passed": complete, "images": outcomes}, indent=2)
        )
        if gate.returncode:
            raise RuntimeError("Telemetry vulnerability release gate failed: " + name)
        print("PASS: complete inventory and strict vulnerability gate:", name, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--trivy", default="trivy")
    parser.add_argument("--grafana-image", required=True)
    parser.add_argument("--only-grafana", action="store_true")
    args = parser.parse_args()
    scan(args.output.resolve(), args.trivy, args.grafana_image, only_grafana=args.only_grafana)


if __name__ == "__main__":
    main()
