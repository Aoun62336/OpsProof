"""Strict offline cloud price-envelope calculator; it never accesses or provisions AWS.

Inputs are operator-sourced price quotes, not embedded assumptions. This command
cannot authorize a cloud operation. It emits a review-only artifact with the
calculation and caveats intact.
"""

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED = frozenset({
    "eks_control_plane", "ec2_workers", "ebs_storage", "public_ipv4",
    "network_transfer", "nat_gateway", "load_balancer", "cloudwatch",
})


def money(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Boolean is not a valid price")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Non-numeric price or quantity") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Price and quantities must be finite and non-negative")
    return amount


def evaluate(document: dict) -> dict:
    if document.get("currency") != "USD":
        raise ValueError("Use USD price quotes with their source and quote date")
    for field in ("region", "quote_utc", "pricing_source", "credit_eligibility_review"):
        if not isinstance(document.get(field), str) or not document[field].strip():
            raise ValueError(f"Missing required price/credit evidence: {field}")
    try:
        quoted = datetime.fromisoformat(document["quote_utc"].replace("Z", "+00:00"))
        if quoted.tzinfo is None or quoted > datetime.now(UTC):
            raise ValueError("Quote timestamp must be timezone-aware and nonfuture")
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid quote_utc timestamp") from exc
    quote_age_days = (datetime.now(UTC) - quoted).total_seconds() / 86400
    credit_reviewed = document["credit_eligibility_review"].startswith("VERIFIED:")
    price_sources_reviewed = document["pricing_source"].startswith("https://") and "REPLACE" not in document["pricing_source"]
    hours = money(document.get("planned_hours"))
    max_hours = money(document.get("maximum_hours"))
    contingency = money(document.get("contingency_usd"))
    allocation = money(document.get("allocation_usd"))
    if not (0 < hours <= max_hours <= 8):
        raise ValueError("Bounded planned_hours <= maximum_hours <= 8 required")
    if allocation <= 0:
        raise ValueError("Positive budget allocation required")
    prices = document.get("line_items")
    if not isinstance(prices, list):
        raise ValueError("line_items must be an array")
    seen = set()
    report = []
    total = Decimal("0")
    impossible_free = False
    for item in prices:
        if not isinstance(item, dict):
            raise ValueError("Invalid cost line item")
        name = item.get("name")
        if not isinstance(name, str) or name in seen or name not in REQUIRED:
            raise ValueError(f"Duplicate or unknown cost item: {name}")
        seen.add(name)
        unit = item.get("unit")
        if unit not in ("hour", "flat"):
            raise ValueError(f"Unsupported cost unit for {name}")
        rate = money(item.get("rate_usd"))
        units = money(item.get("quantity"))
        if name in {"eks_control_plane", "ec2_workers"} and rate == 0 and units > 0:
            impossible_free = True
        cost = rate * units * (max_hours if unit == "hour" else Decimal(1))
        total += cost
        report.append({"name": name, "unit": unit, "rate_usd": str(rate),
                       "quantity": str(units), "maximum_cost_usd": str(cost)})
    if seen != REQUIRED:
        raise ValueError(f"Missing price components: {sorted(REQUIRED - seen)}")
    ceiling = total + contingency
    return {
        "assessed_utc": datetime.now(UTC).isoformat(),
        "quote_utc": document["quote_utc"],
        "quote_age_days": round(quote_age_days, 2),
        "region": document["region"],
        "pricing_source": document["pricing_source"],
        "credit_eligibility_review": document["credit_eligibility_review"],
        "maximum_hours": str(max_hours),
        "line_items": report,
        "estimate_usd": str(total),
        "contingency_usd": str(contingency),
        "maximum_estimate_usd": str(ceiling),
        "allocation_usd": str(allocation),
        "within_allocation": ceiling <= allocation,
        "credit_review_recorded": credit_reviewed,
        "quote_sources_recorded": price_sources_reviewed,
        "required_billable_rates_nonzero": not impossible_free,
        "quote_fresh_24h": quote_age_days <= 1,
        "cloud_operation_authorized": False,
        "status": "REVIEW_ONLY" if (
            ceiling <= allocation and quote_age_days <= 1 and credit_reviewed
            and price_sources_reviewed and not impossible_free
        ) else "BLOCKED",
        "limitations": [
            "No API prices were fetched; quotations and credit coverage need independent confirmation.",
            "Cloud billing may lag; AWS Budgets is not a hard cap.",
            "Estimate is not authorization to create or retain chargeable resources.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--estimate", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    doc = json.loads(args.estimate.read_text(encoding="utf-8"))
    report = evaluate(doc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: estimated maximum ${report['maximum_estimate_usd']} "
          f"versus allocation ${report['allocation_usd']} (review only)")
    return 0 if report["status"] == "REVIEW_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
