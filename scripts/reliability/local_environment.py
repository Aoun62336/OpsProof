"""Fixed local M6 boundaries, owned forwards, current resource and source evidence.

This host-side harness is not an in-cluster privileged service. Only explicit
local context is used; there is no fallback to the user's default context.
"""

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from scripts.platform.preflight import GIB, ROOT, collect, command, memory_available
from scripts.reliability.collect_queue_state import parse_group
from scripts.reliability.run_k6_local import local_prefix

FORWARDS = {
    "demo": ("opsproof-demo", "demo-api", 18088, 8080),
    "control": ("opsproof-control", "control-api", 18090, 8080),
    "prometheus": ("opsproof-observability", "prometheus", 19090, 9090),
    "loki": ("opsproof-observability", "loki", 13100, 3100),
    "tempo": ("opsproof-observability", "tempo", 13200, 3200),
    "release": ("opsproof-gateway", "demo-release-gateway", 18081, 8001),
    "reuse": ("opsproof-reuse-test", "reuse-target", 18089, 8080),
    "ledger": ("opsproof-control", "control-deps-postgres", 18032, 5432),
    "demo_db": ("opsproof-demo", "demo-deps-postgres", 18033, 5432),
    "demo_redis": ("opsproof-demo", "demo-deps-redis", 16379, 6379),
}


def utc():
    return datetime.now(UTC).isoformat()


def write_json(path: Path, value: object):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, default=str, allow_nan=False)
        stream.write("\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    files = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(set(names))
        if (ROOT / name).is_file()
    }
    return {
        "head": revision,
        "dirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                text=True,
            )
        ),
        "files": files,
        "tree_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
    }


def resource_preflight(profile="trial"):
    if profile not in ("startup", "trial"):
        raise ValueError("Unknown resource profile")
    if profile == "startup":
        result = collect()
    else:
        # A running cluster exposes its actual capacity through Kubernetes.
        # Host Docker-pipe access is unnecessary for these bounded trials.
        memory = memory_available()
        disk = shutil.disk_usage(ROOT).free
        checks = {}
        reasons = []
        if memory < 2 * GIB:
            reasons.append("Host free RAM below 2 GiB for bounded active-cluster trial")
        if disk < 15 * GIB:
            reasons.append("Workspace disk free below 15 GiB")
        try:
            kube = local_prefix(ROOT / ".runtime/m5/kubeconfig.yaml")
            checks["nodes"] = command([*kube, "get", "nodes", "-o", "json"])
            if checks["nodes"]["exit_code"]:
                raise ValueError("Local Kubernetes capacity unavailable")
            nodes = json.loads(checks["nodes"]["output"])["items"]
            if len(nodes) != 1 or nodes[0]["metadata"]["name"] != "k3d-opsproof-server-0":
                raise ValueError("Unexpected local cluster node identity")
            node = nodes[0]
            capacity = node["status"]["capacity"]
            quantity = re.fullmatch(r"([0-9]+)Ki", capacity["memory"])
            if not quantity or int(quantity[1]) * 1024 < 5 * GIB:
                raise ValueError("Running Kubernetes node memory below 5 GiB or unavailable")
            if not capacity["cpu"].isdigit() or int(capacity["cpu"]) < 1:
                raise ValueError("Running Kubernetes node CPU capacity unavailable")
            if not any(
                c["type"] == "Ready" and c["status"] == "True" for c in node["status"]["conditions"]
            ):
                raise ValueError("Local Kubernetes node is not Ready")
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):  # fmt: skip
            reasons.append("Ready local node identity and >=5 GiB capacity not established")
        result = {
            "timestamp_utc": utc(),
            "host_free_bytes": memory,
            "disk_free_bytes": disk,
            "minimum_host_free_bytes": 2 * GIB,
            "minimum_disk_free_bytes": 15 * GIB,
            "capacity_source": "live local Kubernetes node",
            "checks": checks,
            "blockers": reasons,
            "passed": not reasons,
        }
    result["profile"] = profile
    result["emergency_stop_free_bytes"] = GIB
    return result


def http(port: int, path: str, *, body=None, headers=None, timeout=5, known_probe_error=False):
    if port not in {
        item[2] for key, item in FORWARDS.items() if key not in ("ledger", "demo_db", "demo_redis")
    }:
        raise ValueError("Unapproved local observer port")
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Relative internal path required")
    req = Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
    )

    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kwargs):
            return None

    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=timeout) as response:
            data = response.read(4_000_001)
            if len(data) > 4_000_000:
                raise ValueError("Observer response exceeded bound")
            try:
                payload = json.loads(data) if data else None
            except json.JSONDecodeError:
                payload = data.decode("utf-8", errors="replace")
            return response.status, payload
    except HTTPError as exc:
        # Do not retain raw error bodies or authentication material.
        if known_probe_error and path == "/api/v1/internal/dependency-probe" and exc.code == 503:
            try:
                value = json.loads(exc.read(1025))
                if value in (
                    {"detail": "Fresh database connection unavailable"},
                    {"detail": "M6 probe capacity unavailable"},
                ):
                    return exc.code, value
            except ValueError:
                pass
        return exc.code, None


