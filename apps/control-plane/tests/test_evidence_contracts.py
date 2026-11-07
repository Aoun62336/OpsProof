"""Exact-job evidence must fail closed for missing and misleading observations."""

from uuid import uuid4

import pytest

from opsproof_control.evidence_contracts import exact_job_status, required_job_ids


@pytest.mark.parametrize(
    "details,count",
    [
        (None, 1),
        ({"job_ids": []}, 1),
        ({"job_ids": [str(uuid4())]}, 2),
        ({"job_ids": [str(uuid4())], "submitted": 0}, 1),
        ({"job_ids": ["invalid"]}, 1),
        ({"job_ids": [123]}, 1),
        ({"job_ids": [str(uuid4())]}, 0),
        ({"job_ids": [str(uuid4())]}, 9),
    ],
)
def test_invalid_evidence_never_grants_success(details, count):
    with pytest.raises(ValueError):
        required_job_ids(details, count)


def test_duplicate_ids_rejected():
    job = str(uuid4())
    with pytest.raises(ValueError, match="Duplicate"):
        required_job_ids({"job_ids": [job, job], "submitted": 2}, 2)


def test_valid_unique_ids_preserve_order():
    ids = [str(uuid4()), str(uuid4())]
    assert required_job_ids({"job_ids": ids, "submitted": 2}, 2) == ids


@pytest.mark.parametrize("state", ["queued", "processing", "completed", "failed"])
def test_valid_identity_and_state(state):
    job = str(uuid4())
    assert exact_job_status({"id": job, "status": state}, job) == state


@pytest.mark.parametrize("payload", [None, {}, {"status": "completed"}, {"status": "unknown"}])
def test_missing_or_unknown_job_data_rejected(payload):
    with pytest.raises(ValueError):
        exact_job_status(payload, str(uuid4()))


def test_wrong_identity_cannot_count_as_completed():
    with pytest.raises(ValueError, match="identity"):
        exact_job_status({"id": str(uuid4()), "status": "completed"}, str(uuid4()))
