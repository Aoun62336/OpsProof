"""Resume creation of two owned database credentials without rotating existing values."""

import argparse
import json
import re
import secrets

TAGS = {
    "Project": "OpsProof",
    "Environment": "temporary-verification",
    "ManagedBy": "OpsProof",
    "Purpose": "database-credentials",
    "Ephemeral": "true",
}
USERS = ("opsproof_app", "opsproof_migrate")


def plan_names(prefix: str) -> tuple[str, str]:
    if prefix != "opsproof-cloud":
        raise ValueError("Only the Terraform/IAM-scoped opsproof-cloud name is allowed")
    return (prefix + "-db-app", prefix + "-db-migration")


def verify_owned_metadata(metadata, name, account_id):
    tags = {item["Key"]: item["Value"] for item in metadata.get("Tags", [])}
    expected = rf"arn:aws:secretsmanager:ap-south-1:{account_id}:secret:{name}-[A-Za-z0-9]{{6}}"
    if not re.fullmatch(expected, metadata.get("ARN", "")) or any(
        tags.get(key) != value for key, value in TAGS.items()
    ):
        raise ValueError("Existing secret identity or ownership does not match")


def ensure_credentials(client, account_id):
    if not re.fullmatch(r"[0-9]{12}", account_id):
        raise ValueError("Exact approved AWS account required")
    results = []
    for name, username in zip(plan_names("opsproof-cloud"), USERS, strict=True):
        try:
            metadata = client.describe_secret(SecretId=name)
        except client.exceptions.ResourceNotFoundException:
            metadata = None
        status = "REUSED"
        if metadata is None:
            value = json.dumps({"username": username, "password": secrets.token_urlsafe(36)})
            try:
                client.create_secret(
                    Name=name,
                    SecretString=value,
                    Tags=[{"Key": k, "Value": v} for k, v in TAGS.items()],
                )
                status = "CREATED"
            except client.exceptions.ResourceExistsException:
                # Reconcile an already completed create; never replace its credential.
                pass
            metadata = client.describe_secret(SecretId=name)
        verify_owned_metadata(metadata, name, account_id)
        if metadata.get("DeletedDate"):
            raise ValueError("Owned secret is pending deletion; explicit owner resolution required")
        payload = json.loads(client.get_secret_value(SecretId=metadata["ARN"])["SecretString"])
        if (
            set(payload) != {"username", "password"}
            or payload["username"] != username
            or not isinstance(payload["password"], str)
            or len(payload["password"]) < 32
        ):
            raise ValueError("Owned secret payload does not match its role contract")
        results.append({"name": name, "arn": metadata["ARN"], "status": status})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--prefix", default="opsproof-cloud")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{12}", args.account_id):
        parser.error("Account ID must be twelve digits")
    names = plan_names(args.prefix)
    if not args.execute:
        print(json.dumps({"mode": "DRY_RUN", "region": "ap-south-1", "names": names}))
        return
    import boto3  # Explicit optional tooling dependency, never an application dependency.

    session = boto3.Session(profile_name=args.profile, region_name="ap-south-1")
    if session.client("sts").get_caller_identity()["Account"] != args.account_id:
        raise SystemExit("AWS account mismatch; nothing changed")
    for item in ensure_credentials(session.client("secretsmanager"), args.account_id):
        print(item["status"], item["name"], "(value hidden)")
    print("TWO_DATABASE_CREDENTIALS_RECONCILED; verify deletion after teardown")


if __name__ == "__main__":
    main()
