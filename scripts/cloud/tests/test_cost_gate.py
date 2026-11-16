"""Offline pricing guard negative-path tests."""

import unittest
from datetime import UTC, datetime

from scripts.cloud.cost_gate import REQUIRED, evaluate


def quote():
    return {
        "region": "ap-south-1",
        "currency": "USD",
        "quote_utc": datetime.now(UTC).isoformat(),
        "pricing_source": "https://aws.amazon.com/eks/pricing/; manually reviewed line items",
        "credit_eligibility_review": (
            "VERIFIED: operator checked current credits and eligible services"
        ),
        "planned_hours": 2,
        "maximum_hours": 3,
        "contingency_usd": 3,
        "allocation_usd": 20,
        "line_items": [
            {"name": name, "unit": "hour", "rate_usd": 0.1, "quantity": 1}
            for name in sorted(REQUIRED)
        ],
    }


class CostGateTests(unittest.TestCase):
    def test_review_only_never_authorizes(self):
        result = evaluate(quote())
        self.assertFalse(result["cloud_operation_authorized"])
        self.assertEqual(result["status"], "REVIEW_ONLY")

    def test_missing_component_rejected(self):
        data = quote()
        data["line_items"].pop()
        with self.assertRaises(ValueError):
            evaluate(data)

    def test_cost_exceeding_budget_blocks(self):
        data = quote()
        data["line_items"][0]["rate_usd"] = 100
        self.assertEqual(evaluate(data)["status"], "BLOCKED")

    def test_placeholder_credit_and_free_eks_are_blocked(self):
        data = quote()
        data["credit_eligibility_review"] = "NOT VERIFIED"
        self.assertEqual(evaluate(data)["status"], "BLOCKED")
        data = quote()
        for item in data["line_items"]:
            if item["name"] == "eks_control_plane":
                item["rate_usd"] = 0
        self.assertEqual(evaluate(data)["status"], "BLOCKED")

    def test_negative_and_nan_rejected(self):
        for bad in (-1, "NaN", "Infinity"):
            data = quote()
            data["line_items"][0]["rate_usd"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                evaluate(data)

    def test_budget_and_hours_required(self):
        for field, value in (("maximum_hours", 24), ("planned_hours", 0), ("allocation_usd", 0)):
            data = quote()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                evaluate(data)


if __name__ == "__main__":
    unittest.main()
