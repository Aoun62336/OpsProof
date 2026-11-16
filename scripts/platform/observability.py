"""Pure renderer for the existing bounded metrics, logs, traces and dashboard stack.

No Docker, cluster, credential access or network operations. Both deployment
procedures consume these same configuration sources and workload definitions.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NS = "opsproof-observability"


def inputs():
    configurations = {
        "prometheus": {
            "prometheus.yml": (ROOT / "observability/prometheus.yml")
            .read_text(encoding="utf-8")
            .replace(
                "opsproof-demo-api:8080",
                "demo-api.opsproof-demo.svc.cluster.local:8080",
            )
            .replace(
                "opsproof-control-api:8080",
                "control-api.opsproof-control.svc.cluster.local:8080",
            ),
            "alerts.yml": (ROOT / "observability/alerts.yml").read_text(encoding="utf-8"),
        },
        "alertmanager": {
            "alertmanager.yml": (ROOT / "observability/alertmanager.yml")
            .read_text(encoding="utf-8")
            .replace(
                "opsproof-control-api:8080",
                "control-api.opsproof-control.svc.cluster.local:8080",
            )
        },
        "otel-collector": {
            "config.yaml": (ROOT / "observability/otel-collector.yml").read_text(encoding="utf-8")
        },
        "loki": {"local.yaml": (ROOT / "observability/loki.yml").read_text(encoding="utf-8")},
        "tempo": {"config.yaml": (ROOT / "observability/tempo.yml").read_text(encoding="utf-8")},
        "grafana": {
            "datasources.yaml": (
                ROOT / "observability/grafana/provisioning/datasources/opsproof.yml"
            ).read_text(encoding="utf-8"),
            "dashboards.yaml": (
                ROOT / "observability/grafana/provisioning/dashboards/opsproof.yml"
            ).read_text(encoding="utf-8"),
            "operations.json": (
                ROOT / "observability/grafana/dashboards/operations.json"
            ).read_text(encoding="utf-8"),
        },
    }
    configurations["prometheus"]["prometheus.yml"] += (
        "\n  - job_name: opsproof-demo-canary\n    metrics_path: /metrics\n  "
        "  static_configs:\n      - targets: "
        "['demo-api-canary.opsproof-demo.svc.cluster.local:8080']\n"
    )
    configurations["alertmanager"]["alertmanager.yml"] = configurations["alertmanager"][
        "alertmanager.yml"
    ].replace("/etc/alertmanager/webhook-token", "/run/opsproof-alert/webhook-token")
    services = [
        (
            "prometheus",
            "prom/prometheus:v3.15.1",
            65534,
            [9090],
            "/etc/prometheus",
            "/prometheus",
            "160Mi",
            "512Mi",
            [
                "--config.file=/etc/prometheus/prometheus.yml",
                "--storage.tsdb.path=/prometheus",
                "--storage.tsdb.retention.time=24h",
                "--storage.tsdb.retention.size=512MB",
            ],
            "/-/ready",
        ),
        (
            "alertmanager",
            "prom/alertmanager:v0.34.2",
            65534,
            [9093],
            "/etc/alertmanager",
            "/alertmanager",
            "32Mi",
            "128Mi",
            [
                "--config.file=/etc/alertmanager/alertmanager.yml",
                "--storage.path=/alertmanager",
            ],
            "/-/ready",
        ),
        (
            "otel-collector",
            (
                "otel/opentelemetry-collector-contrib@sha256:340c9ca6a3661708"
                "4c6661bdc4f0fe92b7cda5a805d61673ec8db375fddc522b"
            ),
            10001,
            [4318],
            "/etc/otelcol",
            None,
            "64Mi",
            "256Mi",
            ["--config=/etc/otelcol/config.yaml"],
            None,
        ),
        (
            "loki",
            "grafana/loki:3.7.8",
            10001,
            [3100],
            "/etc/loki",
            "/loki",
            "128Mi",
            "384Mi",
            ["-config.file=/etc/loki/local.yaml"],
            "/ready",
        ),
        (
            "tempo",
            "grafana/tempo:3.1.1",
            10001,
            [3200, 4318],
            "/etc/tempo",
            "/var/tempo",
            "128Mi",
            "384Mi",
            ["-config.file=/etc/tempo/config.yaml"],
            "/ready",
        ),
        (
            "grafana",
            "grafana/grafana:13.2.4",
            472,
            [3000],
            None,
            "/var/lib/grafana",
            "128Mi",
            "384Mi",
            [],
            "/api/health",
        ),
    ]
    return configurations, services


def render(images: dict[str, str], *, storage_class: str = "local-path") -> dict:
    configurations, services = inputs()
    if set(images) != {item[0] for item in services}:
        raise ValueError("Exactly the six telemetry image identities required")
    if any(
        not re.fullmatch(r"[a-zA-Z0-9_./:-]+@sha256:[0-9a-f]{64}", image)
        for image in images.values()
    ):
        raise ValueError("Immutable telemetry image digests required")
    if storage_class not in {"local-path", "opsproof-ebs-gp3"}:
        raise ValueError("Unsupported storage profile")
    objects = []
    for (
        name,
        image,
        uid,
        ports,
        config_path,
        data_path,
        request,
        limit,
        args,
        health,
    ) in services:
        image = images[name]
        labels = {
            "app.kubernetes.io/name": name,
            "app.kubernetes.io/part-of": "opsproof",
        }
        objects.append(
            {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {"name": name + "-config", "namespace": NS},
                "data": configurations[name],
            }
        )
        volumes = [
            {"name": "config", "configMap": {"name": name + "-config"}},
            {"name": "tmp", "emptyDir": {"sizeLimit": "32Mi"}},
        ]
        mounts = [{"name": "tmp", "mountPath": "/tmp"}]
        if config_path:
            mounts.append({"name": "config", "mountPath": config_path, "readOnly": True})
        if data_path:
            objects.append(
                {
                    "apiVersion": "v1",
                    "kind": "PersistentVolumeClaim",
                    "metadata": {"name": name + "-data", "namespace": NS},
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "storageClassName": storage_class,
                        "resources": {"requests": {"storage": "1Gi"}},
                    },
                }
            )
            volumes.append({"name": "data", "persistentVolumeClaim": {"claimName": name + "-data"}})
            mounts.append({"name": "data", "mountPath": data_path})
        container = {
            "name": name,
            "image": image,
            "args": args,
            "ports": [{"containerPort": p} for p in ports],
            "resources": {
                "requests": {"cpu": "25m", "memory": request},
                "limits": {"cpu": "500m", "memory": limit},
            },
            "securityContext": {
                "allowPrivilegeEscalation": False,
                "readOnlyRootFilesystem": True,
                "capabilities": {"drop": ["ALL"]},
            },
            "volumeMounts": mounts,
            "readinessProbe": {"httpGet": {"path": health, "port": ports[0]}}
            if health
            else {"tcpSocket": {"port": ports[0]}},
        }
        if name == "alertmanager":
            volumes.append(
                {
                    "name": "auth",
                    "secret": {
                        "secretName": "opsproof-telemetry-auth",
                        "items": [{"key": "webhook-token", "path": "webhook-token"}],
                    },
                }
            )
            mounts.append(
                {
                    "name": "auth",
                    "mountPath": "/run/opsproof-alert",
                    "readOnly": True,
                }
            )
        if name == "grafana":
            for filename, target in (
                (
                    "datasources.yaml",
                    "/etc/grafana/provisioning/datasources/opsproof.yaml",
                ),
                (
                    "dashboards.yaml",
                    "/etc/grafana/provisioning/dashboards/opsproof.yaml",
                ),
                ("operations.json", "/var/lib/grafana/dashboards/operations.json"),
            ):
                mounts.append(
                    {
                        "name": "config",
                        "mountPath": target,
                        "subPath": filename,
                        "readOnly": True,
                    }
                )
            container["env"] = [
                {"name": "GF_SECURITY_ADMIN_USER", "value": "opsproof"},
                {
                    "name": "GF_SECURITY_ADMIN_PASSWORD",
                    "valueFrom": {
                        "secretKeyRef": {
                            "name": "opsproof-telemetry-auth",
                            "key": "grafana-password",
                        }
                    },
                },
                {"name": "GF_USERS_ALLOW_SIGN_UP", "value": "false"},
                {"name": "GF_PLUGINS_PREINSTALL_AUTO_UPDATE", "value": "false"},
                {"name": "GF_PLUGINS_PREINSTALL_DISABLED", "value": "true"},
                {"name": "GF_ANALYTICS_REPORTING_ENABLED", "value": "false"},
            ]
        objects.append(
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": name, "namespace": NS},
                "spec": {
                    "replicas": 1,
                    "strategy": {"type": "Recreate"},
                    "selector": {"matchLabels": labels},
                    "template": {
                        "metadata": {"labels": labels},
                        "spec": {
                            "automountServiceAccountToken": False,
                            "securityContext": {
                                "runAsNonRoot": True,
                                "runAsUser": uid,
                                "runAsGroup": uid,
                                "fsGroup": uid,
                                "seccompProfile": {"type": "RuntimeDefault"},
                            },
                            "containers": [container],
                            "volumes": volumes,
                        },
                    },
                },
            }
        )
        objects.append(
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": name, "namespace": NS},
                "spec": {
                    "selector": labels,
                    "ports": [{"name": "tcp-" + str(p), "port": p, "targetPort": p} for p in ports],
                    "type": "ClusterIP",
                },
            }
        )
    return {"apiVersion": "v1", "kind": "List", "items": objects}
