"""Deployment safety and discovery contracts shared by local and cloud profiles."""

import json
from types import SimpleNamespace

import pytest

from scripts.compose import prepare_observability
from scripts.platform.observability import ROOT, inputs, render
from scripts.platform.telemetry_images import runtime_images


@pytest.mark.parametrize("cloud", [False, True])
def test_all_replicas_discovered_and_only_prometheus_has_read_only_node_identity(cloud):
    images = runtime_images("ghcr.io/offline/fixture/opsproof-grafana@sha256:" + "b" * 64)
    rows = render(
        images, storage_class="opsproof-ebs-gp3" if cloud else "local-path", cloud_profile=cloud
    )["items"]
    configurations, _ = inputs(cloud_profile=cloud)
    config = configurations["prometheus"]["prometheus.yml"]
    assert config.count("dns_sd_configs:") == 2
    assert ("opsproof-demo-canary" in config) is not cloud
    assert "insecure_skip_verify" not in config
    assert "ca_file:" in config and "authorization:" in config
    role = next(r for r in rows if r["kind"] == "ClusterRole")
    assert {v for rule in role["rules"] for v in rule["verbs"]} == {"get", "list", "watch"}
    assert {v for rule in role["rules"] for v in rule["resources"]} == {"nodes", "nodes/metrics"}
    claims = [r for r in rows if r["kind"] == "PersistentVolumeClaim"]
    assert len(claims) == 6
    assert all(r["spec"]["resources"]["requests"]["storage"] == "1Gi" for r in claims)
    for row in (r for r in rows if r["kind"] == "Deployment"):
        pod = row["spec"]["template"]["spec"]
        container = pod["containers"][0]
        assert pod["automountServiceAccountToken"] is False
        assert pod["securityContext"]["runAsNonRoot"] is True
        assert container["securityContext"]["readOnlyRootFilesystem"] is True
        assert (
            container["startupProbe"] and container["livenessProbe"] and container["readinessProbe"]
        )
        projected = [v for v in pod["volumes"] if "projected" in v]
        assert bool(projected) is (row["metadata"]["name"] == "prometheus")


def test_dashboard_uses_measurements_and_has_correlation_links():
    text = (ROOT / "observability/grafana/dashboards/operations.json").read_text()
    assert "container_cpu_usage_seconds_total" in text
    assert "container_memory_working_set_bytes" in text
    assert "kubelet_volume_stats_available_bytes" in text
    assert "max by" in text
    datasources = (ROOT / "observability/grafana/provisioning/datasources/opsproof.yml").read_text()
    assert "tracesToLogsV2" in datasources and "matcherRegex: trace_id" in datasources


def test_compose_and_kubernetes_share_reviewed_immutable_images():
    images = json.loads((ROOT / "observability/images.lock.json").read_text())
    compose = (ROOT / "compose.observability.yaml").read_text()
    for image in images.values():
        assert "@sha256:" in image and image in compose
    assert (
        "publishNotReadyAddresses: true"
        in (ROOT / "infra/helm/opsproof-services/templates/workloads.yaml").read_text()
    )


def test_cloud_cannot_use_a_local_grafana_source_tag():
    with pytest.raises(ValueError, match="Immutable telemetry image digests"):
        render(runtime_images(), storage_class="opsproof-ebs-gp3", cloud_profile=True)


@pytest.mark.parametrize("unowned,running", [(True, False), (False, True)])
def test_volume_initialization_refuses_unowned_or_live_data(monkeypatch, unowned, running):
    mutations = []

    def run(args, **_kwargs):
        if args[1:3] != ["volume", "inspect"]:
            mutations.append(args)
        return SimpleNamespace(returncode=0)

    def output(args, **_kwargs):
        if args[1] == "ps":
            return b"running-container" if running else b""
        labels = {
            "com.docker.compose.project": "opsproof-observability",
            "com.docker.compose.volume": "wrong" if unowned else "prometheus-data",
        }
        return json.dumps([{"Labels": labels}]).encode()

    monkeypatch.setattr(prepare_observability.subprocess, "run", run)
    monkeypatch.setattr(prepare_observability.subprocess, "check_output", output)
    with pytest.raises(RuntimeError):
        prepare_observability.prepare_storage()
    assert not mutations
