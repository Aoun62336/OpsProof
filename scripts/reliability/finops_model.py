"""Gross illustrative Mumbai cost model from retained official price rows.

No discounts/credits, actual spending, provisioning approval or measured M6
performance/cost improvement is inferred. KEDA alone does not resize EC2 nodes.
"""

import json
from datetime import UTC, datetime
from decimal import Decimal

from scripts.platform.preflight import ROOT
from scripts.reliability.local_environment import utc

D = Decimal


def amount(rate, quantity):
    if D(str(rate)) < 0 or D(str(quantity)) < 0:
        raise ValueError("Costs and quantities cannot be negative")
    return D(str(rate)) * D(str(quantity))


def select(document, category, predicate=lambda _row: True):
    rows = [
        row
        for row in document["selected"].get(category, [])
        if D(row["PricePerUnit"]) > 0
        and row["StartingRange"] == "0"
        and row.get("Currency") == "USD"
        and predicate(row)
    ]
    if len(rows) != 1:
        raise ValueError(f"Ambiguous or missing regional quote: {category}")
    return rows[0]


def model(document):
    if document["region"] != "ap-south-1":
        raise ValueError("Only the explicitly reviewed Mumbai model is supported")
    age = (datetime.now(UTC) - datetime.fromisoformat(document["retrieved_at"])).total_seconds()
    if not 0 <= age <= 86400:
        raise ValueError("Refresh price evidence before using this model")
    hours = D(8)
    quotes = {
        "eks_control_plane": select(document, "eks_standard_control_plane"),
        "ec2_t3_large": select(document, "compute_t3_large_linux"),
        "public_ipv4": select(document, "public_ipv4"),
        "ebs_gp3": select(document, "ebs_gp3_storage"),
        "logs_ingestion": select(document, "cloudwatch_logs_ingest"),
        "logs_storage": select(document, "cloudwatch_logs_storage"),
        "logs_query": select(
            document,
            "cloudwatch_logs_query",
            lambda row: row.get("Group") == "Queried Logs",
        ),
        "internet_egress": select(document, "internet_egress"),
        "cross_az_transfer": select(document, "regional_transfer"),
        "cpu_credit_upper_bound": select(
            document,
            "t3_cpu_credits",
            lambda row: (
                row.get("Operating System") == "Linux" and "of T3 CPU" in row["PriceDescription"]
            ),
        ),
    }
    quantities = {
        "eks_control_plane": hours,
        "ec2_t3_large": hours,
        "public_ipv4": hours,
        "ebs_gp3": D(39) * hours / D(730),
        "logs_ingestion": D(1),
        "logs_storage": D(1) / D(30),
        "logs_query": D("0.25"),
        "internet_egress": D(1),
        "cross_az_transfer": D("0.2"),
        "cpu_credit_upper_bound": D("1.4") * hours,
    }
    lines = []
    for name, row in quotes.items():
        lines.append(
            {
                "category": name,
                "sku": row["SKU"],
                "unit": row["Unit"],
                "usd_per_unit": row["PricePerUnit"],
                "quantity": str(quantities[name]),
                "modeled_usd": str(
                    amount(row["PricePerUnit"], quantities[name]).quantize(D("0.000001"))
                ),
            }
        )
    upper = sum(D(line["modeled_usd"]) for line in lines)
    lower = upper - D(lines[-1]["modeled_usd"])
    return {
        "generated_at": utc(),
        "region": "ap-south-1",
        "currency": "USD",
        "hours": 8,
        "status": "ILLUSTRATIVE_UNAPPROVED_MODEL",
        "lines": lines,
        "gross_usd_without_cpu_credit_overage": str(lower),
        "gross_usd_with_cpu_credit_upper_bound": str(upper),
        "gross_usd_with_20_percent_reserve": str((upper * D("1.2")).quantize(D("0.01"))),
        "actual_spend_usd": None,
        "account_billing_inspected": False,
        "credits_assumed_usd": "0",
        "resources_created": 0,
        "assumptions": [
            "Eight hours: one standard-support EKS cluster, one Linux t3.large, one public IPv4",
            "Thirty GB node disk plus nine GB PVC storage; gp3 730-hour-month proration",
            "One GB standard CloudWatch log ingestion, one-day one-GB retention, 0.25 GB queried",
            "One GB internet export and 0.1 GB cross-AZ traffic billed at both ends",
            "No free-tier, promotional credit, reservation, Savings Plan or tax assumption",
            "T3 credits: zero overage to sustained two-vCPU use above the 0.6-vCPU baseline",
            "No NAT, managed load balancer, snapshots or public hosted zone in this model",
            "M7 must reprice any topology, version-support, instance, storage or exposure change",
        ],
        "fixed_vs_demand": {
            "fixed_worker": "Same single node/control-plane/IPv4 gross infrastructure rate",
            "keda_workers": "Same node rate; Pod replicas change without node autoscaling",
            "measured_performance_improvement": None,
            "limitation": "Nine comparable M6 runs blocked; no workload savings claimed",
        },
    }


def main():
    paths = sorted(
        (ROOT / ".runtime/reliability/acceptance/pricing").glob("prices-*/selected-prices.json"),
        key=lambda path: path.stat().st_mtime,
    )
    source = paths[-1]
    document = json.loads(source.read_text(encoding="utf-8"))
    report = model(document)
    report["pricing_evidence"] = source.relative_to(ROOT).as_posix()
    images = json.loads(
        (ROOT / ".runtime/reliability/acceptance/image-provenance.json").read_text()
    )
    report["local_image_measurements"] = {name: images[name] for name in ("demo", "control", "web")}
    report["optimization_review"] = {
        "existing_multistage_builds_retained": True,
        "locked_production_python_dependencies_retained": True,
        "nonroot_runtime_and_security_features_retained": True,
        "new_dependency_or_dockerfile_reduction_claimed": False,
        "build_time_caveat": "Local cache/changed source; no optimization speedup claimed",
        "comparable_runtime_before_after": "BLOCKED_HOST_MEMORY",
    }
    output = ROOT / ".runtime/reliability/acceptance/finops-analysis.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "gross_usd_without_cpu_credit_overage",
                    "gross_usd_with_cpu_credit_upper_bound",
                    "gross_usd_with_20_percent_reserve",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
