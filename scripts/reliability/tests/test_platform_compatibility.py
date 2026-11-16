"""Source contracts: safeguard local M5 interfaces when enabling new M6/M7 profiles.

These are source-level regression guards, not Kubernetes acceptance tests.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_existing_m5_routes_and_operator_ui_survive():
    routing = read("apps/control-plane/src/opsproof_control/kubernetes_operations.py")
    ui = read("apps/web/src/app/App.tsx")
    assert '@router.get("/workloads")' in routing
    assert '@router.post("/recoveries"' in routing
    assert "KubernetesPage" in ui
    for route in ("/workloads", "/deployments", "/capacity", "/runbooks"):
        assert route in ui


def test_m5_worker_keeps_shutdown_and_fencing_with_optional_downstream():
    worker = read("apps/demo-workload/src/opsproof_demo/worker.py")
    assert "from .shutdown import checkpoint, stopping" in worker
    assert "AND worker_token = %s" in worker
    assert "checkpoint()" in worker
    assert "probe(" in worker
    assert worker.index("probe(") < worker.index("SET status = 'completed'")
    config = read("apps/demo-workload/src/opsproof_demo/config.py")
    assert "downstream_enabled: bool = False" in config


def test_m5_helm_workflows_default_safe_and_recovery_ownership_unchanged():
    values = read("infra/helm/opsproof-services/values.yaml")
    helpers = read("infra/helm/opsproof-services/templates/_helpers.tpl")
    chart = read("infra/helm/opsproof-services/templates/workloads.yaml")
    assert "demoDownstream:\n  enabled: false" in values
    assert "demoDownstream.delayMs must be an integer in 0..2000" in helpers
    assert "Recovery and KEDA must not own the same worker replicas" in helpers
    assert "opsproof.io/recovery-policy: restore-single-worker-v1" in chart


def test_cloud_requires_explicit_cost_and_operator_identity():
    infra = read("infra/terraform/main.tf")
    vars = read("infra/terraform/variables.tf")
    eks = read("infra/terraform/modules/eks/main.tf")
    assert "default     = false" in vars
    assert "I_APPROVE_TEMPORARY_OPSPROOF_AWS_CHARGES" in infra
    assert "var.expected_account_id == data.aws_caller_identity.active[0].account_id" in infra
    assert "bootstrap_cluster_creator_admin_permissions = false" in eks
    assert "retention_in_days = 1" in eks


def test_release_is_manual_and_never_autoprovisions_aws():
    workflow = read(".github/workflows/release.yml")
    assert "workflow_dispatch:" in workflow
    assert "publish_approved:" in workflow
    assert "environment: opsproof-release" in workflow
    assert "terraform apply" not in workflow
