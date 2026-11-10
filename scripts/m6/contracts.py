"""Locked six-scenario M6 catalog and conservative local execution gate.

This is a data/specification layer, NOT an injection engine. Only the
scenarios listed here may be proposed; execution needs distinct authorization.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final
from urllib.parse import urlparse


class Scenario(StrEnum):
    WORKER_SATURATION = "worker_saturation"
    FAULTY_RELEASE = "faulty_release"
    DATABASE_CONNECTIVITY = "database_connectivity"
    WORKER_FAILURE = "worker_failure"
    DOWNSTREAM_LATENCY = "downstream_latency"
    MISLEADING_EVIDENCE = "misleading_evidence"


@dataclass(frozen=True)
class ScenarioContract:
    scenario: Scenario
    target: str
    mechanism: str
    observation: str
    postconditions: tuple[str, ...]
    requires_cluster_mutation: bool
    active_m5_gate: str


CATALOG: Final = {
    Scenario.WORKER_SATURATION: ScenarioContract(
        Scenario.WORKER_SATURATION, "opsproof-demo/Deployment/demo-worker",
        "bounded durable job submission", "Redis pending/lag, age, replicas, completion",
        ("exact_job_ids_completed", "no_unreconciled_jobs"), False, "keda_and_queue_integrity",
    ),
    Scenario.FAULTY_RELEASE: ScenarioContract(
        Scenario.FAULTY_RELEASE, "opsproof-demo/Rollout/demo-api",
        "Git-owned approved candidate image", "candidate errors, AnalysisRun, rollout events",
        ("stable_revision_serving", "candidate_aborted_or_promoted", "no_data_loss"),
        True, "rollouts_and_gateway",
    ),
    Scenario.DATABASE_CONNECTIVITY: ScenarioContract(
        Scenario.DATABASE_CONNECTIVITY, "opsproof-demo/PostgreSQL/demo-deps-db",
        "reviewed temporary namespace-scoped test network policy",
        "readiness, DB errors, preserved durable IDs",
        ("reads_and_writes_restored", "data_integrity_preserved"), True,
        "network_policy_and_gitops_ownership",
    ),
    Scenario.WORKER_FAILURE: ScenarioContract(
        Scenario.WORKER_FAILURE, "opsproof-demo/Deployment/demo-worker",
        "controlled single Pod termination with bounded in-flight work",
        "Redis PEL, lease fencing, replacement and exact completion",
        ("acknowledged_jobs_complete", "no_duplicate_durable_completion"), True,
        "consumer_failure_recovery",
    ),
    Scenario.DOWNSTREAM_LATENCY: ScenarioContract(
        Scenario.DOWNSTREAM_LATENCY, "opsproof-demo/test-only-downstream",
        "disabled-by-default bounded HTTP latency fixture", "HTTP timeouts, traces, retries",
        ("latency_fixture_disabled", "normal_response_restored"), True,
        "validated_test_dependency",
    ),
    Scenario.MISLEADING_EVIDENCE: ScenarioContract(
        Scenario.MISLEADING_EVIDENCE, "opsproof-control/read-only-evidence",
        "replayed contradictory or stale test evidence", "diagnostic abstention and denial",
        ("no_unauthorized_action", "unknown_outcome_preserved"), False,
        "m4_evidence_policy",
    ),
}


def assert_local_scope(*, kubeconfig: Path, context: str, mutation: bool,
                       acknowledged: bool = False) -> None:
    if context != "k3d-opsproof":
        raise ValueError("Refusing any context other than k3d-opsproof")
    if not kubeconfig.is_file():
        raise ValueError("Explicit local kubeconfig does not exist")
    if mutation and not acknowledged:
        raise ValueError("Mutating experiment requires separately acknowledged trial")


def assert_bounded_workload(*, count: int, duration_ms: int, max_count: int = 120) -> None:
    if type(count) is not int or type(duration_ms) is not int:
        raise ValueError("count and duration must be integers")
    if not 1 <= count <= max_count or not 50 <= duration_ms <= 2000:
        raise ValueError("Job count or duration exceeds experimental bounds")


def assert_isolated_k3d_api(server: str) -> None:
    """Enforce the exact loopback API endpoint from approved M5 k3d config."""
    parsed = urlparse(server)
    if (parsed.scheme != "https" or parsed.hostname != "127.0.0.1"
            or parsed.port != 6550 or parsed.username or parsed.password
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise ValueError("Only the local https://127.0.0.1:6550 API is authorized")
