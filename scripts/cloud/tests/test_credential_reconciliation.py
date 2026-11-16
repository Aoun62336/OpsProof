"""Interrupted cloud secret operations preserve owned values and reject unrelated resources."""

import json
from types import SimpleNamespace

import pytest

from scripts.cloud.delete_db_credentials import delete_credentials
from scripts.cloud.provision_db_credentials import ensure_credentials, plan_names

ACCOUNT = "123456789012"


class Missing(Exception):
    pass


class Exists(Exception):
    pass


class Client:
    exceptions = SimpleNamespace(ResourceNotFoundException=Missing, ResourceExistsException=Exists)

    def __init__(self):
        self.items = {}
        self.fail_second_create = False
        self.deleted = []

    def describe_secret(self, *, SecretId):
        if SecretId not in self.items:
            raise Missing()
        return self.items[SecretId]["metadata"]

    def create_secret(self, *, Name, SecretString, Tags):
        if self.fail_second_create and Name.endswith("migration"):
            self.fail_second_create = False
            raise ConnectionError("Injected interruption")
        if Name in self.items:
            raise Exists()
        self.items[Name] = {
            "metadata": {
                "ARN": f"arn:aws:secretsmanager:ap-south-1:{ACCOUNT}:secret:{Name}-abcdef",
                "Tags": Tags,
            },
            "value": SecretString,
        }

    def get_secret_value(self, *, SecretId):
        return {
            "SecretString": next(
                value["value"]
                for value in self.items.values()
                if value["metadata"]["ARN"] == SecretId
            )
        }

    def delete_secret(self, *, SecretId, ForceDeleteWithoutRecovery):
        assert ForceDeleteWithoutRecovery
        self.deleted.append(SecretId)


def test_resume_after_first_secret_preserves_original_password():
    client = Client()
    client.fail_second_create = True
    with pytest.raises(ConnectionError):
        ensure_credentials(client, ACCOUNT)
    app = plan_names("opsproof-cloud")[0]
    original = client.items[app]["value"]
    result = ensure_credentials(client, ACCOUNT)
    assert [item["status"] for item in result] == ["REUSED", "CREATED"]
    assert client.items[app]["value"] == original
    assert all(item["status"] == "REUSED" for item in ensure_credentials(client, ACCOUNT))
    assert all("password" not in item for item in result)


def test_existing_unowned_secret_is_never_adopted_or_deleted():
    client = Client()
    ensure_credentials(client, ACCOUNT)
    name = plan_names("opsproof-cloud")[1]
    client.items[name]["metadata"]["Tags"] = []
    with pytest.raises(ValueError, match="ownership"):
        ensure_credentials(client, ACCOUNT)
    with pytest.raises(ValueError, match="ownership"):
        delete_credentials(client, ACCOUNT)
    assert client.deleted == []


def test_wrong_role_payload_and_pending_deletion_fail_closed():
    client = Client()
    ensure_credentials(client, ACCOUNT)
    name = plan_names("opsproof-cloud")[0]
    client.items[name]["value"] = json.dumps({"username": "admin", "password": "a" * 48})
    with pytest.raises(ValueError, match="payload"):
        ensure_credentials(client, ACCOUNT)
    client.items[name]["metadata"]["DeletedDate"] = "pending"
    with pytest.raises(ValueError, match="pending deletion"):
        ensure_credentials(client, ACCOUNT)


def test_cleanup_absence_is_idempotent_but_errors_are_not_absence():
    client = Client()
    assert all(item["status"] == "ABSENT" for item in delete_credentials(client, ACCOUNT))

    def unavailable(**_):
        raise ConnectionError("Unavailable")

    client.describe_secret = unavailable
    with pytest.raises(ConnectionError):
        delete_credentials(client, ACCOUNT)
