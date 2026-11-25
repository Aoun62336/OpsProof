"""Exercise a built Python artifact against owned, network-isolated TLS services.

No application source or test libraries enter the runtime. No host ports,
Kubernetes credentials, provider keys or real data are used. Each container is
labelled with a unique invocation identity and checked before removal.
"""

import argparse
import json
import os
import re
import secrets
import subprocess
import time
from datetime import UTC, datetime
from urllib.parse import urlencode
from uuid import uuid4

from scripts.platform.preflight import GIB, ROOT, memory_available
from scripts.reliability.validate_postgres import prepare_cloud_tls

POSTGRES = (
    "postgres:18-alpine@sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5"
)
REDIS = "redis:8-alpine@sha256:21090af93f8324db2f0f0f4f38a7c60369d47d917e000c3423d89d2ae2883537"
LABEL = "opsproof.io/python-image-check"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--component", choices=("demo", "control"), required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._/@:-]{0,500}", args.image):
        raise ValueError("Expected a local image reference")
    if memory_available() < 2 * GIB:
        raise RuntimeError("Artifact integration requires 2 GiB free host RAM")
    identity = uuid4().hex
    output = ROOT / ".runtime/verification/python-images" / identity
    output.mkdir(parents=True)
    private = output / "tls-private"
    owned = []
    roles = []
    # Do not propagate ambient AWS, provider, proxy or application credentials.
    env = {
        k: v
        for k, v in os.environ.items()
        if k.upper()
        in {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "HOME",
            "LOCALAPPDATA",
            "APPDATA",
            "PROGRAMDATA",
            "PATHEXT",
            "COMSPEC",
        }
    }
    env.update(
        POSTGRES_PASSWORD=secrets.token_hex(24),
        REDIS_PASSWORD=secrets.token_hex(24),
        IMAGE_TEST_APP_PASSWORD=secrets.token_hex(24),
        IMAGE_TEST_COMPONENT=args.component,
    )
    prefix = "OPSPROOF_CONTROL_" if args.component == "control" else "OPSPROOF_"
    db = "postgresql://opsproof:" + env["POSTGRES_PASSWORD"] + "@127.0.0.1:5432/opsproof?"
    suffix = urlencode({"sslmode": "verify-full", "sslrootcert": "/tls/server.crt"})
    env[prefix + "DATABASE_URL"] = db + suffix
    env[prefix + "REDIS_URL"] = (
        "rediss://:"
        + env["REDIS_PASSWORD"]
        + "@127.0.0.1:6379/0?"
        + urlencode(
            {
                "ssl_cert_reqs": "required",
                "ssl_check_hostname": "true",
                "ssl_ca_certs": "/tls/server.crt",
            }
        )
    )
    env[prefix + "API_KEY"] = secrets.token_hex(24)
    env.update(
        OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:4318",
        OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf",
        OTEL_TRACES_EXPORTER="otlp",
        OTEL_LOGS_EXPORTER="otlp",
        OTEL_METRICS_EXPORTER="none",
        OTEL_TRACES_SAMPLER="always_on",
        OTEL_PYTHON_LOG_AUTO_INSTRUMENTATION="true",
        OTEL_PYTHON_FASTAPI_EXCLUDED_URLS="metrics,health/live,health/ready,api/v1/auth",
    )
    if args.component == "control":
        env["OPSPROOF_CONTROL_TARGET_URL"] = "http://127.0.0.1:4318"

    env.update(
        OPSPROOF_CONTROL_AI_ENABLED="false",
        OPSPROOF_CONTROL_RECOVERY_ENABLED="false",
        OPSPROOF_CONTROL_KUBERNETES_RECOVERY_ENABLED="false",
        OPSPROOF_CONTROL_KUBERNETES_OBSERVATION_ENABLED="false",
        OPSPROOF_CONTROL_M6_ARM_ENABLED="false",
        OPSPROOF_CONTROL_M6_ENABLED="true",
    )
    report = {
        "started_at": datetime.now(UTC).isoformat(),
        "component": args.component,
        "passed": False,
        "cleanup_verified": False,
        "kubernetes_started": False,
        "cloud_calls": 0,
        "model_calls": 0,
    }

    def redact(message):
        for key, value in env.items():
            if any(word in key for word in ("PASSWORD", "API_KEY")):
                message = message.replace(value, "[REDACTED]")
        return message

    def execute(command, *, data=None, timeout=90):
        return subprocess.run(
            command,
            input=data,
            env=env,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        ).stdout.strip()

    def container(arguments, *, image, command=(), data=None, background=True):
        flags = [
            "docker",
            "run",
            "--pull",
            "never",
            "--label",
            LABEL + "=" + identity,
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            *arguments,
        ]
        flags.extend(["-d"] if background else ["--rm", "-i"])
        value = execute([*flags, image, *command], data=data, timeout=120)
        if background:
            owned.append(value)
        return value

    try:
        prepare_cloud_tls(output)
        info = json.loads(execute(["docker", "image", "inspect", args.image]))[0]
        image = info["Id"]
        report["image_id"] = image
        if info["Architecture"] != "amd64" or info["Config"]["User"] != "10001:10001":
            raise ValueError("Expected the supported x86_64 nonroot artifact")
        pg = container(
            [
                "--network",
                "none",
                "--memory",
                "512m",
                "--cpus",
                "1",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=33554432",
                "--tmpfs",
                "/var/run/postgresql:rw,nosuid,nodev,size=16777216",
                "--tmpfs",
                "/var/lib/postgresql:rw,nosuid,nodev,size=268435456",
                "--tmpfs",
                "/run/opsproof-tls:rw,noexec,nosuid,size=1048576",
                "--mount",
                f"type=bind,source={private},target=/tls-source,readonly",
                "-e",
                "POSTGRES_USER=opsproof",
                "-e",
                "POSTGRES_DB=opsproof",
                "-e",
                "POSTGRES_PASSWORD",
                "--entrypoint",
                "sh",
            ],
            image=POSTGRES,
            command=[
                "-ec",
                "cp /tls-source/server.key /tls-source/server.crt "
                "/tls-source/pg_hba.conf /run/opsproof-tls/; "
                "chown -R 70:70 /run/opsproof-tls; chmod 600 /run/opsproof-tls/server.key; "
                "exec docker-entrypoint.sh postgres -c ssl=on "
                "-c ssl_cert_file=/run/opsproof-tls/server.crt "
                "-c ssl_key_file=/run/opsproof-tls/server.key "
                "-c hba_file=/run/opsproof-tls/pg_hba.conf",
            ],
        )
        for _ in range(40):
            ready = subprocess.run(
                ["docker", "exec", pg, "pg_isready", "-U", "opsproof"],
                env=env,
                capture_output=True,
                timeout=10,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Disposable PostgreSQL did not become ready")
        shared = ["--network", "container:" + pg, "--cpus", "0.5"]
        container(
            [
                *shared,
                "--memory",
                "128m",
                "--cap-drop",
                "ALL",
                "--user",
                "0",
                "--mount",
                f"type=bind,source={private},target=/tls-source,readonly",
                "-e",
                "REDIS_PASSWORD",
                "--entrypoint",
                "sh",
            ],
            image=REDIS,
            command=[
                "-ec",
                "exec redis-server --port 0 --tls-port 6379 --tls-auth-clients no "
                "--tls-cert-file /tls-source/server.crt --tls-key-file /tls-source/server.key "
                "--tls-ca-cert-file /tls-source/server.crt --save '' --appendonly no "
                '--requirepass "$REDIS_PASSWORD"',
            ],
        )
        application = [
            *shared,
            "--memory",
            "256m",
            "--cap-drop",
            "ALL",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=33554432",
        ]
        for filename in ("server.crt", "wrong.crt"):
            application += [
                "--mount",
                f"type=bind,source={private / filename},target=/tls/{filename},readonly",
            ]
        for key in env:
            if key.startswith(("OPSPROOF_", "IMAGE_TEST_", "OTEL_")):
                application += ["-e", key]
        migration = container(
            [*application, "--entrypoint", "alembic"],
            image=image,
            command=["upgrade", "head"],
            background=False,
        )
        (output / "migration.log").write_text(migration, encoding="utf-8")
        probe = (ROOT / "scripts/reliability/python_image_probe.py").read_text(encoding="utf-8")
        if args.component == "control":
            env["IMAGE_TEST_STAGE"] = "prepare"
            application += ["-e", "IMAGE_TEST_STAGE"]
            container(
                [*application, "--entrypoint", "python"],
                image=image,
                command=["-"],
                data=probe,
                background=False,
            )
            env[prefix + "DATABASE_URL"] = (
                "postgresql://opsproof_app:"
                + env["IMAGE_TEST_APP_PASSWORD"]
                + "@127.0.0.1:5432/opsproof?"
                + suffix
            )
        env["IMAGE_TEST_STAGE"] = "receiver"
        if "IMAGE_TEST_STAGE" not in application:
            application += ["-e", "IMAGE_TEST_STAGE"]
        container(
            [*application, "--entrypoint", "python"], image=image, command=["-u", "-c", probe]
        )
        env["IMAGE_TEST_STAGE"] = "probe"
        if "IMAGE_TEST_STAGE" not in application:
            application += ["-e", "IMAGE_TEST_STAGE"]
        for role in (
            ["api", "dispatch", "evidence", "action", "trial"]
            if args.component == "control"
            else ["api", "dispatcher", "worker"]
        ):
            identifier = container(
                [
                    *application,
                    "-e",
                    "OTEL_SERVICE_NAME=opsproof-" + args.component + "-" + role,
                    "--entrypoint",
                    "opentelemetry-instrument",
                ],
                image=image,
                command=["python", "-m", "opsproof_" + args.component, role],
            )
            roles.append((role, identifier))
        api = roles[0][1]
        for _ in range(40):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    api,
                    "python",
                    "-c",
                    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/ready',timeout=1)",
                ],
                env=env,
                capture_output=True,
                timeout=5,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(
                "Final application did not become ready against real TLS dependencies"
            )
        result = container(
            [*application, "--entrypoint", "python"],
            image=image,
            command=["-"],
            data=probe,
            background=False,
        )
        report["probe"] = json.loads(result)
        report["roles"] = {}
        for role, identifier in reversed(roles):
            if (
                execute(["docker", "inspect", "--format", "{{.State.Running}}", identifier])
                != "true"
            ):
                raise RuntimeError("Application role exited unexpectedly: " + role)
            logs = subprocess.run(
                ["docker", "logs", identifier],
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
            )
            log = logs.stdout + logs.stderr
            (output / (role + ".log")).write_text(redact(log), encoding="utf-8")
            if "Traceback" in log or " ERROR " in log:
                raise RuntimeError("Application role reported a runtime error: " + role)
            execute(["docker", "stop", "--time", "10", identifier], timeout=20)
            if execute(["docker", "inspect", "--format", "{{.State.ExitCode}}", identifier]) != "0":
                raise RuntimeError("Application did not exit cleanly on SIGTERM: " + role)
            report["roles"][role] = {"started": True, "sigterm_exit_code": 0}
        report["passed"] = True
    except Exception as error:
        report["error_type"] = type(error).__name__
        report["error"] = redact(str(error))
        if isinstance(error, subprocess.CalledProcessError):
            # Only disposable generated secrets can occur here; redact them.
            (output / "failure.log").write_text(redact(error.stderr or ""), encoding="utf-8")
    finally:
        try:
            remaining = execute(
                ["docker", "ps", "-aq", "--filter", "label=" + LABEL + "=" + identity]
            )
            for identifier in remaining.splitlines():
                owner = execute(
                    [
                        "docker",
                        "inspect",
                        "--format",
                        '{{index .Config.Labels "' + LABEL + '"}}',
                        identifier,
                    ]
                )
                if owner != identity or not any(v.startswith(identifier) for v in owned):
                    raise RuntimeError("Refuse cleanup outside this invocation")
                execute(["docker", "rm", "-f", identifier])
            report["cleanup_verified"] = not execute(
                ["docker", "ps", "-aq", "--filter", "label=" + LABEL + "=" + identity]
            )
        except Exception as error:
            report["cleanup_error"] = redact(str(error))
        finally:
            for key in private.glob("*.key"):
                key.unlink()
            report["private_keys_removed"] = not list(private.glob("*.key"))
            report["ended_at"] = datetime.now(UTC).isoformat()
            (output / "result.json").write_text(
                json.dumps(report, indent=2) + "\n", encoding="utf-8"
            )
    print(json.dumps(report, indent=2))
    return (
        0
        if report["passed"] and report["cleanup_verified"] and report["private_keys_removed"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
