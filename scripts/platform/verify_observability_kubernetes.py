"""Verify discovery, kubelet TLS and read-only monitoring RBAC in a disposable k3d cluster.

Never starts, stops or changes the preserved opsproof cluster. Uses a private
kubeconfig and bounded fixture Pods, not owner applications or credentials.
"""

import argparse
import hashlib
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen
from uuid import uuid4

import yaml

from scripts.platform.import_local_image import import_image
from scripts.platform.observability import render
from scripts.platform.preflight import GIB, ROOT, memory_available
from scripts.platform.telemetry_images import runtime_images

PROBE = """
import signal
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
signal.signal(signal.SIGTERM, lambda *_: exit(0))
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  failed=self.path=="/health/ready" and Path("/tmp/unready").exists()
  self.send_response(503 if failed else 200)
  self.send_header("Content-Type","text/plain; version=0.0.4")
  self.end_headers();self.wfile.write(b"fixture_up 1\\n")
HTTPServer(("0.0.0.0",8080),Handler).serve_forever()
"""


def run(args, *, data=None, timeout=180, check=True):
    result = subprocess.run(
        args, input=data, capture_output=True, text=True, timeout=timeout, check=False
    )
    if check and result.returncode:
        raise RuntimeError(
            "Local verification command failed: " + " ".join(args[:3]) + "\n" + result.stderr
        )
    return result


def eventually(check, description, seconds=120):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if memory_available() < GIB:
            raise RuntimeError("Kubernetes verification aborted below 1 GiB free host RAM")
        try:
            value = check()
            if value:
                print("PASS:", description, flush=True)
                return value
        except OSError, ValueError, KeyError:
            pass
        time.sleep(2)
    raise RuntimeError("Timed out: " + description)