def fresh_database_probe(*, timeout=3):
    key = os.environ.get("OPSPROOF_M6_DEMO_INSPECT_KEY", "")
    if not key:
        raise ValueError("Restricted read-only demo inspection credentials required")
    return http(
        18088,
        "/api/v1/internal/dependency-probe",
        timeout=timeout,
        headers={"X-OpsProof-Inspect-Key": key},
        known_probe_error=True,
    )


class LocalEnvironment:
    def __init__(self, output: Path, *, maximum_seconds=600, read_only=False, kubeconfig=None):
        if not output.resolve().is_relative_to((ROOT / ".runtime/m6").resolve()):
            raise ValueError("Evidence must remain in the ignored M6 tree")
        if not 1 <= maximum_seconds <= 600:
            raise ValueError("Execution deadline outside 1..600 seconds")
        self.output = output
        configured = kubeconfig or os.environ.get("OPSPROOF_M6_KUBECONFIG")
        self.kube = local_prefix(
            Path(configured) if configured else ROOT / ".runtime/m5/kubeconfig.yaml"
        )
        self.read_only = read_only
        self.deadline = time.monotonic() + maximum_seconds
        self.sequence = 0
        self.forwards = {}
        self.authorization_guard = None

    def guard(self):
        if memory_available() < GIB:
            raise RuntimeError("Host free RAM below 1 GiB; stop experiment and restore")
        if time.monotonic() >= self.deadline:
            raise TimeoutError("M6 bounded execution deadline exceeded")
        if self.authorization_guard:
            self.authorization_guard()

    def command(self, args, *, input=None, timeout=20):
        # No shell interpretation. Mutations are constructed only by fixed adapters.
        if self.read_only and (not args or args[0] not in ("get", "logs", "top", "port-forward")):
            raise ValueError("Observer cannot execute Kubernetes mutations or exec")
        return subprocess.check_output(
            [*self.kube, *args], input=input, text=True, timeout=timeout, cwd=ROOT
        )

    def get(self, kind, name=None, namespace="opsproof-demo"):
        return json.loads(
            self.command(["get", kind, *([name] if name else []), "-n", namespace, "-o", "json"])
        )

    def save(self, label, value):
        if not label.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Invalid artifact label")
        self.sequence += 1
        path = self.output / f"{self.sequence:03}-{label}.json"
        digest = write_json(path, {"collected_at": utc(), "data": value})
        return {"relative_path": path.relative_to(ROOT).as_posix(), "sha256": digest}

    def queue(self):
        from redis import Redis

        from scripts.reliability.restricted_access import redis_url

        with Redis.from_url(redis_url(), decode_responses=True, socket_timeout=2) as client:
            groups = client.xinfo_groups("opsproof:jobs")
        return parse_group(groups)

    def duplicate_job(self, identity):
        if self.read_only:
            raise ValueError("Observer cannot enqueue work")
        from uuid import UUID

        from redis import Redis

        from scripts.reliability.restricted_access import redis_url

        self.guard()
        with Redis.from_url(redis_url(), decode_responses=True, socket_timeout=2) as client:
            return client.xadd("opsproof:jobs", {"job_id": str(UUID(identity))})

    def patch(self, kind, name, snapshot, changes, namespace="opsproof-demo"):
        self.guard()
        patch = [
            {
                "op": "test",
                "path": "/metadata/uid",
                "value": snapshot["metadata"]["uid"],
            },
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": snapshot["metadata"]["resourceVersion"],
            },
            *changes,
        ]
        return json.loads(
            self.command(
                [
                    "patch",
                    kind,
                    name,
                    "-n",
                    namespace,
                    "--type=json",
                    "--patch",
                    json.dumps(patch),
                    "-o",
                    "json",
                ]
            )
        )

    def configure_demo(self, values):
        app = self.get("application", "demo", "argocd")
        params = {p["name"]: p["value"] for p in app["spec"]["source"]["helm"]["parameters"]}
        params.update(
            {k: str(v).lower() if isinstance(v, bool) else str(v) for k, v in values.items()}
        )
        changes = [
            {
                "op": "replace",
                "path": "/spec/source/helm/parameters",
                "value": [{"name": k, "value": v} for k, v in params.items()],
            }
        ]
        return self.patch("application", "demo", app, changes, "argocd")

    def restore_demo(self, original, expected_parameters):
        # Cleanup must work below the load RAM floor or after its deadline.
        # It still refuses to overwrite a concurrent operator's configuration.
        current = self.get("application", "demo", "argocd")
        if (
            current["metadata"]["uid"] == original["metadata"]["uid"]
            and current["spec"]["source"]["helm"]["parameters"]
            == original["spec"]["source"]["helm"]["parameters"]
        ):
            return current
        if (
            current["metadata"]["uid"] != original["metadata"]["uid"]
            or current["spec"]["source"]["helm"]["parameters"] != expected_parameters
        ):
            raise RuntimeError("Demo source ownership changed; automatic restoration refused")
        patch = [
            {
                "op": "test",
                "path": "/metadata/uid",
                "value": current["metadata"]["uid"],
            },
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": current["metadata"]["resourceVersion"],
            },
            {
                "op": "replace",
                "path": "/spec/source/helm/parameters",
                "value": original["spec"]["source"]["helm"]["parameters"],
            },
        ]
        self.command(
            [
                "patch",
                "application",
                "demo",
                "-n",
                "argocd",
                "--type=json",
                "--patch",
                json.dumps(patch),
            ]
        )

    def start_forward(self, target):
        if target not in FORWARDS or target in self.forwards:
            raise ValueError("Unsupported or already owned forward")
        ns, service, port, remote = FORWARDS[target]
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError as exc:
                if os.name != "nt" or getattr(exc, "winerror", None) != 10048:
                    raise
                # Windows TIME_WAIT can reject this probe after an owned
                # forward has exited. A live listener must still be refused.
                with socket.socket() as probe:
                    probe.settimeout(0.5)
                    if probe.connect_ex(("127.0.0.1", port)) != 10061:
                        raise exc
        path = self.output / f"forward-{target}-{time.time_ns()}.log"
        with path.open("x", encoding="utf-8") as log:
            process = subprocess.Popen(
                [
                    *self.kube,
                    "port-forward",
                    "-n",
                    ns,
                    "svc/" + service,
                    f"{port}:{remote}",
                    "--address",
                    "127.0.0.1",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        self.forwards[target] = process
        until = time.monotonic() + 25
        try:
            while time.monotonic() < until:
                if process.poll() is not None:
                    raise RuntimeError("Owned local port-forward exited; inspect its bounded log")
                marker = f"Forwarding from 127.0.0.1:{port} -> {remote}"
                if marker in path.read_text(encoding="utf-8", errors="replace"):
                    with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                        return
                time.sleep(0.2)
            raise TimeoutError("Owned port-forward did not become ready")
        except BaseException:
            self.stop_forward(target)
            raise

    def stop_forward(self, target):
        process = self.forwards.pop(target, None)
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    @contextmanager
    def forwarded(self, targets):
        owned = []
        try:
            for target in targets:
                self.start_forward(target)
                owned.append(target)
            yield self
        finally:
            for target in reversed(owned):
                self.stop_forward(target)

    def baseline(self):
        applications = self.get("applications", namespace="argocd")["items"]
        required = {"demo", "control", "web", "demo-deps", "control-deps"}
        selected = {
            a["metadata"]["name"]: a for a in applications if a["metadata"]["name"] in required
        }
        if set(selected) != required or any(
            a.get("status", {}).get("sync", {}).get("status") != "Synced"
            or a.get("status", {}).get("health", {}).get("status") != "Healthy"
            for a in selected.values()
        ):
            raise RuntimeError("All five existing M5 Applications must be Synced/Healthy")
        queue = self.queue()
        if queue["lag"] != 0 or queue["pending"] != 0:
            raise RuntimeError("Previous queue work has not drained, or lag is unknown")
        if http(18088, "/health/ready")[0] != 200 or http(18090, "/health/ready")[0] != 200:
            raise RuntimeError("Demo and control dependencies must be healthy")
        worker = self.get("deployment", "demo-worker")
        if worker["spec"].get("replicas") != 1 or worker["status"].get("readyReplicas") != 1:
            raise RuntimeError("Exactly one healthy fixed worker required before fault trials")
        if self.get("hpa")["items"] or self.get("scaledobjects")["items"]:
            raise RuntimeError("Retire trial autoscalers before fault trials")
        return {
            "queue": queue,
            "worker_uid": worker["metadata"]["uid"],
            "applications": {
                name: {
                    "revision": a["status"]["sync"].get("revision"),
                    "health": a["status"]["health"]["status"],
                }
                for name, a in selected.items()
            },
        }
