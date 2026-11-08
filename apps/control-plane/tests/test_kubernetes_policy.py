from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from opsproof_control.kubernetes_policy import POLICY, PolicyDenied, validate


def fixtures():
    now = datetime.now(UTC)
    proposal = dict(
        id="one",
        action="restore_demo_worker",
        status="running",
        approved_at=now,
        expires_at=now + timedelta(seconds=60),
        target_uid="uid",
        target_version="123",
        target_image="local:fixed",
    )
    target = dict(
        kind="Deployment",
        metadata=dict(
            name="demo-worker",
            namespace="opsproof-demo",
            uid="uid",
            resourceVersion="123",
            annotations={"opsproof.io/recovery-policy": POLICY},
        ),
        spec=dict(replicas=0, template=dict(spec=dict(containers=[dict(image="local:fixed")]))),
        status=dict(replicas=0),
    )
    telemetry = dict(ready=True, queued=5, sample_time=now.timestamp())
    incident = dict(status="firing", name="OpsProofDemoQueueBacklog", target="opsproof-demo-api")
    experiment = dict(status="verifying", scenario="queue-burst")
    return [proposal, target, telemetry, incident, experiment, now]


def test_exact_bounded_compare_and_swap():
    patch = validate(*fixtures())
    assert [p["op"] for p in patch] == ["test", "test", "test", "replace", "add"]
    assert patch[3] == {"op": "replace", "path": "/spec/replicas", "value": 1}


@pytest.mark.parametrize(
    "field,value",
    [
        ("action", "arbitrary"),
        ("status", "pending_approval"),
        ("status", "succeeded"),
        ("approved_at", None),
        ("expires_at", datetime(2000, 1, 1, tzinfo=UTC)),
        ("target_uid", "recreated"),
        ("target_version", "stale"),
        ("target_image", "wrong"),
    ],
)
def test_invalid_authority_or_stale_target(field, value):
    args = fixtures()
    args[0][field] = value
    with pytest.raises(PolicyDenied):
        validate(*args)


@pytest.mark.parametrize(
    "field,value", [("namespace", "other"), ("name", "control-api"), ("annotations", {})]
)
def test_fixed_target_only(field, value):
    args = fixtures()
    args[1]["metadata"][field] = value
    with pytest.raises(PolicyDenied):
        validate(*args)


@pytest.mark.parametrize(
    "telemetry",
    [
        None,
        {},
        {"ready": False},
        {"ready": True, "queued": 0},
        {"ready": True, "queued": 5, "sample_time": 0},
        {"ready": True, "queued": 5, "sample_time": float("nan")},
        {"ready": True, "queued": 5, "sample_time": float("inf")},
    ],
)
def test_missing_stale_or_invalid_telemetry(telemetry):
    args = fixtures()
    args[2] = deepcopy(telemetry)
    with pytest.raises(PolicyDenied):
        validate(*args)


def test_already_restored_is_not_credited():
    args = fixtures()
    args[1]["spec"]["replicas"] = 1
    with pytest.raises(PolicyDenied):
        validate(*args)


def test_resolved_incident_is_not_action_authority():
    args = fixtures()
    args[3]["status"] = "resolved"
    with pytest.raises(PolicyDenied):
        validate(*args)
