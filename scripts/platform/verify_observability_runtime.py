"""Exercise the locked local monitoring pipeline in owned, disposable Docker fixtures.

No Kubernetes, owner credentials, existing volumes, model APIs or cloud APIs.
The fixture image is an already built OpsProof demo artifact, used only for its
Python standard library. All host endpoints bind to loopback.
"""

import argparse
import base64
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from scripts.platform.observability import ROOT
from scripts.platform.preflight import GIB, memory_available
from scripts.platform.telemetry_images import runtime_images

FIXTURE = """
import json, signal
signal.signal(signal.SIGTERM, lambda *_: exit(0))
from http.server import BaseHTTPRequestHandler, HTTPServer
events=[]
failed=False
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_GET(self):
  data=json.dumps(events).encode() if self.path=="/events" else b"fixture_up 1\\n"
  self.send_response(200)
  self.send_header("Content-Type","text/plain; version=0.0.4")
  self.end_headers();self.wfile.write(data)
 def do_POST(self):
  global failed
  data=self.rfile.read(int(self.headers.get("Content-Length",0)))
  if self.path in ("/fail","/recover"):
   failed=self.path=="/fail";self.send_response(200)
  elif failed:self.send_response(503)
  elif self.headers.get("Authorization")!="Bearer runtime-placeholder":self.send_response(401)
  else:
   body=json.loads(data);events.append({"status":body["status"],"alerts":len(body["alerts"])})
   self.send_response(200)
  self.end_headers()
HTTPServer(("0.0.0.0",8080),Handler).serve_forever()
"""


def docker(*args, timeout=90):
    return subprocess.check_output(
        ["docker", *args], text=True, stderr=subprocess.STDOUT, timeout=timeout
    ).strip()


def request(url, data=None, headers=None):
    supplied = headers or {}
    if data is not None:
        supplied = {"Content-Type": "application/json", **supplied}
        data = json.dumps(data).encode()
    with urlopen(Request(url, data=data, headers=supplied), timeout=5) as response:
        raw = response.read()
        try:
            return json.loads(raw)
        except ValueError:
            return raw.decode()


def eventually(check, description, seconds=75):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                print("PASS:", description, flush=True)
                return value
        except OSError, ValueError, KeyError:
            pass
        time.sleep(1)
    raise RuntimeError("Timed out: " + description)


