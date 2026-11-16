"""Migrate and test ONLY an owned, disposable local PostgreSQL 18 container.

No M5 credentials, kubeconfig, named volumes or cluster commands are used.
The random password stays in subprocess environments and is never persisted.
"""

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def browser_check(env, output, dsn):
    import psycopg
    from opsproof_control.trial_catalog import Scenario
    from opsproof_control.trial_store import create_trial, request_abort
    from psycopg.conninfo import make_conninfo
    from psycopg.rows import dict_row

    from scripts.reliability.data_access import grant_control_application

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 8090))
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        trial, _ = create_trial(
            conn,
            request_key="m6-browser-" + uuid4().hex,
            scenario=Scenario.MISLEADING_EVIDENCE,
            source_revision="38b3a46",
        )
        request_abort(conn, trial["id"])
        username = "m6_app_" + uuid4().hex[:16]
        password = secrets.token_hex(24)
        grant_control_application(conn, username, password)
    browser_env = {
        **env,
        "OPSPROOF_CONTROL_API_KEY": secrets.token_hex(24),
        "OPSPROOF_CONTROL_DATABASE_URL": make_conninfo(dsn, user=username, password=password),
        "OPSPROOF_CONTROL_M6_ENABLED": "true",
        "OPSPROOF_CONTROL_M6_ARM_ENABLED": "false",
        "OPSPROOF_CONTROL_REDIS_URL": "redis://127.0.0.1:6399",
        "OPSPROOF_E2E_M6_ISOLATED": "true",
        "OPSPROOF_E2E_TRIAL_ID": str(trial["id"]),
        "CI": "true",
        "OPSPROOF_E2E_M6_SCREENSHOT": str(output / "trials-mobile.png"),
    }
    browser_env["OPSPROOF_E2E_OPERATOR_KEY"] = browser_env["OPSPROOF_CONTROL_API_KEY"]
    browser_env.pop("OPSPROOF_E2E_BASE_URL", None)
    with (output / "browser-api.log").open("w", encoding="utf-8") as api_log:
        backend = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "opsproof_control.api:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8090",
            ],
            env=browser_env,
            cwd=ROOT,
            stdout=api_log,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            from urllib.request import urlopen

            for _ in range(50):
                if backend.poll() is not None:
                    raise RuntimeError("Isolated browser API exited")
                try:
                    with urlopen("http://127.0.0.1:8090/health/live", timeout=1):
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Isolated browser API readiness deadline")
            with (output / "browser.json").open("w", encoding="utf-8") as log:
                run = subprocess.run(
                    [
                        "node",
                        "node_modules/@playwright/test/cli.js",
                        "test",
                        "e2e/trials.spec.ts",
                        "--reporter=json",
                        "--output=" + str(output / "browser-artifacts"),
                    ],
                    env=browser_env,
                    cwd=ROOT / "apps/web",
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=180,
                    check=False,
                )
            return run.returncode
        finally:
            backend.terminate()
            try:
                backend.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend.kill()
                backend.wait(timeout=5)


