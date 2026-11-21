"""Offline contracts for the four formerly missing M7 deployment workstreams.

Not live EKS/RDS acceptance. Negative cases fail closed where appropriate.
"""

from __future__ import annotations

import base64
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.cloud.build_db_role_jobs import build as role_job
from scripts.cloud.build_external_secret import build_all
from scripts.cloud.check_workflow_pins import scan
from scripts.cloud.generate_redis_security import build_for
from scripts.cloud.install_controllers import loaded
from scripts.cloud.provision_db_credentials import plan_names

ROOT = Path(__file__).resolve().parents[3]
DIGEST = "a" * 64
APP_ARN = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:opsproof-cloud-db-app-123456"
MIG_ARN = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:opsproof-cloud-db-migration-123456"
MST_ARN = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:rds!db-abc123"
HOST = "opsproof-cloud-control.abcd.ap-south-1.rds.amazonaws.com"


class RdsContractTests(unittest.TestCase):
    def test_distinct_users_and_no_password_manifest(self):
        docs = build_all(master_arn=MST_ARN, app_arn=APP_ARN, migrate_arn=MIG_ARN, host=HOST)
        self.assertEqual(len(docs), 4)
        names = [x["spec"]["target"]["name"] for x in docs]
        self.assertEqual(len(set(names)), 4)
        self.assertIn("opsproof-control-rds-app-connection", names)
        self.assertIn("opsproof-control-rds-migration-connection", names)
        for doc in docs:
            self.assertNotIn("SUPERSECRET", json.dumps(doc))
        text = (ROOT / "infra/helm/opsproof-services/templates/_helpers.tpl").read_text()
        self.assertIn(names[0], text)
        self.assertNotIn(names[1], text)
        mig = (ROOT / "infra/helm/opsproof-services/templates/migration.yaml").read_text()
        self.assertIn(names[1], mig)
        self.assertNotIn(names[0], mig)

    def test_reject_other_account_or_invalid_endpoint(self):
        with self.assertRaises(ValueError):
            build_all(
                master_arn=MST_ARN.replace("123456789012", "000000000000"),
                app_arn=APP_ARN,
                migrate_arn=MIG_ARN,
                host=HOST,
            )
        with self.assertRaises(ValueError):
            build_all(master_arn=MST_ARN, app_arn=APP_ARN, migrate_arn=MIG_ARN, host="example.org")

    def test_db_secret_names_scoped(self):
        self.assertEqual(
            plan_names("opsproof-cloud"), ("opsproof-cloud-db-app", "opsproof-cloud-db-migration")
        )
        with self.assertRaises(ValueError):
            plan_names("production")

    def test_bootstrap_job_master_only_there(self):
        image = f"ghcr.io/owner/repo/opsproof-control@sha256:{DIGEST}"
        a = role_job(image, "bootstrap")
        b = role_job(image, "verify")
        self.assertIn("rds-bootstrap", json.dumps(a))
        self.assertNotIn("rds-bootstrap", json.dumps(b))
        for job in (a, b):
            self.assertFalse(job["spec"]["template"]["spec"]["automountServiceAccountToken"])
            self.assertEqual(job["spec"]["backoffLimit"], 0)
        with self.assertRaises(ValueError):
            role_job("ghcr.io/owner/repo:latest", "bootstrap")

    def test_database_sql_denies_app_create(self):
        script = (ROOT / "apps/control-plane/src/opsproof_control/db_bootstrap.py").read_text()
        self.assertIn("REVOKE CREATE ON SCHEMA public FROM PUBLIC", script)
        self.assertIn("has_schema_privilege(current_user", script)
        permissions = (
            ROOT / "apps/control-plane/src/opsproof_control/database_permissions.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ALTER DEFAULT PRIVILEGES", permissions)
        self.assertNotIn("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES", permissions)
        tf = (ROOT / "infra/terraform/platform/database.tf").read_text()
        self.assertIn("bootstrap_master_secret_access", tf)
        self.assertIn("opsproof-cloud-db-app-*", tf)
        self.assertIn("opsproof-cloud-db-migration-*", tf)


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL not present on this test runner")
class RedisSecurityTests(unittest.TestCase):
    def test_real_cert_san_and_private_url(self):
        for role in ("demo", "control"):
            docs = build_for(role)
            self.assertEqual(len(docs), 3)
            tls = docs[0]
            data = {k: base64.b64decode(v).decode() for k, v in tls["data"].items()}
            self.assertIn("BEGIN CERTIFICATE", data["tls.crt"])
            self.assertIn("BEGIN PRIVATE KEY", data["tls.key"])
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "tls.crt"
                p.write_text(data["tls.crt"])
                import subprocess

                cert = subprocess.run(
                    ["openssl", "x509", "-in", str(p), "-noout", "-ext", "subjectAltName"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
                self.assertIn(f"{role}-deps-redis.opsproof-{role}.svc.cluster.local", cert)
                ca = Path(tmp) / "ca.crt"
                ca.write_text(data["ca.crt"], encoding="utf-8")
                subprocess.run(
                    [
                        "openssl",
                        "verify",
                        "-x509_strict",
                        "-verify_hostname",
                        f"{role}-deps-redis.opsproof-{role}.svc.cluster.local",
                        "-CAfile",
                        str(ca),
                        str(p),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )

            env_key = "OPSPROOF_REDIS_URL" if role == "demo" else "OPSPROOF_CONTROL_REDIS_URL"
            value = base64.b64decode(docs[2]["data"][env_key]).decode()
            self.assertTrue(value.startswith("rediss://:"))
            self.assertIn("ssl_cert_reqs=required", value)
            self.assertIn("ssl_ca_certs=", value)
            self.assertNotIn("changeme", value)

    def test_helm_server_client_keda_contract(self):
        redis = (ROOT / "infra/helm/opsproof-dependencies/templates/redis.yaml").read_text()
        keda = (ROOT / "infra/helm/opsproof-services/templates/autoscaling.yaml").read_text()
        pod = (ROOT / "infra/helm/opsproof-services/templates/_helpers.tpl").read_text()
        self.assertIn("tls-port 6379", redis)
        self.assertIn("port 0", redis)
        self.assertIn("requirepass", redis)
        self.assertIn("opsproof-redis-auth", keda)
        self.assertIn("parameter: ca", keda)
        self.assertIn("opsproof-demo-redis-connection", pod)
        self.assertIn("opsproof-control-redis-connection", pod)
        self.assertIn("redis-ca", pod)
        for name in ("redis-networkpolicy.yaml", "postgres-networkpolicy.yaml"):
            self.assertTrue((ROOT / "infra/helm/opsproof-dependencies/templates" / name).is_file())


class ReleaseWorkflowTests(unittest.TestCase):
    def test_five_version_locked_controllers(self):
        rows = loaded()
        self.assertEqual(
            {r["name"] for r in rows},
            {
                "aws-load-balancer-controller",
                "external-secrets",
                "argo-cd",
                "argo-rollouts",
                "keda",
            },
        )
        self.assertTrue(all(re.fullmatch(r"\d+\.\d+\.\d+", x["version"]) for x in rows))
        source = (ROOT / "scripts/cloud/install_controllers.py").read_text()
        self.assertIn("chart_sha", source)
        self.assertIn("assert_cluster(kubeconfig, account, profile)", source)
        self.assertIn("--execute", source)

    def test_chart_identity_parser_accepts_aws_and_external_secrets_names(self):
        # Prevent accidental regex regression that truncates chart names containing "s".
        import io
        import tarfile
        from unittest.mock import patch

        import scripts.cloud.install_controllers as installer

        with tempfile.TemporaryDirectory() as td:
            for name in ("aws-load-balancer-controller", "external-secrets"):
                row = {"chart": name, "version": "3.6.2"}
                archive = Path(td) / f"{name}-3.6.2.tgz"
                payload = f"apiVersion: v2\nname: {name}\nversion: 3.6.2\n".encode()
                with tarfile.open(archive, "w:gz") as out:
                    info = tarfile.TarInfo(f"{name}/Chart.yaml")
                    info.size = len(payload)
                    out.addfile(info, io.BytesIO(payload))
                with patch.object(installer, "CHARTS", Path(td)):
                    self.assertRegex(installer.chart_sha(row), r"^[a-f0-9]{64}$")

    def test_installer_passes_verified_vpc_without_node_metadata_discovery(self):
        from unittest.mock import patch

        import scripts.cloud.install_controllers as installer

        row = {
            "name": "aws-load-balancer-controller",
            "release": "aws-load-balancer-controller",
            "namespace": "kube-system",
            "version": "3.6.2",
        }
        with (
            patch.object(installer, "verify"),
            patch.object(installer, "assert_cluster", return_value="vpc-12345678"),
            patch.object(installer, "loaded", return_value=[row]),
            patch.object(installer, "filename", return_value=Path("fixture.tgz")),
            patch.object(installer, "run", return_value="") as run,
        ):
            installer.install(ROOT / ".runtime/cloud/private/kubeconfig", "123456789012", "fixture")
        helm = run.call_args_list[0].args
        self.assertIn("vpcId=vpc-12345678", helm)
        self.assertIn("--set-string", helm)

    def test_pages_protected_content_gate(self):
        path = ROOT / ".github/workflows/evidence-pages.yml"
        text = path.read_text()
        self.assertIn("environment:", text)
        self.assertIn("github-pages", text)
        self.assertIn("sha256sum docs/public/cases.json", text)
        self.assertIn("--review I_REVIEWED_PUBLIC_EVIDENCE", text)
        self.assertIn("scripts.cloud.verify_public_replay", text)
        self.assertIn("pages: write", text)
        self.assertIn("id-token: write", text)
        self.assertNotIn("secrets.AWS_", text)
        # Action refs remain blocked until verified upstream pin resolver runs.
        self.assertEqual(scan([path]), [])


if __name__ == "__main__":
    unittest.main()