def verify(output, fixture_image, grafana_image):
    if memory_available() < 2 * GIB:
        raise RuntimeError("Host free memory below the existing 2 GiB Docker-test gate")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", fixture_image):
        raise ValueError("An exact local fixture image ID is required")
    output.mkdir(parents=True, exist_ok=False)
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", grafana_image):
        raise ValueError("An exact locally built Grafana image ID is required")
    images = runtime_images(grafana_image)
    owner = "opsproof-monitoring-test-" + uuid4().hex[:12]
    names, volumes, endpoints = {}, [], {}
    record = {"passed": False, "images": images, "fixture_image": fixture_image}
    label = "opsproof.io/monitoring-test=" + owner
    token = output / "webhook-token"
    token.write_text("runtime-placeholder\n")

    def owned(kind, name):
        metadata = json.loads(docker(kind, "inspect", name))[0]
        labels = metadata.get("Config", metadata).get("Labels", {})
        if labels.get("opsproof.io/monitoring-test") != owner:
            raise RuntimeError("Fixture ownership changed; cleanup refused")

    def start(name, image, ports, args, mounts=(), env=(), uid="10001:10001", entry=None):
        container = owner + "-" + name
        command = [
            "run",
            "-d",
            "--name",
            container,
            "--label",
            label,
            "--network",
            owner,
            "--network-alias",
            name,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            uid,
            "--memory",
            "384m",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=33554432,mode=1777",
        ]
        if name == "fixture":
            command += [
                "--network-alias",
                "opsproof-demo-api",
                "--network-alias",
                "opsproof-control-api",
            ]
        for port in ports:
            command += ["-p", f"127.0.0.1::{port}"]
        for mount in mounts:
            command += ["--mount", mount]
        for item in env:
            command += ["-e", item]
        if entry:
            command += ["--entrypoint", entry]
        docker(*command, image, *args)
        names[name] = container
        for port in ports:
            bound = docker("port", container, str(port) + "/tcp")
            endpoints[name, port] = "http://" + bound

    def bind(source, target):
        return f"type=bind,source={source},target={target},readonly"

    def data(name, target):
        volume = owner + "-" + name
        docker("volume", "create", "--label", label, volume)
        volumes.append(volume)
        uid = {"prometheus": "65534", "alertmanager": "65534", "grafana": "472"}.get(name, "10001")
        docker(
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--user",
            "0:0",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "CHOWN",
            "--security-opt",
            "no-new-privileges",
            "--mount",
            f"type=volume,source={volume},target=/data",
            "--entrypoint",
            "/bin/chown",
            images["prometheus"],
            uid + ":" + uid,
            "/data",
        )
        return f"type=volume,source={volume},target={target},volume-nocopy"

    try:
        docker("network", "create", "--label", label, owner)
        start("fixture", fixture_image, [8080], ["-c", FIXTURE], entry="python")
        obs = ROOT / "observability"
        for name, path, port, filename, args, entry in [
            ("loki", "/loki", 3100, "loki.yml", ["-config.file=/config"], "/usr/bin/loki"),
            ("tempo", "/var/tempo", 3200, "tempo.yml", ["-config.file=/config"], "/usr/bin/tempo"),
            (
                "otel-collector",
                "/var/lib/otelcol",
                4318,
                "otel-collector.yml",
                ["--config=/config"],
                "/otelcol-contrib",
            ),
        ]:
            ports = [port, 8888, 13133] if name == "otel-collector" else [port]
            start(
                name,
                images[name],
                ports,
                args,
                [bind(obs / filename, "/config"), data(name, path)],
                entry=entry,
            )
        am = (
            (obs / "alertmanager.yml")
            .read_text()
            .replace(
                "opsproof-control-api:8080/api/v1/internal/alertmanager", "fixture:8080/alerts"
            )
        )
        (output / "alertmanager.yml").write_text(am)
        start(
            "alertmanager",
            images["alertmanager"],
            [9093],
            ["--config.file=/config", "--storage.path=/alertmanager", "--cluster.listen-address="],
            [
                bind(output / "alertmanager.yml", "/config"),
                bind(token, "/etc/alertmanager/webhook-token"),
                data("alertmanager", "/alertmanager"),
            ],
            uid="65534:65534",
            entry="/usr/bin/alertmanager",
        )
        start(
            "prometheus",
            images["prometheus"],
            [9090],
            [
                "--config.file=/etc/prometheus/prometheus.yml",
                "--storage.tsdb.path=/prometheus",
                "--storage.tsdb.retention.time=24h",
                "--storage.tsdb.retention.size=512MB",
            ],
            [bind(obs, "/etc/prometheus"), data("prometheus", "/prometheus")],
            uid="65534:65534",
            entry="/usr/bin/prometheus",
        )
        password = uuid4().hex
        start(
            "grafana",
            images["grafana"],
            [3000],
            [],
            [
                bind(obs / "grafana/provisioning", "/etc/grafana/provisioning"),
                bind(obs / "grafana/dashboards", "/var/lib/grafana/dashboards"),
                data("grafana", "/var/lib/grafana"),
            ],
            [
                "GF_SECURITY_ADMIN_USER=opsproof",
                "GF_SECURITY_ADMIN_PASSWORD=" + password,
                "GF_PATHS_HOME=/usr/share/grafana",
                "GF_PATHS_DATA=/var/lib/grafana",
                "GF_PATHS_LOGS=/var/lib/grafana/log",
                "GF_PATHS_PLUGINS=/var/lib/grafana/plugins",
                "GF_PLUGINS_PREINSTALL_DISABLED=true",
                "GF_ANALYTICS_REPORTING_ENABLED=false",
                "GF_ANALYTICS_CHECK_FOR_UPDATES=false",
            ],
            uid="472:472",
        )
        for name, port, path in [
            ("loki", 3100, "/ready"),
            ("tempo", 3200, "/ready"),
            ("otel-collector", 13133, "/"),
            ("prometheus", 9090, "/-/ready"),
            ("alertmanager", 9093, "/-/ready"),
            ("grafana", 3000, "/api/health"),
        ]:
            eventually(lambda n=name, p=port, h=path: request(endpoints[n, p] + h), name + " ready")
        prometheus = endpoints["prometheus", 9090]
        eventually(
            lambda: (
                len(
                    [
                        t
                        for t in request(prometheus + "/api/v1/targets")["data"]["activeTargets"]
                        if t["health"] == "up"
                    ]
                )
                == 8
            ),
            "all eight scrape jobs healthy",
        )
        auth = {
            "Authorization": "Basic " + base64.b64encode(("opsproof:" + password).encode()).decode()
        }
        grafana = endpoints["grafana", 3000]
        dashboard = request(grafana + "/api/search", headers=auth)
        assert any(
            d["uid"] == json.loads((obs / "grafana/dashboards/operations.json").read_text())["uid"]
            for d in dashboard
        )
        record["dashboard_provisioned"] = True
        marker, trace = "pipeline-" + uuid4().hex, uuid4().hex
        now = time.time_ns()
        resource = {
            "attributes": [
                {"key": "service.name", "value": {"stringValue": "opsproof-verification"}}
            ]
        }
        logs = {
            "resourceLogs": [
                {
                    "resource": resource,
                    "scopeLogs": [
                        {
                            "logRecords": [
                                {
                                    "timeUnixNano": str(now),
                                    "body": {"stringValue": marker},
                                    "traceId": trace,
                                    "spanId": "0123456789abcdef",
                                    "severityNumber": 9,
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        traces = {
            "resourceSpans": [
                {
                    "resource": resource,
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": trace,
                                    "spanId": "0123456789abcdef",
                                    "name": marker,
                                    "kind": 1,
                                    "startTimeUnixNano": str(now),
                                    "endTimeUnixNano": str(now + 1_000_000),
                                }
                            ]
                        }
                    ],
                }
            ]
        }
        for name in ("loki", "tempo"):
            docker("stop", "--time", "45", names[name])
        for signal, payload in (("logs", logs), ("traces", traces)):
            response = request(endpoints["otel-collector", 4318] + "/v1/" + signal, payload)
            assert not response.get("partialSuccess")

        def queued():
            metrics = request(endpoints["otel-collector", 8888] + "/metrics")
            return (
                sum(
                    float(v)
                    for v in re.findall(
                        r"^otelcol_exporter_queue_size\{[^\n]+\} ([0-9.e+-]+)$", metrics, re.M
                    )
                )
                >= 2
            )

        eventually(queued, "both backend outages buffered persistently", seconds=20)
        docker("stop", "--time", "45", names["otel-collector"])
        for name in ("loki", "tempo", "otel-collector"):
            docker("start", names[name])
            # Docker can allocate a different ephemeral host port after restart.
            for role, port in list(endpoints):
                if role == name:
                    endpoints[role, port] = "http://" + docker(
                        "port", names[name], str(port) + "/tcp"
                    )
        query = urlencode(
            {
                "query": '{service_name="opsproof-verification"} |= "' + marker + '"',
                "start": str(now - 1_000_000_000),
                "end": str(now + 300_000_000_000),
            }
        )

        def log_found(base, headers=None):
            result = request(base + "/loki/api/v1/query_range?" + query, headers=headers)
            return any(
                marker in v[1]
                for s in result.get("data", {}).get("result", [])
                for v in s["values"]
            )

        def trace_found(base, headers=None):
            return marker in json.dumps(request(base + "/api/traces/" + trace, headers=headers))

        eventually(
            lambda: log_found(endpoints["loki", 3100]),
            "queued log survives Collector restart and reaches Loki",
        )
        eventually(
            lambda: trace_found(endpoints["tempo", 3200]),
            "queued span survives Collector restart and reaches Tempo",
        )
        proxy = grafana + "/api/datasources/proxy/uid/"
        eventually(
            lambda: log_found(proxy + "opsproof-loki", auth), "authenticated Grafana log query"
        )
        eventually(
            lambda: trace_found(proxy + "opsproof-tempo", auth), "authenticated Grafana trace query"
        )
        assert (
            request(proxy + "opsproof-prometheus/api/v1/query?query=up", headers=auth)["status"]
            == "success"
        )
        record["persistent_restart_and_grafana_queries"] = True
        am_url, fixture = endpoints["alertmanager", 9093], endpoints["fixture", 8080]
        alert = [
            {
                "labels": {
                    "alertname": "OpsProofVerification",
                    "severity": "warning",
                    "job": "verification",
                },
                "annotations": {"summary": "Disposable pipeline check"},
            }
        ]
        request(fixture + "/fail", {})
        request(am_url + "/api/v2/alerts", alert)

        def delivery_failed():
            text = request(am_url + "/metrics")
            return any(
                float(value) > 0
                for value in re.findall(
                    r"^alertmanager_notifications_failed_total\{[^\n]+\} ([0-9.e+-]+)$", text, re.M
                )
            )

        eventually(delivery_failed, "receiver outage produces delivery-failure evidence")
        request(fixture + "/recover", {})
        eventually(
            lambda: any(e["status"] == "firing" for e in request(fixture + "/events")),
            "Alertmanager sends authenticated firing webhook",
        )
        from datetime import UTC, datetime, timedelta

        alert[0]["endsAt"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        request(am_url + "/api/v2/alerts", alert)
        eventually(
            lambda: any(e["status"] == "resolved" for e in request(fixture + "/events")),
            "Alertmanager sends resolution webhook",
        )
        record["authenticated_firing_and_resolution"] = True
        from scripts.platform.watch_observability import inspect

        eventually(
            lambda: inspect(endpoints["prometheus", 9090], am_url)["healthy"],
            "independent foreground watch reports fresh healthy services",
        )
        docker("stop", "--time", "45", names["prometheus"])
        report = inspect(endpoints["prometheus", 9090], am_url)
        assert not report["healthy"] and any(
            "prometheus unavailable" in f for f in report["failures"]
        )
        docker("stop", "--time", "45", names["alertmanager"])
        report = inspect(endpoints["prometheus", 9090], am_url)
        assert not report["healthy"] and any(
            "alertmanager unavailable" in f for f in report["failures"]
        )
        record["watch_detects_monitoring_outages"] = True
        record["receiver_outage_observed"] = True
        record["passed"] = True
    except Exception as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        for name, port, path, filename in (
            ("otel-collector", 8888, "/metrics", "collector-metrics.txt"),
            (
                "loki",
                3100,
                "/loki/api/v1/query_range?"
                + urlencode({"query": '{service_name=~".+"}', "limit": 20}),
                "loki-query.json",
            ),
        ):
            if (name, port) in endpoints:
                try:
                    value = request(endpoints[name, port] + path)
                    (output / filename).write_text(
                        value if isinstance(value, str) else json.dumps(value)
                    )
                except OSError:
                    pass
        for name, container in names.items():
            owned("container", container)
            (output / (name + ".log")).write_text(docker("logs", container, timeout=20))
            docker("stop", "--time", "45", container)
            exit_code = json.loads(docker("inspect", container))[0]["State"]["ExitCode"]
            record.setdefault("exit_codes", {})[name] = exit_code
            docker("rm", container)
        for volume in volumes:
            owned("volume", volume)
            docker("volume", "rm", volume)
        owned("network", owner)
        docker("network", "rm", owner)
        record["cleanup_verified"] = not docker("ps", "-a", "--filter", "label=" + label, "-q")
        record["passed"] = (
            record["passed"]
            and record["cleanup_verified"]
            and all(code == 0 for code in record.get("exit_codes", {}).values())
        )
        (output / "result.json").write_text(json.dumps(record, indent=2))
    if not record["passed"]:
        raise RuntimeError("Telemetry verification or graceful cleanup did not pass")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture-image", required=True)
    parser.add_argument("--grafana-image", required=True)
    args = parser.parse_args()
    verify(args.output.resolve(), args.fixture_image, args.grafana_image)


if __name__ == "__main__":
    main()
