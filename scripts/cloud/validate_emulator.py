"""Bounded local AWS Emulator contract rehearsal; never accepts a real AWS endpoint.

No Terraform apply or real account credentials. This tests SDK/serialization and
our reconciliation logic, not IAM enforcement, real infrastructure or billing.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import socket
import ssl
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from scripts.cloud.delete_db_credentials import delete_credentials
from scripts.cloud.provision_db_credentials import ensure_credentials

ROOT = Path(__file__).resolve().parents[2]
ENDPOINT = "https://127.0.0.1:9297"


def require_local_endpoint(url: str) -> None:
    value = urlsplit(url)
    if (
        value.scheme != "https"
        or value.hostname != "127.0.0.1"
        or value.port != 9297
        or value.username
        or value.password
    ):
        raise ValueError("Emulator requests must use the exact private loopback HTTPS endpoint")


def run(*args: str, check=True, timeout=60):
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AWS_", "OPSPROOF_", "GROQ_", "GEMINI_"))
    }
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=check,
        timeout=timeout,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def contracts(private: Path) -> dict:
    # Imported only by the explicitly executed isolated tooling environment.
    import boto3
    from botocore.config import Config

    for key in list(os.environ):
        if key.startswith(("AWS_", "BOTO_", "OPSPROOF_", "GROQ_", "GEMINI_")):
            del os.environ[key]
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    os.environ["AWS_CONFIG_FILE"] = str(private / "empty-config")
    os.environ["AWS_SHARED_CREDENTIALS_FILE"] = str(private / "empty-credentials")
    (private / "empty-config").write_text("", encoding="utf-8")
    (private / "empty-credentials").write_text("", encoding="utf-8")
    settings = configparser.ConfigParser()
    settings.read(private / "9297/emulator_credentials", encoding="utf-8")
    key = settings["default"]
    session = boto3.Session(
        aws_access_key_id=key["aws_access_key_id"],
        aws_secret_access_key=key["aws_secret_access_key"],
        region_name="ap-south-1",
    )
    config = Config(
        retries={"max_attempts": 0},
        connect_timeout=3,
        read_timeout=10,
        inject_host_prefix=False,
        proxies={},
        s3={"addressing_style": "path"},
    )
    count = 0

    def guard(request, **_kwargs):
        nonlocal count
        require_local_endpoint(request.url)
        count += 1
        if count > 100:
            raise RuntimeError("Emulator request ceiling reached")

    def client(service):
        require_local_endpoint(ENDPOINT)
        result = session.client(
            service, endpoint_url=ENDPOINT, verify=str(private / "9297/ca.pem"), config=config
        )
        result.meta.events.register("before-send.*.*", guard)
        return result

    sts, secrets, s3 = (client(name) for name in ("sts", "secretsmanager", "s3"))
    identity = sts.get_caller_identity()
    if identity.get("Account") != "000000000000":
        raise RuntimeError("Expected emulator account; refuse all subsequent requests")
    account = identity["Account"]
    bucket = "opsproof-emulator-" + uuid4().hex[:16]
    created_bucket = False
    result = {"emulator_identity_verified": True, "security_enforcement_validated": False}
    try:
        first = ensure_credentials(secrets, account)
        values = {
            row["name"]: secrets.get_secret_value(SecretId=row["arn"])["SecretString"]
            for row in first
        }
        second = ensure_credentials(secrets, account)
        if not all(
            row["status"] == "REUSED"
            and secrets.get_secret_value(SecretId=row["arn"])["SecretString"] == values[row["name"]]
            for row in second
        ):
            raise AssertionError("Cloud credential reconciliation rotated a retry credential")
        result["two_owned_secrets_reconciled_without_rotation"] = True
        s3.create_bucket(
            Bucket=bucket, CreateBucketConfiguration={"LocationConstraint": "ap-south-1"}
        )
        created_bucket = True
        s3.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        if s3.get_bucket_versioning(Bucket=bucket).get("Status") != "Enabled":
            raise AssertionError("S3 versioning round trip differs")
        state = b'{"local_fixture":true,"real_state":false}'
        s3.put_object(
            Bucket=bucket,
            Key="platform/terraform.tfstate",
            Body=state,
            ServerSideEncryption="AES256",
        )
        if s3.get_object(Bucket=bucket, Key="platform/terraform.tfstate")["Body"].read() != state:
            raise AssertionError("S3 state-object round trip differs")
        s3.put_object(
            Bucket=bucket, Key="platform/terraform.tfstate.tflock", Body=b"{}", IfNoneMatch="*"
        )
        try:
            s3.put_object(
                Bucket=bucket, Key="platform/terraform.tfstate.tflock", Body=b"{}", IfNoneMatch="*"
            )
        except s3.exceptions.ClientError as exc:
            if exc.response["Error"]["Code"] != "PreconditionFailed":
                raise
        else:
            raise AssertionError("Conditional lock write did not reject a duplicate")
        result.update(s3_versioned_state_round_trip=True, conditional_lock_collision_rejected=True)
    except Exception as exc:
        result["contract_error"] = {
            "type": type(exc).__name__,
            "service_code": getattr(exc, "response", {}).get("Error", {}).get("Code"),
        }
    finally:
        try:
            if created_bucket:
                versions = s3.list_object_versions(Bucket=bucket)
                objects = [
                    {"Key": row["Key"], "VersionId": row["VersionId"]}
                    for row in versions.get("Versions", []) + versions.get("DeleteMarkers", [])
                ]
                if objects:
                    s3.delete_objects(Bucket=bucket, Delete={"Objects": objects, "Quiet": True})
                s3.delete_bucket(Bucket=bucket)
            delete_credentials(secrets, account)
            deadline = time.monotonic() + 20
            while True:
                remaining = secrets.list_secrets(IncludePlannedDeletion=True)["SecretList"]
                owned = [
                    row for row in remaining if row.get("Name", "").startswith("opsproof-cloud-db-")
                ]
                if not owned:
                    break
                if time.monotonic() >= deadline:
                    result["secret_api_cleanup_unverified"] = [
                        {"name": row["Name"], "pending_deletion": bool(row.get("DeletedDate"))}
                        for row in owned
                    ]
                    break
                time.sleep(1)
            bucket_remains = any(row["Name"] == bucket for row in s3.list_buckets()["Buckets"])
            result["emulated_resources_deleted"] = not owned and not bucket_remains
        except Exception as exc:
            result["cleanup_error"] = {
                "type": type(exc).__name__,
                "service_code": getattr(exc, "response", {}).get("Error", {}).get("Code"),
            }
            result["emulated_resources_deleted"] = False
        result["local_sdk_requests"] = count
        for item in (sts, secrets, s3):
            item.close()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Use --execute for the isolated local emulator rehearsal")
    # Do not take an already occupied endpoint or reuse someone else's emulator.
    with socket.socket() as check:
        check.bind(("127.0.0.1", 9297))
    output = ROOT / ".runtime/verification/cloud/emulator" / ("run-" + uuid4().hex)
    private = output / "private"
    private.mkdir(parents=True, exist_ok=False)
    name = "opsproof-emulator-check-" + uuid4().hex[:12]
    result = {
        "passed": False,
        "real_aws_requests": 0,
        "model_calls": 0,
        "kubernetes_started": False,
        "telemetry_enabled": False,
    }
    try:
        version = run(
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--memory",
            "256m",
            "opsproof-emulator:1.0.385",
            "-v",
        ).stdout
        if "1.0.385" not in version:
            raise ValueError("Emulator image version differs from verified package")
        result["version_output"] = version.strip()
        run(
            "docker",
            "run",
            "--detach",
            "--name",
            name,
            "--label",
            "opsproof.test=aws-emulator",
            "--publish",
            "127.0.0.1:9297:9297",
            "--memory",
            "2g",
            "--memory-swap",
            "2g",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=134217728",
            "--mount",
            f"type=bind,source={private},target=/home/emulator/.aws/emulator",
            "opsproof-emulator:1.0.385",
            "-p",
            "9297",
        )
        deadline = time.monotonic() + 30
        while not (private / "9297/ca.pem").exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("Emulator did not create its private session files")
            time.sleep(0.2)
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(
                context=ssl.create_default_context(cafile=str(private / "9297/ca.pem"))
            ),
        )
        require_local_endpoint(ENDPOINT + "/__admin/health")
        with opener.open(ENDPOINT + "/__admin/health", timeout=5) as response:
            if response.status != 200 or response.read(16).strip() != b"ok":
                raise ValueError("Emulator health differs from documented contract")
        result["contracts"] = contracts(private)
        result["passed"] = not result["contracts"].get("contract_error") and result[
            "contracts"
        ].get("emulated_resources_deleted", False)
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        raise
    finally:
        inspected = run("docker", "inspect", name, check=False)
        if inspected.returncode == 0:
            item = json.loads(inspected.stdout)[0]
            if item["Config"].get("Labels", {}).get("opsproof.test") != "aws-emulator":
                raise RuntimeError("Container ownership differs; refuse cleanup")
            run("docker", "stop", "--time", "10", name, timeout=30)
            run("docker", "rm", name)
        elif "No such object" not in inspected.stderr:
            raise RuntimeError("Emulator cleanup could not be established")
        if not private.resolve().is_relative_to(
            (ROOT / ".runtime/verification/cloud/emulator").resolve()
        ):
            raise RuntimeError("Refuse cleanup outside the owned emulator workspace")
        for file in private.rglob("*"):
            if file.is_file():
                file.unlink()
        for directory in sorted((p for p in private.rglob("*") if p.is_dir()), reverse=True):
            directory.rmdir()
        private.rmdir()
        result["private_session_files_removed"] = True
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
