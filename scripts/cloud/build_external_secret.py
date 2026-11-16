"""Generate credential-free ESO manifests for M7 scoped PostgreSQL roles.

The generated application Secret is the only DB Secret consumed by control
service Pods. The migration Job gets a separate Secret. Master credentials
exist only in the short-lived bootstrap Secret and Job, removed after use.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ARN_RE = re.compile(r"^arn:aws:secretsmanager:ap-south-1:(\d{12}):secret:[A-Za-z0-9/_+=.@!-]+$")
HOST_RE = re.compile(r"^[a-z0-9-]+\.[a-z0-9-]+\.ap-south-1\.rds\.amazonaws\.com$")


def secret_name(arn: str) -> None:
    if not ARN_RE.fullmatch(arn):
        raise ValueError("valid Mumbai Secrets Manager ARN required")


def build_scope(arn: str, *, target: str, role: str, host: str) -> dict:
    secret_name(arn)
    if not HOST_RE.fullmatch(host):
        raise ValueError("exact validated RDS endpoint hostname required")
    url = (
        "postgresql://{{ .username | urlquery }}:{{ .password | urlquery }}@"
        + host
        + ":5432/opsproof?sslmode=verify-full"
        "&sslrootcert=/etc/opsproof/rds-ca/global-bundle.pem"
    )
    return {
        "apiVersion": "external-secrets.io/v1",
        "kind": "ExternalSecret",
        "metadata": {"name": f"opsproof-control-rds-{role}", "namespace": "opsproof-control"},
        "spec": {
            "refreshInterval": "1h",
            "secretStoreRef": {"name": "opsproof-aws-sm", "kind": "SecretStore"},
            "target": {
                "name": target,
                "creationPolicy": "Owner",
                "template": {
                    "engineVersion": "v2",
                    "data": {
                        "OPSPROOF_CONTROL_DATABASE_URL": url,
                    },
                },
            },
            "data": [
                {"secretKey": field, "remoteRef": {"key": arn, "property": field}}
                for field in ("username", "password")
            ],
        },
    }


def build(arn: str, *, host: str, region: str = "ap-south-1") -> dict:
    """Keep the old unit-test builder shape, but now target the scoped app role."""
    if region != "ap-south-1":
        raise ValueError("ap-south-1 is required")
    return build_scope(arn, target="opsproof-control-rds-app-connection", role="app", host=host)


def build_all(*, master_arn: str, app_arn: str, migrate_arn: str, host: str) -> list[dict]:
    ids = {
        ARN_RE.fullmatch(x).group(1) if ARN_RE.fullmatch(x) else None
        for x in (master_arn, app_arn, migrate_arn)
    }
    if None in ids or len(ids) != 1:
        raise ValueError("three valid secrets from the same account are required")
    app = build_scope(app_arn, target="opsproof-control-rds-app-connection", role="app", host=host)
    migration = build_scope(
        migrate_arn, target="opsproof-control-rds-migration-connection", role="migration", host=host
    )
    # ESO bootstrap must contain only explicit role/password fields; no URL override.
    bootstrap = {
        "apiVersion": "external-secrets.io/v1",
        "kind": "ExternalSecret",
        "metadata": {"name": "opsproof-control-rds-bootstrap", "namespace": "opsproof-control"},
        "spec": {
            "refreshInterval": "1h",
            "secretStoreRef": {"name": "opsproof-aws-sm", "kind": "SecretStore"},
            "target": {
                "name": "opsproof-control-rds-bootstrap",
                "creationPolicy": "Owner",
                "template": {
                    "engineVersion": "v2",
                    "data": {
                        "OPSPROOF_RDS_MASTER_USERNAME": "{{ .master_username }}",
                        "OPSPROOF_RDS_MASTER_PASSWORD": "{{ .master_password }}",
                        "OPSPROOF_CLOUD_APP_PASSWORD": "{{ .app_password }}",
                        "OPSPROOF_CLOUD_MIGRATION_PASSWORD": "{{ .migration_password }}",
                        "OPSPROOF_RDS_HOST": host,
                        "OPSPROOF_RDS_PORT": "5432",
                    },
                },
            },
            "data": [
                {"secretKey": f"{prefix}_{field}", "remoteRef": {"key": arn, "property": field}}
                for prefix, arn, fields in (
                    ("master", master_arn, ("username", "password")),
                    ("app", app_arn, ("password",)),
                    ("migration", migrate_arn, ("password",)),
                )
                for field in fields
            ],
        },
    }
    # Later verifier uses app/role secrets but must not read RDS master.
    check = {
        "apiVersion": "external-secrets.io/v1",
        "kind": "ExternalSecret",
        "metadata": {"name": "opsproof-control-rds-role-verifier", "namespace": "opsproof-control"},
        "spec": {
            "refreshInterval": "1h",
            "secretStoreRef": {"name": "opsproof-aws-sm", "kind": "SecretStore"},
            "target": {
                "name": "opsproof-control-rds-role-verifier",
                "creationPolicy": "Owner",
                "template": {
                    "engineVersion": "v2",
                    "data": {
                        "OPSPROOF_CLOUD_APP_PASSWORD": "{{ .app_password }}",
                        "OPSPROOF_CLOUD_MIGRATION_PASSWORD": "{{ .migration_password }}",
                        "OPSPROOF_RDS_HOST": host,
                        "OPSPROOF_RDS_PORT": "5432",
                    },
                },
            },
            "data": [
                {
                    "secretKey": f"{prefix}_password",
                    "remoteRef": {"key": arn, "property": "password"},
                }
                for prefix, arn in (("app", app_arn), ("migration", migrate_arn))
            ],
        },
    }
    return [app, migration, bootstrap, check]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--master-secret-arn", required=True)
    parser.add_argument("--app-secret-arn", required=True)
    parser.add_argument("--migration-secret-arn", required=True)
    parser.add_argument("--rds-host", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    docs = build_all(
        master_arn=args.master_secret_arn,
        app_arn=args.app_secret_arn,
        migrate_arn=args.migration_secret_arn,
        host=args.rds_host,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"apiVersion": "v1", "kind": "List", "items": docs}, indent=2) + "\n",
        encoding="utf-8",
    )
    print("CREATED_4_SCOPED_EXTERNAL_SECRETS (no passwords in manifests)")


if __name__ == "__main__":
    main()
