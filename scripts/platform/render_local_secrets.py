"""Render local-only Kubernetes Secret JSON to stdout for `kubectl apply -f -`.

Does not import application dependencies; never commit the output or .env.
"""

import argparse
import base64
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

REQUIRED = (
    "OPSPROOF_DB_PASSWORD",
    "OPSPROOF_CONTROL_DB_PASSWORD",
    "OPSPROOF_CONTROL_API_KEY",
    "OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN",
    "OPSPROOF_INSPECTION_KEY",
    "OPSPROOF_RECOVERY_KEY",
)


def read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"Local environment file not found: {path}")
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            raise ValueError("Malformed environment assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise ValueError("Invalid environment key")
        value = value.strip()
        if value[:1] in ('"', "'"):
            if not value.endswith(value[0]):
                raise ValueError("Unbalanced environment quote")
            value = value[1:-1]
        values[key] = value
    return values


def secret(name: str, namespace: str, fields: dict[str, str]) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {"app.kubernetes.io/part-of": "opsproof"},
        },
        "type": "Opaque",
        "data": {
            key: base64.b64encode(val.encode("utf-8")).decode("ascii")
            for key, val in fields.items()
        },
    }


def render(values: dict[str, str]) -> dict:
    missing = [key for key in REQUIRED if len(values.get(key, "")) < 16]
    if missing:
        raise ValueError("Missing or short local credentials: " + ", ".join(missing))
    dpwd = quote(values["OPSPROOF_DB_PASSWORD"], safe="")
    cpwd = quote(values["OPSPROOF_CONTROL_DB_PASSWORD"], safe="")
    demo_ns = "opsproof-demo"
    control_ns = "opsproof-control"
    return {
        "apiVersion": "v1",
        "kind": "List",
        "items": [
            secret(
                "opsproof-postgres-auth",
                demo_ns,
                {"POSTGRES_PASSWORD": values["OPSPROOF_DB_PASSWORD"]},
            ),
            secret(
                "opsproof-demo-runtime",
                demo_ns,
                {
                    "OPSPROOF_DATABASE_URL": f"postgresql://opsproof:{dpwd}@demo-deps-postgres.{demo_ns}.svc.cluster.local:5432/opsproof",
                    "OPSPROOF_REDIS_URL": f"redis://demo-deps-redis.{demo_ns}.svc.cluster.local:6379/0",
                },
            ),
            secret(
                "opsproof-demo-inspection",
                demo_ns,
                {"OPSPROOF_INSPECTION_KEY": values["OPSPROOF_INSPECTION_KEY"]},
            ),
            secret(
                "opsproof-demo-recovery",
                demo_ns,
                {"OPSPROOF_RECOVERY_KEY": values["OPSPROOF_RECOVERY_KEY"]},
            ),
            secret(
                "opsproof-postgres-auth",
                control_ns,
                {"POSTGRES_PASSWORD": values["OPSPROOF_CONTROL_DB_PASSWORD"]},
            ),
            secret(
                "opsproof-control-runtime",
                control_ns,
                {
                    "OPSPROOF_CONTROL_DATABASE_URL": f"postgresql://opsproof:{cpwd}@control-deps-postgres.{control_ns}.svc.cluster.local:5432/opsproof",
                    "OPSPROOF_CONTROL_REDIS_URL": f"redis://control-deps-redis.{control_ns}.svc.cluster.local:6379/0",
                    "OPSPROOF_CONTROL_TARGET_URL": f"http://demo-api.{demo_ns}.svc.cluster.local:8080",
                },
            ),
            secret(
                "opsproof-control-operator",
                control_ns,
                {"OPSPROOF_CONTROL_API_KEY": values["OPSPROOF_CONTROL_API_KEY"]},
            ),
            secret(
                "opsproof-control-alert",
                control_ns,
                {
                    "OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN": values[
                        "OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN"
                    ]
                },
            ),
            secret(
                "opsproof-control-inspection",
                control_ns,
                {"OPSPROOF_CONTROL_INSPECTION_KEY": values["OPSPROOF_INSPECTION_KEY"]},
            ),
            secret(
                "opsproof-control-recovery",
                control_ns,
                {"OPSPROOF_CONTROL_RECOVERY_KEY": values["OPSPROOF_RECOVERY_KEY"]},
            ),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()
    try:
        secrets = render(read_env(Path(args.env)))
    except ValueError as exc:
        print(f"Local secret preparation failed: {exc}", file=sys.stderr)
        sys.exit(2)
    json.dump(secrets, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