def verify(output):
    output.mkdir(parents=True, exist_ok=False)
    available = memory_available()
    if available < 5 * GIB:
        raise RuntimeError(
            "Disposable Kubernetes startup requires the unchanged 5 GiB free RAM gate"
        )
    name = "opsproof-monitoring-" + uuid4().hex[:10]
    before = json.loads(run(["k3d", "cluster", "list", "-o", "json"]).stdout)
    if any(c["name"] == name for c in before):
        raise RuntimeError("Fixture cluster name collision")
    default_config = Path.home() / ".kube/config"

    def default_hash():
        return (
            hashlib.sha256(default_config.read_bytes()).hexdigest()
            if default_config.exists()
            else None
        )

    initial_hash = default_hash()
    config = yaml.safe_load((ROOT / "infra/k3d/cluster.yaml").read_text())
    config["metadata"]["name"] = name
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        config["kubeAPI"]["hostPort"] = str(sock.getsockname()[1])
    config.pop("ports", None)
    path = output / "cluster.yaml"
    path.write_text(yaml.safe_dump(config))
    receipt = json.loads(
        (ROOT / ".runtime/reliability/acceptance/image-provenance.json").read_text()
    )["demo"]
    image = receipt["tag"]
    actual = run(["docker", "image", "inspect", image, "--format", "{{.Id}}"]).stdout.strip()
    if actual != receipt["local_image_id"]:
        raise RuntimeError("Fixture image differs from its source build receipt")
    images = runtime_images()
    record = {
        "passed": False,
        "fixture_cluster": name,
        "startup_free_bytes": available,
        "original_clusters": before,
        "model_calls": 0,
        "cloud_calls": 0,
    }
    created = False
    forward = None
    prom_alias = None
    kube = []

    def apply(rows):
        run(
            [*kube, "apply", "-f", "-"],
            data=json.dumps({"apiVersion": "v1", "kind": "List", "items": rows}),
        )

    def get(*args):
        return json.loads(run([*kube, "get", *args, "-o", "json"]).stdout)

    try:
        created = True
        result = run(["k3d", "cluster", "create", "--config", str(path)], timeout=300)
        (output / "create.log").write_text(result.stdout + result.stderr)
        cfg = output / "kubeconfig.yaml"
        cfg.write_text(run(["k3d", "kubeconfig", "get", name]).stdout)
        kube = ["kubectl", "--kubeconfig", str(cfg), "--context", "k3d-" + name]
        server = json.loads(run([*kube, "config", "view", "--minify", "-o", "json"]).stdout)[
            "clusters"
        ][0]["cluster"]["server"]
        if urlsplit(server).hostname != "127.0.0.1":
            raise RuntimeError("Fixture kubeconfig is not loopback")
        run([*kube, "wait", "node", "--all", "--for=condition=Ready", "--timeout=120s"])
        record["fixture_import"] = import_image(image, actual, name)
        prom_id = run(
            ["docker", "image", "inspect", images["prometheus"], "--format", "{{.Id}}"]
        ).stdout.strip()
        prom_alias = "opsproof-monitoring-test:" + name
        run(["docker", "image", "tag", images["prometheus"], prom_alias])
        record["prometheus_source"] = images["prometheus"]
        record["prometheus_import"] = import_image(prom_alias, prom_id, name)
        apply(
            [
                {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {
                        "name": ns,
                        "labels": {"pod-security.kubernetes.io/enforce": "restricted"},
                    },
                }
                for ns in ("opsproof-demo", "opsproof-control", "opsproof-observability")
            ]
        )
        pods = []
        for role, count in (("demo", 2), ("control", 1)):
            rendered = run(
                [
                    "helm",
                    "template",
                    role,
                    "infra/helm/opsproof-services",
                    "-f",
                    "infra/helm/opsproof-services/values-" + role + ".yaml",
                    "--set",
                    "image.tag=verification-fixture,telemetry.metricsHeadlessEnabled=true",
                ]
            ).stdout
            services = [r for r in yaml.safe_load_all(rendered) if r and r["kind"] == "Service"]
            for service in services:
                service["metadata"]["namespace"] = "opsproof-" + role
            apply(services)
            labels = next(
                s["spec"]["selector"]
                for s in services
                if s["metadata"]["name"].endswith("-metrics")
            )
            for index in range(count):
                pod_name = role + "-probe-" + str(index)
                pods.append(("opsproof-" + role, pod_name))
                apply(
                    [
                        {
                            "apiVersion": "v1",
                            "kind": "Pod",
                            "metadata": {
                                "name": pod_name,
                                "namespace": "opsproof-" + role,
                                "labels": labels,
                            },
                            "spec": {
                                "automountServiceAccountToken": False,
                                "securityContext": {
                                    "runAsNonRoot": True,
                                    "runAsUser": 10001,
                                    "runAsGroup": 10001,
                                    "seccompProfile": {"type": "RuntimeDefault"},
                                },
                                "containers": [
                                    {
                                        "name": "probe",
                                        "image": image,
                                        "imagePullPolicy": "Never",
                                        "command": ["python", "-c", PROBE],
                                        "ports": [{"name": "http", "containerPort": 8080}],
                                        "resources": {
                                            "requests": {"cpu": "25m", "memory": "48Mi"},
                                            "limits": {"cpu": "250m", "memory": "128Mi"},
                                        },
                                        "securityContext": {
                                            "allowPrivilegeEscalation": False,
                                            "readOnlyRootFilesystem": True,
                                            "capabilities": {"drop": ["ALL"]},
                                        },
                                        "readinessProbe": {
                                            "httpGet": {"path": "/health/ready", "port": 8080},
                                            "periodSeconds": 2,
                                        },
                                        "volumeMounts": [{"name": "tmp", "mountPath": "/tmp"}],
                                    }
                                ],
                                "volumes": [{"name": "tmp", "emptyDir": {"sizeLimit": "16Mi"}}],
                            },
                        }
                    ]
                )
        rows = render(images)["items"]
        selected = [
            r
            for r in rows
            if r["kind"] in {"ServiceAccount", "ClusterRole", "ClusterRoleBinding"}
            or r["metadata"]["name"] in {"prometheus", "prometheus-config", "prometheus-data"}
        ]
        for row in selected:
            if row["kind"] == "Deployment":
                row["spec"]["template"]["spec"]["containers"][0]["imagePullPolicy"] = "Never"
                row["spec"]["template"]["spec"]["containers"][0]["image"] = prom_alias
        apply(selected)
        for ns, pod in pods:
            run([*kube, "wait", "-n", ns, "pod/" + pod, "--for=condition=Ready", "--timeout=90s"])
        run(
            [
                *kube,
                "rollout",
                "status",
                "-n",
                "opsproof-observability",
                "deployment/prometheus",
                "--timeout=120s",
            ]
        )
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        log = (output / "forward.log").open("w")
        forward = subprocess.Popen(
            [
                *kube,
                "port-forward",
                "-n",
                "opsproof-observability",
                "svc/prometheus",
                f"{port}:9090",
                "--address",
                "127.0.0.1",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        base = "http://127.0.0.1:" + str(port)

        def http(path):
            with urlopen(base + path, timeout=4) as response:
                return json.load(response)

        def targets():
            return http("/api/v1/targets")["data"]["activeTargets"]

        def query(expr):
            return http("/api/v1/query?" + urlencode({"query": expr}))["data"]["result"]

        eventually(
            lambda: (
                len(
                    [
                        t
                        for t in targets()
                        if t["labels"]["job"] == "opsproof-demo-api" and t["health"] == "up"
                    ]
                )
                == 2
            ),
            "headless DNS discovers both API replicas",
        )
        pod_ip = get("pod", "demo-probe-0", "-n", "opsproof-demo")["status"]["podIP"]
        run(
            [
                *kube,
                "exec",
                "-n",
                "opsproof-demo",
                "demo-probe-0",
                "--",
                "python",
                "-c",
                "from pathlib import Path;Path('/tmp/unready').touch()",
            ]
        )
        eventually(
            lambda: any(
                c["type"] == "Ready" and c["status"] == "False"
                for c in get("pod", "demo-probe-0", "-n", "opsproof-demo")["status"]["conditions"]
            ),
            "fixture Pod becomes unready",
        )
        slices = get(
            "endpointslices", "-n", "opsproof-demo", "-l", "kubernetes.io/service-name=demo-api"
        )["items"]
        assert any(
            pod_ip in e["addresses"] and e["conditions"]["ready"] is False
            for s in slices
            for e in s["endpoints"]
        )
        eventually(
            lambda: (
                len(
                    [
                        t
                        for t in targets()
                        if t["labels"]["job"] == "opsproof-demo-api" and t["health"] == "up"
                    ]
                )
                == 2
            ),
            "unready Pod remains observable without serving normal Service traffic",
        )
        record["ready_and_unready_discovery"] = True
        eventually(
            lambda: (
                {t["labels"]["job"] for t in targets() if t["health"] == "up"}
                >= {"kubelet", "cadvisor"}
            ),
            "direct kubelet and cAdvisor scrapes pass TLS and scoped authentication",
        )
        sa = "system:serviceaccount:opsproof-observability:opsproof-monitoring"
        for verb, resource, subresource, expected in (
            ("get", "nodes", "metrics", "yes"),
            ("list", "secrets", None, "no"),
            ("get", "nodes", "proxy", "no"),
            ("create", "pods", "exec", "no"),
        ):
            flags = ["--subresource", subresource] if subresource else []
            answer = run(
                [*kube, "auth", "can-i", verb, resource, *flags, "--as", sa, "-n", "opsproof-demo"],
                check=False,
            ).stdout.strip()
            assert answer == expected, (resource, answer)
        record["read_only_rbac_and_verified_tls"] = True
        record["measured_memory"] = bool(
            query('container_memory_working_set_bytes{namespace="opsproof-demo",container="probe"}')
        )
        assert record["measured_memory"]
        record["volume_metrics_available"] = bool(
            query('kubelet_volume_stats_capacity_bytes{namespace="opsproof-observability"}')
        )
        run(
            [
                *kube,
                "delete",
                "pod",
                "demo-probe-0",
                "demo-probe-1",
                "-n",
                "opsproof-demo",
                "--wait=true",
            ]
        )
        eventually(
            lambda: (
                not any(
                    t["health"] == "up" and t["labels"]["job"] == "opsproof-demo-api"
                    for t in targets()
                )
            ),
            "disappeared API Pods have no healthy scrape targets",
        )
        eventually(
            lambda: any(
                a["labels"].get("alertname") == "OpsProofDemoAPIUnavailable"
                and a["state"] == "firing"
                for a in http("/api/v1/alerts")["data"]["alerts"]
            ),
            "missing API targets produce an actual firing alert",
        )
        record["disappearance_alert_verified"] = True
        (output / "targets.json").write_text(json.dumps(targets(), indent=2))
        record["passed"] = True
    except Exception as exc:
        record["error"] = str(exc)
        if kube:
            (output / "pods.json").write_text(
                run([*kube, "get", "pods", "-A", "-o", "json"], check=False).stdout
            )
        raise
    finally:
        if forward:
            forward.terminate()
            forward.wait(timeout=10)
            log.close()
        if created:
            current = json.loads(run(["k3d", "cluster", "list", "-o", "json"]).stdout)
            if any(c["name"] == name for c in current):
                run(["k3d", "cluster", "delete", name], timeout=180)
        after = json.loads(run(["k3d", "cluster", "list", "-o", "json"]).stdout)
        record["cleanup_verified"] = not any(c["name"] == name for c in after)
        if prom_alias:
            alias_id = run(
                ["docker", "image", "inspect", prom_alias, "--format", "{{.Id}}"]
            ).stdout.strip()
            if alias_id != prom_id:
                raise RuntimeError("Fixture alias changed; image-tag cleanup refused")
            run(["docker", "image", "rm", prom_alias])
        record["original_clusters_unchanged"] = before == after
        record["default_kubeconfig_unchanged"] = initial_hash == default_hash()
        record["passed"] = (
            record["passed"]
            and record["cleanup_verified"]
            and record["original_clusters_unchanged"]
            and record["default_kubeconfig_unchanged"]
        )
        (output / "result.json").write_text(json.dumps(record, indent=2))
        (output / "kubeconfig.yaml").unlink(missing_ok=True)
    if not record["passed"]:
        raise RuntimeError("Kubernetes verification or cleanup did not pass")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    verify(parser.parse_args().output.resolve())


if __name__ == "__main__":
    main()
