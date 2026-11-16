"""Read-only audit of exact identities recorded during the temporary AWS window.

Discovery, identity capture and deletion are separate operations. Missing IDs or
failed API calls are never proof of cleanup. A result is not a billing assertion.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

# kind: (service, operation, ID argument, exact absence code, response collection)
LOOKUPS = {
    "eks_cluster": ("eks", "describe-cluster", "--name", "ResourceNotFoundException", None),
    "rds_instance": (
        "rds",
        "describe-db-instances",
        "--db-instance-identifier",
        "DBInstanceNotFound",
        None,
    ),
    "nat_gateway": (
        "ec2",
        "describe-nat-gateways",
        "--nat-gateway-ids",
        "InvalidNatGatewayID.NotFound",
        "NatGateways",
    ),
    "load_balancer": (
        "elbv2",
        "describe-load-balancers",
        "--load-balancer-arns",
        "LoadBalancerNotFound",
        None,
    ),
    "target_group": (
        "elbv2",
        "describe-target-groups",
        "--target-group-arns",
        "TargetGroupNotFound",
        None,
    ),
    "http_api": ("apigatewayv2", "get-api", "--api-id", "NotFoundException", None),
    "vpc_link": ("apigatewayv2", "get-vpc-link", "--vpc-link-id", "NotFoundException", None),
    "volume": ("ec2", "describe-volumes", "--volume-ids", "InvalidVolume.NotFound", None),
    "eip": ("ec2", "describe-addresses", "--allocation-ids", "InvalidAllocationID.NotFound", None),
    "eni": (
        "ec2",
        "describe-network-interfaces",
        "--network-interface-ids",
        "InvalidNetworkInterfaceID.NotFound",
        None,
    ),
    "vpc": ("ec2", "describe-vpcs", "--vpc-ids", "InvalidVpcID.NotFound", None),
    "security_group": (
        "ec2",
        "describe-security-groups",
        "--group-ids",
        "InvalidGroup.NotFound",
        None,
    ),
    "snapshot": ("ec2", "describe-snapshots", "--snapshot-ids", "InvalidSnapshot.NotFound", None),
    "rds_snapshot": (
        "rds",
        "describe-db-snapshots",
        "--db-snapshot-identifier",
        "DBSnapshotNotFound",
        None,
    ),
    "db_subnet_group": (
        "rds",
        "describe-db-subnet-groups",
        "--db-subnet-group-name",
        "DBSubnetGroupNotFoundFault",
        None,
    ),
    "db_parameter_group": (
        "rds",
        "describe-db-parameter-groups",
        "--db-parameter-group-name",
        "DBParameterGroupNotFound",
        None,
    ),
    "secret": (
        "secretsmanager",
        "describe-secret",
        "--secret-id",
        "ResourceNotFoundException",
        None,
    ),
    "log_group": ("logs", "describe-log-groups", "--log-group-name-prefix", None, "logGroups"),
    "iam_role": ("iam", "get-role", "--role-name", "NoSuchEntity", None),
    "iam_policy": ("iam", "get-policy", "--policy-arn", "NoSuchEntity", None),
    "auto_scaling_group": (
        "autoscaling",
        "describe-auto-scaling-groups",
        "--auto-scaling-group-names",
        None,
        "AutoScalingGroups",
    ),
    "s3_bucket": ("s3api", "head-bucket", "--bucket", "404", None),
}
ERROR_CODE = re.compile(r"^An error occurred \(([A-Za-z0-9_.-]+)\) when calling ", re.MULTILINE)
PREFIXES = {
    "nat_gateway": "nat",
    "volume": "vol",
    "eip": "eipalloc",
    "eni": "eni",
    "vpc": "vpc",
    "security_group": "sg",
    "snapshot": "snap",
}
ARN_SERVICES = {
    "load_balancer": "elasticloadbalancing",
    "target_group": "elasticloadbalancing",
    "secret": "secretsmanager",
    "iam_policy": "iam",
}


def validate_inventory(data: dict) -> None:
    if not isinstance(data, dict) or data.get("schema") != 2:
        raise ValueError("Exact identity capture schema 2 required")
    if data.get("region") != "ap-south-1" or not re.fullmatch(
        r"[0-9]{12}", str(data.get("account_id", ""))
    ):
        raise ValueError("Exact Mumbai region and AWS account required")
    if type(data.get("capture_complete")) is not bool:
        raise ValueError("Explicit complete/partial capture status required")
    resources = data.get("resources")
    if not isinstance(resources, dict) or set(resources) != set(LOOKUPS):
        raise ValueError("Every resource category must be recorded, including explicit empty lists")
    seen = set()
    for kind, ids in resources.items():
        if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids):
            raise ValueError("Resource identities must be nonempty strings in lists")
        for identity in ids:
            if (kind, identity) in seen:
                raise ValueError("Duplicate resource identity")
            seen.add((kind, identity))
            if kind in PREFIXES and not re.fullmatch(PREFIXES[kind] + r"-[a-f0-9]{8,17}", identity):
                raise ValueError("Malformed EC2 identity")
            if kind in ARN_SERVICES:
                region = "" if kind == "iam_policy" else "ap-south-1"
                prefix = f"arn:aws:{ARN_SERVICES[kind]}:{region}:{data['account_id']}:"
                if not identity.startswith(prefix) or len(identity) <= len(prefix):
                    raise ValueError("Foreign-account or malformed resource ARN")
            if kind == "eks_cluster" and identity != "opsproof-cloud":
                raise ValueError("Unexpected EKS cluster")
            if kind == "rds_instance" and identity != "opsproof-cloud-control":
                raise ValueError("Unexpected RDS instance")
            if kind in {"http_api", "vpc_link"} and not re.fullmatch(r"[a-z0-9]{6,20}", identity):
                raise ValueError("Malformed API Gateway identity")
            if kind in {
                "iam_role",
                "db_subnet_group",
                "db_parameter_group",
            } and not identity.startswith("opsproof-cloud-"):
                raise ValueError("Unrelated resource name")
            if kind == "s3_bucket" and not re.fullmatch(r"opsproof-[a-z0-9.-]{3,54}", identity):
                raise ValueError("Unrelated backend bucket")
            if kind == "log_group" and not (
                identity.startswith("/aws/eks/opsproof-cloud/")
                or identity.startswith("/opsproof-cloud/")
            ):
                raise ValueError("Unrelated log group")
    if not seen:
        raise ValueError("An empty identity capture is not cleanup evidence")


def aws(profile: str, region: str, parts: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["aws", "--profile", profile, "--region", region, "--output", "json", *parts],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def lookup(profile: str, region: str, kind: str, identity: str) -> dict:
    service, operation, argument, missing_code, collection = LOOKUPS[kind]
    try:
        status, stdout, stderr = aws(profile, region, [service, operation, argument, identity])
        if status:
            code = ERROR_CODE.search(stderr)
            # A diagnostic that merely mentions NotFound must never pass.
            if missing_code is not None and code and code.group(1) == missing_code:
                return {"status": "NOT_FOUND"}
            return {
                "status": "UNVERIFIED_ERROR",
                "error_code": code.group(1) if code else "UNPARSED_CLI_ERROR",
            }
        if collection:
            rows = json.loads(stdout).get(collection)
            if not isinstance(rows, list):
                raise ValueError("Missing response collection")
            if kind == "log_group":
                rows = [row for row in rows if row.get("logGroupName") == identity]
            if kind == "nat_gateway":
                rows = [row for row in rows if row.get("State") != "deleted"]
            return {"status": "PRESENT" if rows else "NOT_FOUND"}
        return {"status": "PRESENT"}
    except OSError, subprocess.TimeoutExpired, ValueError, TypeError:
        return {"status": "UNVERIFIED_ERROR", "error_code": "LOOKUP_INCOMPLETE"}


def audit(profile: str, record: dict) -> dict:
    validate_inventory(record)
    if not profile:
        raise ValueError("Explicit AWS profile required")
    rc, stdout, _stderr = aws(profile, record["region"], ["sts", "get-caller-identity"])
    if rc or json.loads(stdout).get("Account") != record["account_id"]:
        raise RuntimeError("Wrong AWS account or caller identity unavailable")
    results = {
        kind: {identity: lookup(profile, record["region"], kind, identity) for identity in ids}
        for kind, ids in record["resources"].items()
    }
    absent = all(
        row["status"] == "NOT_FOUND" for category in results.values() for row in category.values()
    )
    return {
        "checked_utc": datetime.now(UTC).isoformat(),
        "region": record["region"],
        "account_id_last4": record["account_id"][-4:],
        "capture_complete": record["capture_complete"],
        "results": results,
        "status": "EXACT_IDENTITIES_NOT_FOUND"
        if absent and record["capture_complete"]
        else "RESOURCES_REMAIN_OR_UNVERIFIED",
        "limitations": [
            "Recorded identities only; inspect discovery results for untracked objects.",
            "Include backend buckets after approved state export and versioned-object deletion.",
            "Pending deletion is PRESENT. Review billing, backups and other Regions separately.",
            "Destroy and this report cannot guarantee a zero bill or an enforced spending cap.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--expected-resource-ids", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.profile, json.loads(args.expected_resource_ids.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["status"])
    return 0 if report["status"] == "EXACT_IDENTITIES_NOT_FOUND" else 2


if __name__ == "__main__":
    raise SystemExit(main())
