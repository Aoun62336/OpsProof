"""The console and recovery scripts must reach the actual registered endpoints."""

from opsproof_control.kubernetes_operations import router


def test_public_route_contract():
    assert {route.path for route in router.routes} == {
        "/api/v1/kubernetes/workloads",
        "/api/v1/kubernetes/recoveries",
        "/api/v1/kubernetes/recoveries/{recovery_id}/events",
        "/api/v1/kubernetes/recoveries/{recovery_id}/approve",
    }
    assert all(route.dependencies for route in router.routes)
