"""Fail-closed source-independent structural audit of Terraform's real JSON CREATE plan.

This is NOT an AWS cost approval, security audit, or permission to apply. Requires
`terraform show -json <saved.plan>` after a fully reviewed plan execution.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
from collections import Counter
from pathlib import Path

ALLOWED = frozenset(
    {
        "terraform_data",
        "aws_vpc",
        "aws_subnet",
        "aws_internet_gateway",
        "aws_route_table",
        "aws_route",
        "aws_route_table_association",
        "aws_eip",
        "aws_nat_gateway",
        "aws_vpc_endpoint",
        "aws_security_group",
        "aws_vpc_security_group_ingress_rule",
        "aws_vpc_security_group_egress_rule",
        "aws_iam_role",
        "aws_iam_role_policy",
        "aws_iam_role_policy_attachment",
        "aws_iam_policy",
        "aws_eks_cluster",
        "aws_eks_access_entry",
        "aws_eks_access_policy_association",
        "aws_eks_node_group",
        "aws_eks_addon",
        "aws_eks_pod_identity_association",
        "aws_cloudwatch_log_group",
        "aws_db_parameter_group",
        "aws_db_subnet_group",
        "aws_db_instance",
    }
)
EXACT = {
    "aws_vpc": 1,
    "aws_subnet": 4,
    "aws_nat_gateway": 1,
    "aws_eks_cluster": 1,
    "aws_eks_node_group": 2,
    "aws_db_instance": 1,
}


def check(plan: dict) -> dict:
    if not isinstance(plan, dict) or not isinstance(plan.get("resource_changes"), list):
        raise ValueError("Requires terraform show -json with resource_changes")
    changes = plan["resource_changes"]
    counts = Counter()
    for item in changes:
        if item.get("mode") == "data":
            if item.get("change", {}).get("actions") not in (["read"], ["no-op"]):
                raise ValueError(f"Unexpected data action: {item.get('address')}")
            continue
        kind = item.get("type")
        actions = item.get("change", {}).get("actions")
        if kind not in ALLOWED:
            raise ValueError(f"Unapproved Terraform kind {kind}: {item.get('address')}")
        if actions != ["create"]:
            raise ValueError(f"Not an initial CREATE-only plan: {item.get('address')}: {actions}")
        counts[kind] += 1
        after = item.get("change", {}).get("after") or {}
        if kind == "aws_nat_gateway":
            if after.get("connectivity_type") not in (None, "public"):
                raise ValueError("NAT must be reviewed public zonal NAT")
        if kind == "aws_eks_node_group":
            sc = after.get("scaling_config") or []
            if len(sc) != 1 or any(
                sc[0].get(k) != 1 for k in ("min_size", "max_size", "desired_size")
            ):
                raise ValueError("Each worker nodegroup must remain exactly one node")
            if after.get("instance_types") != ["m7i-flex.large"]:
                raise ValueError("Unapproved worker instance type")
        if kind == "aws_db_instance":
            if after.get("publicly_accessible") is not False or after.get("multi_az") is not True:
                raise ValueError("Control RDS must be private and Multi-AZ")
            if after.get("manage_master_user_password") is not True:
                raise ValueError("RDS must own password generation")
            if after.get("instance_class") != "db.t4g.small":
                raise ValueError("Unapproved RDS size")
        if kind == "aws_eks_cluster":
            vcs = after.get("vpc_config") or []
            if len(vcs) != 1:
                raise ValueError("Unexpected EKS network configuration")
            cfg = vcs[0]
            cidrs = cfg.get("public_access_cidrs") or []
            if len(cidrs) != 1 or not isinstance(cidrs[0], str):
                raise ValueError("Missing single operator EKS CIDR")
            try:
                net = ipaddress.ip_network(cidrs[0], strict=True)
            except ValueError as exc:
                raise ValueError("Invalid operator EKS CIDR") from exc
            if net.version != 4 or net.prefixlen != 32 or net.is_loopback or net.is_unspecified:
                raise ValueError("EKS endpoint must be restricted to single public IPv4 /32")
            if cfg.get("endpoint_private_access") is not True:
                raise ValueError("EKS private API access must remain enabled")
    for kind, expected in EXACT.items():
        if counts[kind] != expected:
            raise ValueError(f"Unexpected {kind} count {counts[kind]}; expected {expected}")
    if counts["aws_iam_role_policy_attachment"] == 0:
        raise ValueError("Missing IAM role attachments")
    return {
        "status": "SHAPE_ONLY_NOT_AUTHORIZED_FOR_APPLY",
        "counts": dict(sorted(counts.items())),
        "limitations": [
            "Does not review IAM policy content, provider-managed resources, billing, "
            "account quota or user approvals."
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan-json", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(check(json.loads(args.plan_json.read_text(encoding="utf-8"))), indent=2))


if __name__ == "__main__":
    main()
