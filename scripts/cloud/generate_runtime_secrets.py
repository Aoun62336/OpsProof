"""Generate isolated temporary-cloud app credentials without reading local/API keys.

Output is private and must be reused for retries, never rotated implicitly. RDS
and Redis connections arrive through their separate required Secret references.
"""

import argparse
import json
import os
import secrets
from pathlib import Path
from urllib.parse import quote

from scripts.platform.render_local_secrets import secret

ROOT = Path(__file__).resolve().parents[2]


def build() -> dict:
    password, inspection, recovery, operator, alert, grafana = (
        secrets.token_urlsafe(36) for _ in range(6)
    )
    demo, control = "opsproof-demo", "opsproof-control"
    specs = [
        ("opsproof-postgres-auth", demo, {"POSTGRES_PASSWORD": password}),
        (
            "opsproof-demo-runtime",
            demo,
            {
                "OPSPROOF_DATABASE_URL": (
                    f"postgresql://opsproof:{quote(password, safe='')}@"
                    f"demo-deps-postgres.{demo}.svc.cluster.local:5432/opsproof"
                ),
            },
        ),
        ("opsproof-demo-inspection", demo, {"OPSPROOF_INSPECTION_KEY": inspection}),
        ("opsproof-demo-recovery", demo, {"OPSPROOF_RECOVERY_KEY": recovery}),
        (
            "opsproof-control-runtime",
            control,
            {
                "OPSPROOF_CONTROL_TARGET_URL": f"http://demo-api.{demo}.svc.cluster.local:8080",
            },
        ),
        ("opsproof-control-operator", control, {"OPSPROOF_CONTROL_API_KEY": operator}),
        ("opsproof-control-alert", control, {"OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN": alert}),
        ("opsproof-control-inspection", control, {"OPSPROOF_CONTROL_INSPECTION_KEY": inspection}),
        ("opsproof-control-recovery", control, {"OPSPROOF_CONTROL_RECOVERY_KEY": recovery}),
        (
            "opsproof-telemetry-auth",
            "opsproof-observability",
            {
                "webhook-token": alert,
                "grafana-password": grafana,
            },
        ),
    ]
    return {"apiVersion": "v1", "kind": "List", "items": [secret(*row) for row in specs]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((ROOT / ".runtime/cloud/private").resolve()):
        parser.error("Output must be within this repository's .runtime/cloud/private directory")
    if args.output.exists():
        parser.error("Credentials already exist; reuse them for retries")
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(build(), stream, indent=2)
        stream.write("\n")
    print("PRIVATE_RUNTIME_CREDENTIALS_CREATED; reuse on retry; no values printed")


if __name__ == "__main__":
    main()
