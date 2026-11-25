"""Prove two exact upstream fixes before producing scoped OpenVEX status=fixed.

The Go pseudo-version sorts below Tempo 2.x despite containing both fixes.
This is source-fix verification, not a risk waiver. Raw findings are retained.
New images, revisions, CVEs or failed ancestry checks receive no resolution.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

IMAGE = "cleanstart/grafana@sha256:f7d47c4ebb4b632bfb5e7d4c78b8a126e739cd6e733aeda15b720d93a4247eef"
REVISION = "bcfe9f230c1de0f79cfd2110b38062e0f41c81e9"
VERSION = "v1.5.1-0.20260910130453-bcfe9f230c1d"
MODULE = "github.com/grafana/tempo"
TARGET = "usr/share/grafana/data/plugins-bundled/tempo/gpx_grafana-tempo-datasource_linux_amd64"
# Public upstream advisory references, not local reachability assumptions:
# https://github.com/advisories/GHSA-p4r4-xvrq-gvmc
# https://github.com/advisories/GHSA-ffqx-q65f-36jf
FIXES = {
    "CVE-2026-21728": "650eb1985a0776789c8564122990f588a742356f",
    "CVE-2026-28377": "bb8ca663db34a0980c9758b40d918fda3b4dbec3",
}


def upstream_comparison(fix):
    url = "https://api.github.com/repos/grafana/tempo/compare/" + fix + "..." + REVISION
    request = Request(url, headers={"User-Agent": "OpsProof-upstream-fix-verification"})
    with urlopen(request, timeout=20) as response:
        raw = response.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("Upstream comparison exceeds bound")
    data = json.loads(raw)
    return {
        "url": url,
        "status": data["status"],
        "base": data["base_commit"]["sha"],
        "merge_base": data["merge_base_commit"]["sha"],
        "behind_by": data["behind_by"],
        "head": data["commits"][-1]["sha"],
    }


def verified_fixed(report, image, *, compare=upstream_comparison):
    metadata = report.get("Metadata", {})
    vendor = image == IMAGE and IMAGE in metadata.get("RepoDigests", [])
    labels = metadata.get("ImageConfig", {}).get("config", {}).get("Labels", {})
    identities = [
        metadata.get("ImageID"),
        *metadata.get("RepoDigests", []),
        *metadata.get("RepoTags", []),
    ]
    artifact = (
        image in identities
        and labels.get("org.opsproof.grafana-source") == IMAGE
        and metadata.get("OS", {}).get("Family") == "wolfi"
        and str(metadata.get("ImageID", "")).startswith("sha256:")
    )
    if not (vendor or artifact):
        raise ValueError("Exact reviewed image/report binding required")
    statements = []
    receipts = {}
    for result in report.get("Results", []):
        for finding in result.get("Vulnerabilities", []):
            cve = finding["VulnerabilityID"]
            if cve not in FIXES:
                continue
            if (
                result.get("Target") != TARGET
                or finding.get("PkgName") != MODULE
                or finding.get("InstalledVersion") != VERSION
                or finding.get("PkgIdentifier", {}).get("PURL")
                != "pkg:golang/" + MODULE + "@" + VERSION
            ):
                raise ValueError("Finding differs from the reviewed binary/module revision")
            proof = compare(FIXES[cve])
            if (
                proof["status"] != "ahead"
                or proof["base"] != FIXES[cve]
                or proof["merge_base"] != FIXES[cve]
                or proof["behind_by"] != 0
                or proof["head"] != REVISION
            ):
                raise ValueError("Upstream fix ancestry was not established")
            receipts[cve] = proof
            statements.append(
                {
                    "vulnerability": {"name": cve},
                    "status": "fixed",
                    "products": [{"@id": finding["PkgIdentifier"]["PURL"]}],
                    "action_statement": "The embedded revision contains upstream fix "
                    + FIXES[cve]
                    + "; verified for exact image "
                    + image,
                }
            )
    return {
        "@context": "https://openvex.dev/ns/v0.2.0",
        "@id": "urn:sha256:" + hashlib.sha256(image.encode()).hexdigest(),
        "author": "OpsProof source-fix verification",
        "role": "Document Creator",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": 1,
        "statements": statements,
    }, receipts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document, receipts = verified_fixed(
        json.loads(args.report.read_text(encoding="utf-8")), args.image
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    args.output.with_suffix(".proof.json").write_text(
        json.dumps(receipts, indent=2) + "\n", encoding="utf-8"
    )
    print("Verified upstream fixes:", ", ".join(sorted(receipts)))


if __name__ == "__main__":
    main()
