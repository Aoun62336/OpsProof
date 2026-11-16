"""Importable, fixed M6 scenario catalog. No arbitrary target or injected command."""

from enum import StrEnum


class Scenario(StrEnum):
    WORKER_SATURATION = "worker_saturation"
    FAULTY_RELEASE = "faulty_release"
    DATABASE_CONNECTIVITY = "database_connectivity"
    WORKER_FAILURE = "worker_failure"
    DOWNSTREAM_LATENCY = "downstream_latency"
    MISLEADING_EVIDENCE = "misleading_evidence"


TARGETS: dict[Scenario, str] = {
    Scenario.WORKER_SATURATION: "opsproof-demo/Deployment/demo-worker",
    Scenario.FAULTY_RELEASE: "opsproof-demo/Rollout/demo-api",
    Scenario.DATABASE_CONNECTIVITY: "opsproof-demo/PostgreSQL/demo-deps-db",
    Scenario.WORKER_FAILURE: "opsproof-demo/Deployment/demo-worker",
    Scenario.DOWNSTREAM_LATENCY: "opsproof-demo/test-only-downstream",
    Scenario.MISLEADING_EVIDENCE: "opsproof-control/read-only-evidence",
}


def fixed_target(scenario: Scenario) -> str:
    return TARGETS[scenario]
