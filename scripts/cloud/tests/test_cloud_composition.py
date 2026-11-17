"""Cloud composition preserves credential, network and reconciliation boundaries."""

import base64
import json

import pytest

from scripts.cloud.generate_runtime_secrets import build as credentials
from scripts.cloud.render_controller_permissions import build as controller_permissions
from scripts.cloud.render_gitops import render as gitops
from scripts.cloud.render_network_policies import build as network
from scripts.platform.observability import ROOT
from scripts.platform.observability import render as telemetry


def release():
    return {
        "source_sha": "a" * 40,
        "repository": "example/opsproof",
        "workflow_run_id": 123,
        "images": {
            role: f"ghcr.io/example/opsproof/opsproof-{role}@sha256:{str(i) * 64}"
            for i, role in enumerate(("demo", "control", "web", "edge"))
        },
    }


def test_cloud_gitops_does_not_sync_before_ordered_bootstrap():
    record = release()
    rendered = gitops(record, "https://github.com/example/opsproof.git", "sg-12345678")
    project, *apps = rendered["items"]
    assert project["spec"]["clusterResourceWhitelist"] == []
    assert not {"Secret", "Role", "RoleBinding", "ClusterRole"} & {
        row["kind"] for row in project["spec"]["namespaceResourceWhitelist"]
    }
    assert len(apps) == 6
    for app in apps:
        spec = app["spec"]
        assert "automated" not in spec["syncPolicy"]
        assert spec["source"]["targetRevision"] == record["source_sha"]
    auto = gitops(record, "https://github.com/example/opsproof", "sg-12345678", reconcile=True)
    assert all(
        app["spec"]["syncPolicy"]["automated"] == {"prune": False, "selfHeal": True}
        for app in auto["items"][1:]
    )


def test_gitops_refuses_foreign_repository_or_missing_edge():
    with pytest.raises(ValueError):
        gitops(release(), "https://github.com/other/opsproof", "sg-12345678")
    record = release()
    del record["images"]["edge"]
    with pytest.raises(ValueError):
        gitops(record, "https://github.com/example/opsproof", "sg-12345678")


def test_network_has_five_default_denies_and_no_public_database_or_api_egress():
    rendered = network(["10.72.20.0/24", "10.72.21.0/24"], ["10.72.20.10", "172.20.0.1"])
    rows = rendered["items"]
    assert len([row for row in rows if row["metadata"]["name"] == "opsproof-default-deny"]) == 5
    for row in rows:
        for rule in row["spec"].get("egress", []):
            assert all(
                peer.get("ipBlock", {}).get("cidr") != "0.0.0.0/0" for peer in rule.get("to", [])
            )
    edge = [row for row in rows if row["metadata"]["namespace"] == "opsproof-edge"]
    assert not any(
        peer.get("namespaceSelector", {}).get("matchLabels", {}).get("kubernetes.io/metadata.name")
        == "opsproof-control"
        for row in edge
        for rule in row["spec"].get("egress", [])
        for peer in rule.get("to", [])
    )


@pytest.mark.parametrize(
    "subnets,addresses",
    [
        (["0.0.0.0/0", "10.72.21.0/24"], ["10.72.20.10"]),
        (["10.72.20.0/24", "10.72.21.0/24"], ["8.8.8.8"]),
        (["10.72.20.0/24", "10.72.21.0/24"], []),
    ],
)
def test_network_refuses_unverified_scope(subnets, addresses):
    with pytest.raises(ValueError):
        network(subnets, addresses)


def test_cloud_credentials_are_isolated_complete_and_do_not_hold_rds_master():
    docs = {
        (row["metadata"]["namespace"], row["metadata"]["name"]): {
            key: base64.b64decode(value).decode() for key, value in row["data"].items()
        }
        for row in credentials()["items"]
    }
    assert len(docs) == 10
    assert set(docs["opsproof-control", "opsproof-control-runtime"]) == {
        "OPSPROOF_CONTROL_TARGET_URL"
    }
    assert (
        docs["opsproof-demo", "opsproof-demo-inspection"]["OPSPROOF_INSPECTION_KEY"]
        == docs["opsproof-control", "opsproof-control-inspection"][
            "OPSPROOF_CONTROL_INSPECTION_KEY"
        ]
    )
    assert (
        docs["opsproof-control", "opsproof-control-alert"]["OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN"]
        == docs["opsproof-observability", "opsproof-telemetry-auth"]["webhook-token"]
    )
    assert "MASTER" not in json.dumps(list(docs.values()))


def test_controller_permissions_have_no_secret_reads_or_rbac_writes():
    docs = controller_permissions()["items"]
    for row in docs:
        if row["kind"] == "Role":
            for rule in row["rules"]:
                assert not {"secrets", "roles", "rolebindings", "*"} & set(rule["resources"])
    assert all(row["kind"] not in {"ClusterRole", "ClusterRoleBinding"} for row in docs)


def test_existing_telemetry_renders_with_cloud_storage_and_pinned_images():
    images = json.loads((ROOT / "observability/images.lock.json").read_text(encoding="utf-8"))
    rows = telemetry(images, storage_class="opsproof-ebs-gp3", cloud_profile=True)["items"]
    assert len([row for row in rows if row["kind"] == "Deployment"]) == 6
    assert all(
        row["spec"]["storageClassName"] == "opsproof-ebs-gp3"
        for row in rows
        if row["kind"] == "PersistentVolumeClaim"
    )


def test_cloud_scrapes_each_api_replica_and_omits_unconfigured_canary():
    images = json.loads((ROOT / "observability/images.lock.json").read_text(encoding="utf-8"))
    rows = telemetry(images, storage_class="opsproof-ebs-gp3", cloud_profile=True)["items"]
    config = next(
        row["data"]["prometheus.yml"]
        for row in rows
        if row["kind"] == "ConfigMap" and row["metadata"]["name"] == "prometheus-config"
    )
    assert config.count("dns_sd_configs:") == 2
    assert "demo-api-metrics.opsproof-demo.svc.cluster.local" in config
    assert "control-api-metrics.opsproof-control.svc.cluster.local" in config
    assert "opsproof-demo-canary" not in config
