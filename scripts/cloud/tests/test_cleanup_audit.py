"""Cloud cleanup evidence fails closed on ambiguous errors and partial capture."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from scripts.cloud.audit_aws_cleanup import LOOKUPS, audit, lookup, validate_inventory


def inventory():
    return {
        "schema": 2,
        "account_id": "123456789012",
        "region": "ap-south-1",
        "capture_complete": True,
        "resources": {
            kind: ["opsproof-cloud"] if kind == "eks_cluster" else [] for kind in LOOKUPS
        },
    }


@pytest.mark.parametrize(
    "message",
    [
        "AccessDenied: ResourceNotFoundException mentioned in policy",
        "An error occurred (AccessDenied) when calling DescribeCluster: ResourceNotFoundException",
        "Unable to locate credentials",
    ],
)
def test_errors_are_not_absence(message):
    with patch("scripts.cloud.audit_aws_cleanup.aws", return_value=(1, "", message)):
        assert (
            lookup("fixture", "ap-south-1", "eks_cluster", "opsproof-cloud")["status"]
            == "UNVERIFIED_ERROR"
        )


def test_exact_service_error_is_absence():
    error = "An error occurred (ResourceNotFoundException) when calling DescribeCluster: missing"
    with patch("scripts.cloud.audit_aws_cleanup.aws", return_value=(1, "", error)):
        assert (
            lookup("fixture", "ap-south-1", "eks_cluster", "opsproof-cloud")["status"]
            == "NOT_FOUND"
        )


def test_partial_capture_never_passes_cleanup():
    record = inventory()
    record["capture_complete"] = False
    with (
        patch(
            "scripts.cloud.audit_aws_cleanup.aws",
            return_value=(0, '{"Account":"123456789012"}', ""),
        ),
        patch("scripts.cloud.audit_aws_cleanup.lookup", return_value={"status": "NOT_FOUND"}),
    ):
        assert audit("fixture", record)["status"] == "RESOURCES_REMAIN_OR_UNVERIFIED"


def test_missing_categories_foreign_arns_and_duplicates_rejected():
    original = inventory()
    missing = deepcopy(original)
    del missing["resources"]["eni"]
    foreign = deepcopy(original)
    foreign["resources"]["secret"] = ["arn:aws:secretsmanager:ap-south-1:000000000000:secret:other"]
    duplicate = deepcopy(original)
    duplicate["resources"]["eks_cluster"].append("opsproof-cloud")
    for record in (missing, foreign, duplicate):
        with pytest.raises(ValueError):
            validate_inventory(record)


def test_pending_secret_and_nat_deleting_are_present():
    with patch("scripts.cloud.audit_aws_cleanup.aws", return_value=(0, '{"DeletedDate":123}', "")):
        assert lookup("fixture", "ap-south-1", "secret", "fixture")["status"] == "PRESENT"
    with patch(
        "scripts.cloud.audit_aws_cleanup.aws",
        return_value=(0, '{"NatGateways":[{"State":"deleting"}]}', ""),
    ):
        assert lookup("fixture", "ap-south-1", "nat_gateway", "fixture")["status"] == "PRESENT"
