"""One typed operation: restore the explicitly managed demo worker from 0 to 1.

No caller-controlled Kubernetes path, namespace, selector, command or patch.
"""

from datetime import UTC, datetime
from math import isfinite

TARGET_PATH = "/apis/apps/v1/namespaces/opsproof-demo/deployments/demo-worker"
ACTION = "restore_demo_worker"
CONFIRMATION = "APPROVE DEMO WORKER RESTORE"
POLICY = "restore-single-worker-v1"


class PolicyDenied(ValueError):
    pass


def validate(proposal, target, telemetry, incident, experiment, now=None):
    now = now or datetime.now(UTC)
    if proposal.get("action") != ACTION or proposal.get("status") != "running":
        raise PolicyDenied("Approved claimed operation required")
    if not proposal.get("approved_at") or now >= proposal["expires_at"]:
        raise PolicyDenied("Approval missing or expired")
    if (
        not incident
        or incident.get("status") != "firing"
        or incident.get("name") != "OpsProofDemoQueueBacklog"
        or incident.get("target") != "opsproof-demo-api"
    ):
        raise PolicyDenied("Current supported firing incident required")
    if (
        not experiment
        or experiment.get("status") != "verifying"
        or experiment.get("scenario") != "queue-burst"
    ):
        raise PolicyDenied("Active bounded queue experiment required")
    queued = telemetry.get("queued") if telemetry else None
    if (
        not telemetry
        or telemetry.get("ready") is not True
        or type(queued) not in (int, float)
        or not isfinite(queued)
        or not 0 < queued <= 1_000_000
    ):
        raise PolicyDenied("Live dependency and queue evidence required")
    age = now.timestamp() - telemetry.get("sample_time", 0)
    if not 0 <= age <= 30:
        raise PolicyDenied("Telemetry missing, future-dated or stale")
    meta = target.get("metadata", {})
    if (
        target.get("kind") != "Deployment"
        or meta.get("namespace") != "opsproof-demo"
        or meta.get("name") != "demo-worker"
    ):
        raise PolicyDenied("Unsupported target")
    if meta.get("uid") != proposal.get("target_uid") or meta.get("resourceVersion") != proposal.get(
        "target_version"
    ):
        raise PolicyDenied("Target identity or resourceVersion changed")
    if meta.get("annotations", {}).get("opsproof.io/recovery-policy") != POLICY:
        raise PolicyDenied("Target is not opted into this recovery policy")
    if target.get("spec", {}).get("replicas") != 0:
        raise PolicyDenied("Only a stopped worker can be restored")
    if target.get("status", {}).get("replicas", 0) != 0:
        raise PolicyDenied("Worker has not finished stopping")
    if target["spec"]["template"]["spec"]["containers"][0]["image"] != proposal.get("target_image"):
        raise PolicyDenied("Target image changed")
    return [
        {"op": "test", "path": "/metadata/uid", "value": proposal["target_uid"]},
        {"op": "test", "path": "/metadata/resourceVersion", "value": proposal["target_version"]},
        {"op": "test", "path": "/spec/replicas", "value": 0},
        {"op": "replace", "path": "/spec/replicas", "value": 1},
        {
            "op": "add",
            "path": "/metadata/annotations/opsproof.io~1recovery-id",
            "value": str(proposal["id"]),
        },
    ]
