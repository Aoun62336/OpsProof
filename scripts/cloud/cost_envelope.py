"""Review-only M7 gross-cost envelope; cannot authorize cloud provisioning.

Input units are explicit flat allowances or hourly rate * quantity * approved hours.
Rates MUST come from current account/region-specific AWS pricing; no guessed zeros.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

# All charges must be reviewed, even if a line item's measured usage is tiny.
REQUIRED = frozenset(
    {
        "eks",
        "two_workers",
        "nat_hours",
        "nat_gb",
        "alb_hours",
        "alb_lcu",
        "api_gateway_requests",
        "rds_multi_az",
        "rds_storage",
        "ebs_root_and_pvcs",
        "public_ipv4",
        "secrets_manager",
        "cloudwatch",
        "s3_backend",
        "inter_az_transfer",
        "internet_egress",
        "tax_and_other",
    }
)


def amount(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Booleans are not quantities")
    try:
        x = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Amounts must be finite nonnegative decimals") from exc
    if not x.is_finite() or x < 0:
        raise ValueError("Amounts must be finite nonnegative decimals")
    return x


def review(record: dict) -> dict:
    if not isinstance(record, dict):
        raise ValueError("Expected a pricing record")
    if record.get("region") != "ap-south-1" or record.get("currency") != "USD":
        raise ValueError("Require USD prices for ap-south-1")
    timestamp = datetime.fromisoformat(str(record.get("quoted_utc", "")))
    if timestamp.utcoffset() is None:
        raise ValueError("Price quote must have an explicit UTC offset")
    age_hours = (datetime.now(UTC) - timestamp).total_seconds() / 3600
    if age_hours < 0 or age_hours > 24:
        raise ValueError("Price quote must have UTC offset and be within 24 hours")
    if not str(record.get("source_url", "")).startswith("https://"):
        raise ValueError("Source URL for price evidence required")
    if not str(record.get("credit_eligibility_review", "")).startswith("VERIFIED:"):
        raise ValueError("Account-specific credit applicability must be reviewed")
    hours = amount(record.get("max_hours"))
    ceiling = amount(record.get("gross_ceiling_usd"))
    allowance = amount(record.get("operating_allocation_usd"))
    contingency = amount(record.get("contingency_usd"))
    if not (1 <= hours <= 12 and 0 < allowance <= 15 and allowance + 25 <= ceiling <= 40):
        raise ValueError("Review requires <=12 hours, <=$15 operating allocation and >=$25 reserve")
    items = record.get("items")
    if (
        not isinstance(items, list)
        or any(not isinstance(i, dict) or not isinstance(i.get("name"), str) for i in items)
        or set(i.get("name") for i in items) != REQUIRED
        or len(items) != len(REQUIRED)
    ):
        raise ValueError(f"Exactly these line items required: {', '.join(sorted(REQUIRED))}")
    total = Decimal("0")
    for item in items:
        if item.get("unit") not in {"hour", "flat"}:
            raise ValueError("Only hour or flat cost units supported")
        rate = amount(item.get("usd_per_unit"))
        count = amount(item.get("quantity"))
        if (
            item["name"] in {"eks", "two_workers", "nat_hours", "alb_hours", "rds_multi_az"}
            and rate * count <= 0
        ):
            raise ValueError("Known billable resources cannot have zero rates or counts")
        expected_count = {
            "eks": 1,
            "two_workers": 2,
            "nat_hours": 1,
            "alb_hours": 1,
            "rds_multi_az": 1,
        }.get(item["name"])
        if expected_count is not None and (item["unit"] != "hour" or count != expected_count):
            raise ValueError("Core hourly quantities must match the approved topology")
        total += rate * count * (hours if item["unit"] == "hour" else 1)
    estimated = total + contingency
    return {
        "status": "REVIEW_ONLY" if estimated <= allowance else "BLOCKED",
        "max_hours": str(hours),
        "estimate_usd": str(total),
        "contingency_usd": str(contingency),
        "estimated_max_usd": str(estimated),
        "operating_allocation_usd": str(allowance),
        "gross_ceiling_usd": str(ceiling),
        "authorization_to_apply": False,
        "limitations": [
            "Real prices and credit eligibility come from the user's AWS account "
            "and approved quote.",
            "AWS Budgets does not automatically stop resources; "
            "manual safety timer/teardown required.",
            "An estimate cannot guarantee a maximum bill or that a service is covered by credits.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    a = parser.parse_args()
    report = review(json.loads(a.input.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(report["status"], "max reviewed estimate", report["estimated_max_usd"], "USD")
    return 0 if report["status"] == "REVIEW_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
