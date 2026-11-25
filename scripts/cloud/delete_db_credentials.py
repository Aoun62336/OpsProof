"""Delete only the two verified owned database secrets after owner-approved teardown."""

import argparse
import re

from scripts.cloud.provision_db_credentials import plan_names, verify_owned_metadata


def delete_credentials(client, account_id):
    if not re.fullmatch(r"[0-9]{12}", account_id):
        raise ValueError("Exact account required")
    owned, results = [], []
    # Inspect both identities before requesting either deletion.
    for name in plan_names("opsproof-cloud"):
        try:
            metadata = client.describe_secret(SecretId=name)
        except client.exceptions.ResourceNotFoundException:
            results.append({"name": name, "status": "ABSENT"})
            continue
        verify_owned_metadata(metadata, name, account_id)
        if metadata.get("DeletedDate"):
            results.append({"name": name, "status": "PENDING_DELETE"})
        else:
            owned.append((name, metadata["ARN"]))
    for name, arn in owned:
        client.delete_secret(SecretId=arn, ForceDeleteWithoutRecovery=True)
        results.append({"name": name, "status": "DELETION_REQUESTED"})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]{12}", args.account_id):
        parser.error("Explicit twelve-digit account ID required")
    if args.confirm != "DELETE_OPSPROOF_CLOUD_DB_SECRETS":
        parser.error("Destructive confirmation missing; nothing changed")
    import boto3

    session = boto3.Session(profile_name=args.profile, region_name="ap-south-1")
    if session.client("sts").get_caller_identity()["Account"] != args.account_id:
        raise SystemExit("Wrong account; nothing changed")
    for item in delete_credentials(session.client("secretsmanager"), args.account_id):
        print(item["status"], item["name"])
    print("Deletion is eventually consistent; verify actual absence before closure.")


if __name__ == "__main__":
    main()
