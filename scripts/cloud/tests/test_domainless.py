"""Source-only M7 security and cost tests. No AWS calls or changes."""

import json
import unittest
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.cloud.audit_domainless import audit
from scripts.cloud.build_external_secret import build
from scripts.cloud.cost_envelope import REQUIRED, review

ROOT = Path(__file__).resolve().parents[3]


class DesignTests(unittest.TestCase):
    def test_static_audit(self):
        self.assertEqual(audit(ROOT)["status"], "STATIC_CONTRACT_PASS_NOT_RUNTIME_ACCEPTANCE")

    def test_fails_public_alb_change(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [
                "infra/terraform/platform/variables.tf",
                "infra/terraform/platform/gate.tf",
                "infra/terraform/platform/network.tf",
                "infra/terraform/platform/eks.tf",
                "infra/terraform/platform/database.tf",
                "infra/terraform/public-edge/main.tf",
                "infra/helm/opsproof-edge/templates/edge.yaml",
                "apps/edge-proof/nginx.conf",
                "apps/edge-proof/index.html",
                "scripts/cloud/build_external_secret.py",
                "infra/helm/opsproof-dependencies/values-control-eks.yaml",
                "infra/helm/opsproof-dependencies/values-demo-eks.yaml",
                "infra/k8s/cloud/gp3-storageclass.yaml",
                "infra/helm/opsproof-services/templates/_helpers.tpl",
                "infra/helm/opsproof-services/templates/migration.yaml",
            ]
            for p in paths:
                dest = root / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((ROOT / p).read_bytes())
            ingress = root / "infra/helm/opsproof-edge/templates/edge.yaml"
            ingress.write_text(
                ingress.read_text().replace("scheme: internal", "scheme: internet-facing")
            )
            with self.assertRaisesRegex(ValueError, "ALB ingress must be internal"):
                audit(root)


class CredentialTests(unittest.TestCase):
    def test_external_secret_is_credential_free(self):
        doc = build(
            "arn:aws:secretsmanager:ap-south-1:123456789012:secret:my-db-secret-x",
            host="db.example.ap-south-1.rds.amazonaws.com",
        )
        self.assertEqual(doc["kind"], "ExternalSecret")
        target = doc["spec"]["target"]
        self.assertEqual(target["name"], "opsproof-control-rds-app-connection")
        self.assertEqual(set(target["template"]["data"]), {"OPSPROOF_CONTROL_DATABASE_URL"})
        db_url = target["template"]["data"]["OPSPROOF_CONTROL_DATABASE_URL"]
        self.assertTrue(db_url.startswith("postgresql://"))
        self.assertNotIn("postgresql+psycopg://", db_url)
        self.assertIn("sslmode=verify-full", db_url)
        self.assertNotIn("my_password", json.dumps(doc))

    def test_reject_unapproved_region(self):
        with self.assertRaises(ValueError):
            build(
                "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-db-secret-x",
                host="db.example.ap-south-1.rds.amazonaws.com",
            )


class SourceIntegrationTests(unittest.TestCase):
    def test_ebs_storageclass_is_consistent(self):
        name = "opsproof-ebs-gp3"
        self.assertIn(f"name: {name}", (ROOT / "infra/k8s/cloud/gp3-storageclass.yaml").read_text())
        for chart_values in ("values-demo-eks.yaml", "values-control-eks.yaml"):
            text = (ROOT / "infra/helm/opsproof-dependencies" / chart_values).read_text()
            self.assertEqual(
                text.count(f"storageClassName: {name}"),
                2 if chart_values.startswith("values-demo") else 1,
            )

    def test_control_and_migration_load_rds_override(self):
        for f in ("templates/_helpers.tpl", "templates/migration.yaml"):
            src = (ROOT / "infra/helm/opsproof-services" / f).read_text()
            self.assertIn(
                "opsproof-control-rds-"
                + ("app" if f.startswith("templates/_helpers") else "migration")
                + "-connection",
                src,
            )
            self.assertIn("opsproof-control-runtime", src)


class CostTests(unittest.TestCase):
    def setUp(self):
        self.doc = {
            "region": "ap-south-1",
            "currency": "USD",
            "quoted_utc": datetime.now(UTC).isoformat(),
            "source_url": "https://aws.amazon.com/pricing/",
            "credit_eligibility_review": ("VERIFIED: offline fixture; real user approval required"),
            "max_hours": 12,
            "gross_ceiling_usd": 40,
            "operating_allocation_usd": 15,
            "contingency_usd": 4,
            "items": [
                {
                    "name": name,
                    "unit": "hour"
                    if name
                    in {
                        "eks",
                        "two_workers",
                        "nat_hours",
                        "alb_hours",
                        "rds_multi_az",
                        "public_ipv4",
                    }
                    else "flat",
                    "usd_per_unit": "0.01",
                    "quantity": 2 if name == "two_workers" else 1,
                }
                for name in sorted(REQUIRED)
            ],
        }

    def test_bounded_review_not_approval(self):
        out = review(self.doc)
        self.assertEqual(out["status"], "REVIEW_ONLY")
        self.assertFalse(out["authorization_to_apply"])

    def test_block_expensive_estimate(self):
        self.doc["items"][0]["usd_per_unit"] = 100
        self.assertEqual(review(self.doc)["status"], "BLOCKED")

    def test_reject_credit_guess(self):
        self.doc["credit_eligibility_review"] = "assume free"
        with self.assertRaises(ValueError):
            review(self.doc)

    def test_reject_thirteenth_hour(self):
        self.doc["max_hours"] = 13
        with self.assertRaises(ValueError):
            review(self.doc)

    def test_reject_nan(self):
        self.doc["items"][0]["usd_per_unit"] = "NaN"
        with self.assertRaises(ValueError):
            review(self.doc)

    def test_reject_missing_service(self):
        self.doc["items"].pop()
        with self.assertRaises(ValueError):
            review(self.doc)

    def test_reject_duplicate_service(self):
        self.doc["items"].append(deepcopy(self.doc["items"][0]))
        with self.assertRaises(ValueError):
            review(self.doc)

    def test_reject_invalid_amounts_and_unsafe_bounds(self):
        for value in (-1, "NaN", "Infinity", True):
            data = deepcopy(self.doc)
            data["items"][0]["usd_per_unit"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(data)
        for key, value in (
            ("max_hours", 0),
            ("gross_ceiling_usd", 41),
            ("operating_allocation_usd", 0),
        ):
            data = deepcopy(self.doc)
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                review(data)

    def test_reject_zero_rate_and_understated_worker_count(self):
        for field, value in (("usd_per_unit", 0), ("quantity", 1), ("unit", "flat")):
            data = deepcopy(self.doc)
            item = next(x for x in data["items"] if x["name"] == "two_workers")
            item[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                review(data)

    def test_reject_naive_stale_or_future_quote(self):
        for value in ("2026-11-01T00:00:00Z", "2099-01-01T00:00:00Z", datetime.now().isoformat()):
            data = deepcopy(self.doc)
            data["quoted_utc"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                review(data)


class TeardownTests(unittest.TestCase):
    def test_requires_full_resource_inventory(self):
        from scripts.cloud.audit_aws_cleanup import validate_inventory

        with self.assertRaises(ValueError):
            validate_inventory({"region": "ap-south-1", "account_id": "123456789012"})

    def test_rejects_different_cluster(self):
        from scripts.cloud.audit_aws_cleanup import validate_inventory

        with self.assertRaises(ValueError):
            validate_inventory(
                {
                    "region": "ap-south-1",
                    "account_id": "123456789012",
                    "eks_cluster": "another-company-production",
                    "rds_db_identifier": "opsproof-cloud-control",
                    "nat_gateway_id": "nat-12345678",
                    "alb_arn": (
                        "arn:aws:elasticloadbalancing:ap-south-1:123456789012:"
                        "loadbalancer/app/abc/123"
                    ),
                    "http_api_id": "abc1234567",
                    "ebs_volume_ids": ["vol-12345678"],
                }
            )


class TerraformPlanTests(unittest.TestCase):
    def test_create_only_bound_nodes_db_nat(self):
        from scripts.cloud.verify_domainless_plan import check

        def r(kind, after=None):
            return {"type": kind, "change": {"actions": ["create"], "after": after or {}}}

        sample = {
            "resource_changes": [
                r("aws_vpc"),
                *[r("aws_subnet") for _ in range(4)],
                r("aws_nat_gateway"),
                r(
                    "aws_eks_cluster",
                    {
                        "vpc_config": [
                            {
                                "public_access_cidrs": ["203.0.113.9/32"],
                                "endpoint_private_access": True,
                            }
                        ]
                    },
                ),
                *[
                    r(
                        "aws_eks_node_group",
                        {
                            "instance_types": ["m7i-flex.large"],
                            "scaling_config": [{"min_size": 1, "max_size": 1, "desired_size": 1}],
                        },
                    )
                    for _ in range(2)
                ],
                r(
                    "aws_db_instance",
                    {
                        "publicly_accessible": False,
                        "multi_az": True,
                        "manage_master_user_password": True,
                        "instance_class": "db.t4g.small",
                    },
                ),
                r("aws_iam_role_policy_attachment"),
            ]
        }
        self.assertEqual(check(sample)["status"], "SHAPE_ONLY_NOT_AUTHORIZED_FOR_APPLY")
        sample["resource_changes"][5]["change"]["actions"] = ["delete", "create"]
        with self.assertRaisesRegex(ValueError, "CREATE-only"):
            check(sample)

    def test_reject_three_worker_nodes(self):
        from scripts.cloud.verify_domainless_plan import check

        with self.assertRaises(ValueError):
            check(
                {
                    "resource_changes": [
                        {"type": "aws_eks_node_group", "change": {"actions": ["create"]}}
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
