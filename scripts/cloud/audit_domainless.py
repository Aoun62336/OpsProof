"""Independent source-contract audit for the temporary domainless AWS edge.

Checks safety-invariant text in the generated files. These are NOT Terraform,
Kubernetes, IAM, CloudFront or AWS runtime validations. Fail closed on drift.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


def audit(root: Path) -> dict:
    files = {
        "variables": "infra/terraform/platform/variables.tf",
        "gate": "infra/terraform/platform/gate.tf",
        "network": "infra/terraform/platform/network.tf",
        "eks": "infra/terraform/platform/eks.tf",
        "rds": "infra/terraform/platform/database.tf",
        "edge": "infra/terraform/public-edge/main.tf",
        "ingress": "infra/helm/opsproof-edge/templates/edge.yaml",
        "nginx": "apps/edge-proof/nginx.conf",
        "html": "apps/edge-proof/index.html",
        "rds_secret": "scripts/cloud/build_external_secret.py",
        "control_values": "infra/helm/opsproof-dependencies/values-control-eks.yaml",
        "demo_values": "infra/helm/opsproof-dependencies/values-demo-eks.yaml",
        "storageclass": "infra/k8s/cloud/gp3-storageclass.yaml",
        "service_env": "infra/helm/opsproof-services/templates/_helpers.tpl",
        "migrate_env": "infra/helm/opsproof-services/templates/migration.yaml",
    }
    sources = {name: (root / path).read_text(encoding="utf-8") for name, path in files.items()}
    # Native Terraform formatting aligns assignments; text guards ignore that layout.
    for name in ("variables", "gate", "network", "eks", "rds", "edge"):
        sources[name] = re.sub(r"\s+", " ", sources[name])
    errors: list[str] = []

    def require(why: str, test: bool) -> None:
        if not test:
            errors.append(why)

    require(
        "paid resources must default disabled",
        bool(
            re.search(
                r'variable "enable_paid_resources"\s*\{\s*type\s*=\s*bool\s*default\s*=\s*false',
                sources["variables"],
            )
        ),
    )
    require(
        "approval requires exact account and spending bounds",
        all(
            s in sources["gate"]
            for s in [
                "approval_acknowledgement",
                "expected_account_id",
                "gross_budget_usd",
                "maximum_approved_hours",
            ]
        ),
    )
    require(
        "exactly one NAT Gateway in controlled scope",
        'resource "aws_nat_gateway" "single"' in sources["network"]
        and "count = var.enable_paid_resources ? 1 : 0" in sources["network"],
    )
    require(
        "private subnets cannot automatically receive public IPs",
        sources["network"].count("map_public_ip_on_launch = false") == 2,
    )
    require(
        "each private AZ has NAT egress route",
        'resource "aws_route" "private_egress"' in sources["network"],
    )
    require(
        "node groups must use private subnets",
        "subnet_ids = [aws_subnet.private[count.index].id]" in sources["eks"],
    )
    require(
        "node count must be two AZ-specific groups",
        'resource "aws_eks_node_group" "zone"' in sources["eks"]
        and "count = var.enable_paid_resources ? 2 : 0" in sources["eks"],
    )
    require(
        "operator API must not be globally reachable",
        "public_access_cidrs = [var.operator_public_cidr]" in sources["eks"],
    )
    require(
        "VPC CNI NetworkPolicy must be opt-in and explicit",
        'enableNetworkPolicy = "true"' in sources["eks"],
    )
    require(
        "RDS must be Multi-AZ and not internet-exposed",
        "multi_az = true" in sources["rds"] and "publicly_accessible = false" in sources["rds"],
    )
    require(
        "RDS password must not be stored in Terraform",
        "manage_master_user_password = true" in sources["rds"]
        and not re.search(r"(?m)^\s*password\s*=", sources["rds"]),
    )
    require(
        "API Gateway must provide managed TLS 1.2",
        'resource "aws_apigatewayv2_api"' in sources["edge"]
        and 'protocol_type = "HTTP"' in sources["edge"],
    )
    require(
        "API Gateway must use VPC Link",
        'resource "aws_apigatewayv2_vpc_link"' in sources["edge"]
        and 'connection_type = "VPC_LINK"' in sources["edge"],
    )
    require(
        "origin must explicitly state HTTP and no end-to-end TLS",
        'output "private_alb_origin_tls" { value = false }' in sources["edge"],
    )
    require(
        "only read-only GET routes allowed publicly",
        'route_key = "GET /"' in sources["edge"]
        and 'route_key = "GET /healthz"' in sources["edge"]
        and "ANY /" not in sources["edge"],
    )
    require(
        "ALB ingress must be internal",
        "alb.ingress.kubernetes.io/scheme: internal" in sources["ingress"],
    )
    require(
        "public edge must never proxy an API",
        not any(x in sources["nginx"] for x in ["proxy_pass", "api/v1", "auth_request"]),
    )
    require("static page must identify its isolation", "OPSPROOF_EDGE_READ_ONLY" in sources["html"])
    require(
        "no secret values in public static page",
        not any(x in sources["html"].lower() for x in ["api_key=", "bearer ", "postgresql://"]),
    )
    require(
        "RDS must use native psycopg-compatible scheme",
        bool(
            re.search(r"[\"']postgresql://\{\{ \.username \| urlquery \}\}", sources["rds_secret"])
        )
        and "postgresql+psycopg://" not in sources["rds_secret"],
    )
    require(
        "RDS integration must not overwrite complete runtime Secret",
        'target="opsproof-control-rds-app-connection"' in sources["rds_secret"]
        and '"name": "opsproof-control-runtime"' not in sources["rds_secret"],
    )
    require(
        "storage class must match demo and control values",
        all(
            "storageClassName: opsproof-ebs-gp3" in sources[k]
            for k in ("control_values", "demo_values")
        )
        and "name: opsproof-ebs-gp3" in sources["storageclass"],
    )
    require(
        "control Pods must load RDS connection after runtime",
        "- secretRef: {name: opsproof-control-rds-app-connection}" in sources["service_env"],
    )
    require(
        "migration must use RDS connection secret",
        "- secretRef: {name: opsproof-control-rds-migration-connection}" in sources["migrate_env"],
    )
    require(
        "ESO must restrict master secret to ephemeral bootstrap",
        "bootstrap_master_secret_access" in sources["rds"],
    )
    require(
        "application Pods must not consume migration credentials",
        "opsproof-control-rds-migration-connection" not in sources["service_env"],
    )
    require(
        "migration Job must not consume application credentials",
        "opsproof-control-rds-app-connection" not in sources["migrate_env"],
    )
    if errors:
        raise ValueError("\n".join(errors))
    return {
        "status": "STATIC_CONTRACT_PASS_NOT_RUNTIME_ACCEPTANCE",
        "checks": 25,
        "files": len(files),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True, type=Path)
    result = audit(p.parse_args().root)
    print(result)


if __name__ == "__main__":
    main()
