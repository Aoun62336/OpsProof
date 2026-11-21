"""Pure renderer for the existing bounded metrics, logs, traces and dashboard stack.

No Docker, cluster, credential access or network operations. Both deployment
procedures consume these same configuration sources and workload definitions.
"""

import re
from pathlib import Path

from scripts.platform.telemetry_images import local_grafana_image, runtime_images

ROOT = Path(__file__).resolve().parents[2]
NS = "opsproof-observability"


def inputs(*, cloud_profile=False):
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
    configurations["grafana"]["operations.json"] = configurations["grafana"][
        "operations.json"
    ].replace("local-compose", "temporary-eks" if cloud_profile else "local-k3d")
    # Both Kubernetes profiles discover individual Pods, including unready ones.
    # The Compose source remains a single explicitly configured API endpoint.
    for role in ("demo", "control"):
        old = (
            "    static_configs:\n      - targets:\n"
            f"          - {role}-api.opsproof-{role}.svc.cluster.local:8080"
        )
        new = (
            "    dns_sd_configs:\n      - names: "
            f"[{role}-api-metrics.opsproof-{role}.svc.cluster.local]\n"
            "        type: A\n        port: 8080"
        )
        if old not in configurations["prometheus"]["prometheus.yml"]:
            raise ValueError("Existing scrape configuration differs from the reviewed contract")
        configurations["prometheus"]["prometheus.yml"] = configurations["prometheus"][
            "prometheus.yml"
        ].replace(old, new)
    if not cloud_profile:
        configurations["prometheus"]["canary-alerts.yml"] = (
            ROOT / "observability/canary-alerts.yml"
        ).read_text(encoding="utf-8")
        configurations["prometheus"]["prometheus.yml"] = configurations["prometheus"][
            "prometheus.yml"
        ].replace(
            "  - /etc/prometheus/alerts.yml",
            "  - /etc/prometheus/alerts.yml\n  - /etc/prometheus/canary-alerts.yml",
        )
        configurations["prometheus"]["prometheus.yml"] += (
            "\n  - job_name: opsproof-demo-canary\n    metrics_path: /metrics\n  "
            "  static_configs:\n      - targets: "
            "['demo-api-canary.opsproof-demo.svc.cluster.local:8080']\n"
        )
    configurations["prometheus"]["resource-alerts.yml"] = (
        ROOT / "observability/resource-alerts.yml"
    ).read_text(encoding="utf-8")
    configurations["prometheus"]["prometheus.yml"] = configurations["prometheus"][
        "prometheus.yml"
    ].replace(
        "  - /etc/prometheus/alerts.yml",
        "  - /etc/prometheus/alerts.yml\n  - /etc/prometheus/resource-alerts.yml",
    )
    configurations["prometheus"]["prometheus.yml"] += (
        ROOT / "observability/kubelet-scrapes.yml"
    ).read_text(encoding="utf-8")
    configurations["alertmanager"]["alertmanager.yml"] = configurations["alertmanager"][
        "alertmanager.yml"
    ].replace("/etc/alertmanager/webhook-token", "/run/opsproof-alert/webhook-token")
    images = runtime_images()
    services = [
        (
            "prometheus",
            images["prometheus"],
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
            images["alertmanager"],
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
            images["otel-collector"],
            10001,
            [13133, 4318, 8888],
            "/etc/otelcol",
            "/var/lib/otelcol",
            "64Mi",
            "256Mi",
            ["--config=/etc/otelcol/config.yaml"],
            "/",
        ),
        (
            "loki",
            images["loki"],
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
            images["tempo"],
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
            images["grafana"],
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


def render(
    images: dict[str, str], *, storage_class: str = "local-path", cloud_profile=False
) -> dict:
    configurations, services = inputs(cloud_profile=cloud_profile)
    if set(images) != {item[0] for item in services}:
        raise ValueError("Exactly the six telemetry image identities required")
    if any(
        not re.fullmatch(r"[a-zA-Z0-9_./:-]+@sha256:[0-9a-f]{64}", image)
        for name, image in images.items()
        if not (name == "grafana" and not cloud_profile and image == local_grafana_image())
    ):
        raise ValueError("Immutable telemetry image digests required")
    if storage_class not in {"local-path", "opsproof-ebs-gp3"}:
        raise ValueError("Unsupported storage profile")
    identity = "opsproof-monitoring"
    objects = [
        {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": identity,
                "namespace": NS,
                "labels": {"app.kubernetes.io/part-of": "opsproof"},
            },
            "automountServiceAccountToken": False,
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "metadata": {"name": identity, "labels": {"app.kubernetes.io/part-of": "opsproof"}},
            "rules": [
                {
                    "apiGroups": [""],
                    "resources": ["nodes"],
                    "verbs": ["get", "list", "watch"],
                },
                {"apiGroups": [""], "resources": ["nodes/metrics"], "verbs": ["get"]},
            ],
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRoleBinding",
            "metadata": {"name": identity, "labels": {"app.kubernetes.io/part-of": "opsproof"}},
            "roleRef": {
                "apiGroup": "rbac.authorization.k8s.io",
                "kind": "ClusterRole",
                "name": identity,
            },
            "subjects": [{"kind": "ServiceAccount", "name": identity, "namespace": NS}],
        },
    ]
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
        if name in {"prometheus", "alertmanager"}:
            # Vendor convenience wrappers add flags and enable reload endpoints.
            # Execute the reviewed binary with exactly the args above instead.
            container["command"] = ["/usr/bin/" + name]
        healthy_path = {
            "prometheus": "/-/healthy",
            "alertmanager": "/-/healthy",
            "otel-collector": "/",
            "grafana": "/api/health",
        }.get(name, "/metrics")
        container["startupProbe"] = {
            "httpGet": {"path": healthy_path, "port": ports[0]},
            "periodSeconds": 5,
            "failureThreshold": 30,
        }
        container["livenessProbe"] = {
            "httpGet": {"path": healthy_path, "port": ports[0]},
            "periodSeconds": 15,
            "timeoutSeconds": 3,
            "failureThreshold": 3,
        }
        if name == "prometheus":
            volumes.append(
                {
                    "name": "monitoring-identity",
                    "projected": {
                        "sources": [
                            {
                                "serviceAccountToken": {
                                    "path": "token",
                                    "expirationSeconds": 3600,
                                }
                            },
                            {
                                "configMap": {
                                    "name": "kube-root-ca.crt",
                                    "items": [{"key": "ca.crt", "path": "ca.crt"}],
                                }
                            },
                        ]
                    },
                }
            )
            mounts.append(
                {
                    "name": "monitoring-identity",
                    "mountPath": "/run/opsproof-monitoring",
                    "readOnly": True,
                }
            )
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
                {"name": "GF_PATHS_DATA", "value": "/var/lib/grafana"},
                {"name": "GF_PATHS_LOGS", "value": "/var/lib/grafana/log"},
                {"name": "GF_PATHS_PLUGINS", "value": "/var/lib/grafana/plugins"},
                {"name": "GF_PATHS_HOME", "value": "/usr/share/grafana"},
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
                            "serviceAccountName": identity if name == "prometheus" else "default",
                            "automountServiceAccountToken": False,
                            "terminationGracePeriodSeconds": 60,
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