def main() -> int:
    name = "opsproof-m6-pg-test-" + uuid4().hex[:10]
    output = ROOT / ".runtime/m6/acceptance/postgres" / name
    output.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 15432))
    env = dict(os.environ)
    env["POSTGRES_PASSWORD"] = secrets.token_hex(24)
    dsn = f"postgresql://opsproof:{env['POSTGRES_PASSWORD']}@127.0.0.1:15432/opsproof_m6_test"
    env["OPSPROOF_CONTROL_DATABASE_URL"] = dsn
    env["OPSPROOF_M6_TEST_DATABASE_URL"] = dsn
    env["PYTHONPATH"] = str(ROOT)
    record = {
        "started_at": datetime.now(UTC).isoformat(),
        "container": name,
        "database": "opsproof_m6_test",
        "passed": False,
        "cleanup_verified": False,
    }
    owned_id = None
    try:
        owned_id = subprocess.check_output(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                name,
                "--label",
                "opsproof.io/m6-disposable-test=true",
                "--memory",
                "512m",
                "--cpus",
                "1",
                "--shm-size",
                "64m",
                "-e",
                "POSTGRES_USER=opsproof",
                "-e",
                "POSTGRES_DB=opsproof_m6_test",
                "-e",
                "POSTGRES_PASSWORD",
                "-p",
                "127.0.0.1:15432:5432",
                "postgres:18-alpine",
            ],
            env=env,
            text=True,
            timeout=180,
        ).strip()
        info = json.loads(subprocess.check_output(["docker", "inspect", owned_id], text=True))[0]
        record["image_id"] = info["Image"]
        record["mounts"] = [
            {"type": m["Type"], "destination": m["Destination"]} for m in info["Mounts"]
        ]
        for _ in range(60):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    owned_id,
                    "pg_isready",
                    "-U",
                    "opsproof",
                    "-d",
                    "opsproof_m6_test",
                ],
                capture_output=True,
                timeout=10,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Disposable PostgreSQL readiness deadline exceeded")
        commands = [
            (
                "baseline_migration",
                [
                    sys.executable,
                    "-m",
                    "alembic",
                    "-c",
                    "apps/control-plane/alembic.ini",
                    "upgrade",
                    "0005",
                ],
            ),
            (
                "migration",
                [
                    sys.executable,
                    "-m",
                    "alembic",
                    "-c",
                    "apps/control-plane/alembic.ini",
                    "upgrade",
                    "head",
                ],
            ),
            (
                "integration",
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "apps/control-plane/tests/test_trial_postgres_integration.py",
                    "apps/control-plane/tests/test_postgres_safety.py",
                    "apps/control-plane/tests/test_postgres_api.py",
                    "apps/control-plane/tests/test_verification_postgres.py",
                    "apps/control-plane/tests/test_database_permissions.py",
                    "-q",
                    "-ra",
                ],
            ),
        ]
        for label, command in commands:
            with (output / f"{label}.log").open("w", encoding="utf-8") as log:
                result = subprocess.run(
                    command,
                    env=env,
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=180,
                )
            record[label + "_exit_code"] = result.returncode
            if result.returncode:
                raise RuntimeError(f"{label} failed; inspect saved log")
            if label in ("baseline_migration", "migration"):
                import psycopg

                with psycopg.connect(dsn) as conn:
                    if label == "baseline_migration":
                        conn.execute(
                            "INSERT INTO experiments(id,request_key,scenario,count,duration_ms) "
                            "VALUES (%s,'m6-legacy-preservation-sentinel','queue-burst',1,50)",
                            (uuid4(),),
                        )
                    rows = conn.execute(
                        "SELECT row_to_json(e) FROM experiments e ORDER BY id"
                    ).fetchall()
                    digest = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
                    if label == "baseline_migration":
                        record["legacy_rows_sha256"] = digest
                    else:
                        record["m5_rows_preserved"] = record["legacy_rows_sha256"] == digest
                        if not record["m5_rows_preserved"]:
                            raise RuntimeError("M5 sentinel data changed during migration")
        if "--browser" in sys.argv:
            record["browser_exit_code"] = browser_check(env, output, dsn)
            if record["browser_exit_code"]:
                raise RuntimeError("Actual SQL/API browser verification failed")
        record["passed"] = True
    except Exception as exc:
        record["error_type"] = type(exc).__name__
        print("PostgreSQL verification failed; inspect local evidence.", flush=True)
    finally:
        if owned_id:
            # Stop exactly the returned ID, after confirming our ownership label.
            label = subprocess.check_output(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "opsproof.io/m6-disposable-test"}}',
                    owned_id,
                ],
                text=True,
                timeout=15,
            ).strip()
            if label != "true":
                raise RuntimeError("Container ownership changed; automatic cleanup refused")
            subprocess.run(
                ["docker", "stop", "--time", "10", owned_id],
                check=True,
                capture_output=True,
                timeout=30,
            )
            remaining = subprocess.check_output(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    "id=" + owned_id,
                    "--format",
                    "{{.ID}}",
                ],
                text=True,
                timeout=15,
            ).strip()
            record["cleanup_verified"] = not remaining
        record["ended_at"] = datetime.now(UTC).isoformat()
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if record["passed"] and record["cleanup_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
