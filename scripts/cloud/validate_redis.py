"""Exercise the rendered Redis TLS/auth server in two disposable local containers.

Uses no Kubernetes, cloud or provider credentials. Every container has an owned
random name, loopback-only port, bounded resources and memory-only writable data.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import redis
import yaml

from scripts.cloud.generate_redis_security import build_for

ROOT = Path(__file__).resolve().parents[2]


def run(*args: str, check: bool = True):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AWS_", "GROQ_", "GEMINI_", "OPSPROOF_"))
    }
    return subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, check=check, timeout=60, env=environment
    )


def decode(document):
    return {key: base64.b64decode(value).decode() for key, value in document["data"].items()}


def tls_rejected(client):
    try:
        client.ping()
    except redis.exceptions.ConnectionError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise AssertionError("Expected certificate verification rejection") from exc
    else:
        raise AssertionError("Untrusted Redis TLS connection succeeded")
    finally:
        client.close()


def validate_role(role: str, documents: list[dict], other_ca: str, private: Path) -> dict:
    name = "opsproof-redis-check-" + uuid4().hex[:12]
    directory = private / role
    directory.mkdir()
    tls, authentication, connection = map(decode, documents)
    for field in ("ca.crt", "tls.crt", "tls.key"):
        (directory / field).write_text(tls[field], encoding="utf-8")
    (directory / "wrong-ca.crt").write_text(other_ca, encoding="utf-8")
    (directory / "credentials.env").write_text(
        "REDIS_PASSWORD=" + authentication["password"] + "\n", encoding="utf-8"
    )
    chart = "infra/helm/opsproof-dependencies"
    rendered = run(
        "helm",
        "template",
        role + "-deps",
        chart,
        "-n",
        "opsproof-" + role,
        "-f",
        chart + "/values-" + role + "-eks.yaml",
    ).stdout
    rows = [row for row in yaml.safe_load_all(rendered) if row]
    server = next(
        row
        for row in rows
        if row["kind"] == "StatefulSet" and row["metadata"]["name"].endswith("-redis")
    )
    container = server["spec"]["template"]["spec"]["containers"][0]
    try:
        run(
            "docker",
            "run",
            "--detach",
            "--name",
            name,
            "--label",
            "opsproof.test=redis-tls",
            "--publish",
            "127.0.0.1::6379",
            "--memory",
            "128m",
            "--cpus",
            "0.5",
            "--pids-limit",
            "64",
            "--user",
            "999:999",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--env-file",
            str(directory / "credentials.env"),
            "--mount",
            f"type=bind,source={directory},target=/run/redis-tls,readonly",
            "--tmpfs",
            "/run/redis-config:rw,noexec,nosuid,nodev,uid=999,gid=999,mode=0700,size=1048576",
            "--tmpfs",
            "/data:rw,noexec,nosuid,nodev,uid=999,gid=999,size=16777216",
            "--entrypoint",
            container["command"][0],
            container["image"],
            *container["command"][1:],
            *container["args"],
        )
        mappings = json.loads(run("docker", "inspect", name).stdout)[0]["NetworkSettings"]["Ports"][
            "6379/tcp"
        ]
        if len(mappings) != 1 or mappings[0]["HostIp"] != "127.0.0.1":
            raise ValueError("Redis test port must be loopback-only")
        port = int(mappings[0]["HostPort"])
        key = "OPSPROOF_REDIS_URL" if role == "demo" else "OPSPROOF_CONTROL_REDIS_URL"
        original = urlsplit(connection[key])
        hostname = original.hostname
        # Process-local name mapping preserves actual client hostname verification.
        # No hosts file, DNS service or other process configuration is changed.
        lookup = socket.getaddrinfo

        def resolve(host, target_port, *args, **kwargs):
            return lookup("127.0.0.1" if host == hostname else host, target_port, *args, **kwargs)

        authority = original.netloc.rsplit(":", 1)[0] + ":" + str(port)
        query = original.query.replace(
            "/etc/opsproof/redis-ca/ca.crt", (directory / "ca.crt").as_posix()
        )
        url = urlunsplit((original.scheme, authority, original.path, query, ""))
        options = {"socket_connect_timeout": 2, "socket_timeout": 2, "decode_responses": True}
        with patch("socket.getaddrinfo", side_effect=resolve):
            client = redis.Redis.from_url(url, **options)
            deadline = time.monotonic() + 20
            while True:
                try:
                    if client.ping():
                        break
                except redis.exceptions.ConnectionError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.2)
            try:
                client.xgroup_create("checks", "workers", id="0", mkstream=True)
                client.xadd("checks", {"job": "first"})
                client.xadd("checks", {"job": "second"})
                items = client.xreadgroup("workers", "worker", {"checks": ">"}, count=1)
                group = client.xinfo_groups("checks")[0]
                if group["pending"] != 1 or group["lag"] != 1:
                    raise AssertionError("Redis Stream lag/pending contract differs")
                client.xack("checks", "workers", items[0][1][0][0])
                items = client.xreadgroup("workers", "worker", {"checks": ">"}, count=1)
                client.xack("checks", "workers", items[0][1][0][0])
                group = client.xinfo_groups("checks")[0]
                if group["pending"] != 0 or group["lag"] != 0:
                    raise AssertionError("Stream did not drain")
            finally:
                client.close()
            for password in (None, "incorrect-fixture-password"):
                unauthorized = redis.Redis(
                    host=hostname,
                    port=port,
                    password=password,
                    ssl=True,
                    ssl_ca_certs=str(directory / "ca.crt"),
                    ssl_check_hostname=True,
                    **options,
                )
                try:
                    try:
                        unauthorized.ping()
                    except redis.exceptions.AuthenticationError:
                        pass
                    else:
                        raise AssertionError("Redis accepted missing/incorrect credentials")
                finally:
                    unauthorized.close()
            tls_rejected(
                redis.Redis(
                    host=hostname,
                    port=port,
                    password=authentication["password"],
                    ssl=True,
                    ssl_ca_certs=str(directory / "wrong-ca.crt"),
                    ssl_check_hostname=True,
                    **options,
                )
            )
            tls_rejected(
                redis.Redis(
                    host="127.0.0.1",
                    port=port,
                    password=authentication["password"],
                    ssl=True,
                    ssl_ca_certs=str(directory / "ca.crt"),
                    ssl_check_hostname=True,
                    **options,
                )
            )
        plaintext = redis.Redis(host="127.0.0.1", port=port, **options)
        try:
            try:
                plaintext.ping()
            except redis.exceptions.AuthenticationError as exc:
                raise AssertionError("Plaintext Redis is listening") from exc
            except redis.exceptions.ConnectionError, redis.exceptions.TimeoutError:
                pass
            else:
                raise AssertionError("Redis accepted cleartext")
        finally:
            plaintext.close()
        return {
            "role": role,
            "trusted_tls": True,
            "stream_lag_pending_and_drain": True,
            "no_auth_rejected": True,
            "wrong_password_rejected": True,
            "wrong_ca_rejected": True,
            "wrong_hostname_rejected": True,
            "cleartext_rejected": True,
            "server_source": "actual rendered Helm command",
        }
    finally:
        inspected = run("docker", "inspect", name, check=False)
        if inspected.returncode == 0:
            owned = json.loads(inspected.stdout)[0]
            if owned["Config"].get("Labels", {}).get("opsproof.test") != "redis-tls":
                raise RuntimeError("Container ownership differs; refuse cleanup")
            run("docker", "rm", "--force", name)
            if run("docker", "inspect", name, check=False).returncode == 0:
                raise RuntimeError("Owned Redis test container remains")
        elif "No such object" not in inspected.stderr:
            raise RuntimeError("Cannot establish Redis test container cleanup")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error("Use --execute for the two bounded disposable local container tests")
    output = ROOT / ".runtime/verification/cloud/redis" / uuid4().hex
    private = output / "private"
    private.mkdir(parents=True, exist_ok=False)
    result = {"passed": False, "kubernetes_started": False, "cloud_calls": 0, "model_calls": 0}
    try:
        fixtures = {role: build_for(role) for role in ("demo", "control")}
        result["checks"] = [
            validate_role(
                role,
                fixtures[role],
                decode(fixtures["control" if role == "demo" else "demo"][0])["ca.crt"],
                private,
            )
            for role in ("demo", "control")
        ]
        result["passed"] = True
    except Exception as exc:
        result["error_type"] = type(exc).__name__
        raise
    finally:
        for directory in private.iterdir():
            for file in directory.iterdir():
                file.unlink()
            directory.rmdir()
        private.rmdir()
        result["private_fixture_files_removed"] = True
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
