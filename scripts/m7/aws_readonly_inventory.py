"""Explicit read-only, scoped AWS inventory. NO create/update/delete operations.

Completeness requires the manual AWS Console/billing cross-check documented in
M7_CLOUD_RUNBOOK.md; tagging APIs alone do not enumerate all chargeable objects.
"""
import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

COMMANDS = {
    "identity": ["sts", "get-caller-identity"],
    "tagged_resources": ["resourcegroupstaggingapi", "get-resources", "--tag-filters", "Key=Project,Values=OpsProof", "Key=Environment,Values=temporary-verification"],
    "eks": ["eks", "list-clusters"],
    "nat_gateways": ["ec2", "describe-nat-gateways", "--filter", "Name=tag:Project,Values=OpsProof"],
    "instances": ["ec2", "describe-instances", "--filters", "Name=tag:Project,Values=OpsProof"],
    "volumes": ["ec2", "describe-volumes", "--filters", "Name=tag:Project,Values=OpsProof"],
    "elastic_ips": ["ec2", "describe-addresses", "--filters", "Name=tag:Project,Values=OpsProof"],
    "vpcs": ["ec2", "describe-vpcs", "--filters", "Name=tag:Project,Values=OpsProof"],
}


def inventory(*, profile: str, region: str, expected_account: str) -> dict:
    if not profile or not region or not (len(expected_account) == 12 and expected_account.isascii() and expected_account.isdigit()):
        raise ValueError("Explicit profile, region and twelve-digit account required")
    results = {}
    for name, args in COMMANDS.items():
        cmd = ["aws", "--profile", profile, "--region", region, "--output", "json", *args]
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=45, check=False)
        if proc.returncode:
            raise RuntimeError(f"Read-only inventory call {name} failed; inspect AWS CLI profile/permissions")
        results[name] = json.loads(proc.stdout)
        if name == "identity" and results[name].get("Account") != expected_account:
            raise RuntimeError("AWS account mismatch; stop inventory")
    return {
        "collected_utc": datetime.now(UTC).isoformat(), "region": region,
        "expected_account_last4": expected_account[-4:],
        "inventory": {name: value for name, value in results.items() if name != "identity"},
        "scope": "Read-only, selected Region, tag-oriented inventory. NOT exhaustive cleanup verification.",
        "manual_review_required": [
            "Un/incorrectly tagged ELB, EBS snapshots, EIP, CloudWatch, IAM and S3 backend",
            "Other AWS Regions and pricing/credit visibility",
            "AWS Cost Explorer and account billing after settlement",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--expected-account", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = inventory(profile=args.profile, region=args.region, expected_account=args.expected_account)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Read-only inventory saved locally. Manual cleanup/cost review still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
