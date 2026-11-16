"""Prepare the nonowner local control runtime after additive M6 migration.

Creates one owned local Kubernetes Secret and database role; never changes the
existing M5 runtime Secret, invokes a cloud API or prints credentials.
"""

import argparse
import base64
import json
import secrets
import subprocess
from urllib.parse import quote
from uuid import uuid4

import psycopg
from opsproof_control.trial_access import require_application_role
from psycopg.rows import dict_row

from scripts.platform.render_local_secrets import read_env
from scripts.reliability.data_access import grant_control_application
from scripts.reliability.local_environment import ROOT, LocalEnvironment, utc, write_json

SECRET = "opsproof-control-m6-runtime"


def execute(acknowledgment):
    if acknowledgment != "M6_LOCAL_DATABASE_ROLE":
        raise ValueError("Explicit local database-role preparation acknowledgment required")
    directory = ROOT / ".runtime/m6/acceptance/deployment" / ("database-" + uuid4().hex)
    directory.mkdir(parents=True)
    env = LocalEnvironment(directory)
    result = {"started_at": utc(), "prepared": False, "secret_name": SECRET}
    existing = json.loads(
        subprocess.check_output(
            [
                *env.kube,
                "get",
                "secrets",
                "-n",
                "opsproof-control",
                "-o",
                "json",
                "--field-selector",
                "metadata.name=" + SECRET,
            ],
            text=True,
            timeout=15,
        )
    )["items"]
    with env.forwarded(["ledger"]):
        values = read_env(ROOT / ".env")
        owner = (
            "postgresql://opsproof:"
            + quote(values["OPSPROOF_CONTROL_DB_PASSWORD"], safe="")
            + "@127.0.0.1:18032/opsproof"
        )
        with psycopg.connect(owner, row_factory=dict_row, connect_timeout=3) as conn:
            if (
                conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"]
                != "0007"
            ):
                raise RuntimeError("Deploy and migrate the reviewed M6 image through 0007 first")
        if existing:
            secret = existing[0]
            identity = secret["metadata"].get("labels", {}).get("opsproof.io/m6-runtime-role", "")
            if len(identity) != 16 or any(c not in "0123456789abcdef" for c in identity):
                raise RuntimeError("Existing runtime Secret is not owned by M6; no overwrite")
            private_dsn = base64.b64decode(secret["data"]["OPSPROOF_CONTROL_DATABASE_URL"]).decode()
            from psycopg.conninfo import conninfo_to_dict, make_conninfo

            fields = conninfo_to_dict(private_dsn)
            if fields["user"] != "m6_app_" + identity or fields["dbname"] != "opsproof":
                raise RuntimeError("Existing M6 runtime role identity mismatch")
            probe_dsn = make_conninfo(private_dsn, host="127.0.0.1", port="18032")
            username = fields["user"]
        else:
            identity = uuid4().hex[:16]
            username = "m6_app_" + identity
            password = secrets.token_hex(24)
            private_dsn = (
                "postgresql://"
                + username
                + ":"
                + password
                + "@control-deps-postgres.opsproof-control.svc.cluster.local:5432/opsproof"
            )
            secret = {
                "apiVersion": "v1",
                "kind": "Secret",
                "type": "Opaque",
                "metadata": {
                    "name": SECRET,
                    "namespace": "opsproof-control",
                    "labels": {"opsproof.io/m6-runtime-role": identity},
                },
                "stringData": {"OPSPROOF_CONTROL_DATABASE_URL": private_dsn},
            }
            with psycopg.connect(owner, row_factory=dict_row, connect_timeout=3) as conn:
                grant_control_application(conn, username, password)
                created = subprocess.run(
                    [*env.kube, "create", "-f", "-", "-o", "json"],
                    input=json.dumps(secret),
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                if created.returncode:
                    raise RuntimeError("Owned runtime Secret creation failed; SQL role rolled back")
                secret = json.loads(created.stdout)
            probe_dsn = "postgresql://" + username + ":" + password + "@127.0.0.1:18032/opsproof"
        with psycopg.connect(probe_dsn, row_factory=dict_row, connect_timeout=3) as conn:
            require_application_role(conn)
        result.update(
            prepared=True,
            role=username,
            secret_uid=secret["metadata"]["uid"],
            schema_version="0007",
            nonowner_guard_passed=True,
        )
    result["ended_at"] = utc()
    write_json(directory / "result.json", result)
    pointer = ROOT / ".runtime/m6/acceptance/deployment/runtime-role.json"
    if not pointer.exists():
        write_json(pointer, result)
    elif json.loads(pointer.read_text())["secret_uid"] != result["secret_uid"]:
        raise RuntimeError("Runtime Secret provenance differs from the saved ownership record")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge", required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.acknowledge), indent=2))


if __name__ == "__main__":
    main()
