"""Prepare local-only monitoring credentials without printing secrets."""

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
RUNTIME_DIR = ROOT / ".runtime" / "observability"
TOKEN_FILE = RUNTIME_DIR / "webhook-token"

REQUIRED = (
    "OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN",
    "OPSPROOF_GRAFANA_ADMIN_PASSWORD",
)


def read_values(lines: list[str]) -> dict[str, str]:
    values = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if separator:
            values[name.strip()] = value.strip().strip("\"'")
    return values


def main() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    existing = read_values(lines)
    to_append: list[str] = []

    webhook_token = existing.get("OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN")
    if not webhook_token:
        webhook_token = secrets.token_hex(32)
        to_append.append(f"OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN={webhook_token}")

    grafana_password = existing.get("OPSPROOF_GRAFANA_ADMIN_PASSWORD")
    if not grafana_password:
        grafana_password = secrets.token_urlsafe(16)
        to_append.append(f"OPSPROOF_GRAFANA_ADMIN_PASSWORD={grafana_password}")

    if to_append:
        with open(ENV_FILE, "a", encoding="utf-8") as f:
            if lines and lines[-1].strip():
                f.write("\n")
            for item in to_append:
                f.write(f"{item}\n")

    TOKEN_FILE.write_text(webhook_token.strip() + "\n", encoding="utf-8")

    # Set read-only permissions where supported
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except Exception:
        pass

    print("Observability credentials prepared successfully.")


if __name__ == "__main__":
    main()
