"""Prepare local-only monitoring credentials without printing secrets."""

import os
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
RUNTIME_DIR = ROOT / ".runtime" / "observability"
TOKEN_FILE = RUNTIME_DIR / "webhook-token"

REQUIRED = (
    "OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN",
    "OPSPROOF_GRAFANA_ADMIN_PASSWORD",
)


def prepare_storage():
    """Initialize exact Compose-owned volume roots; never recurse into existing data."""
    import json

    images = json.loads((ROOT / "observability/images.lock.json").read_text())
    for service, uid in (
        ("prometheus", 65534),
        ("alertmanager", 65534),
        ("collector", 10001),
        ("loki", 10001),
        ("tempo", 10001),
        ("grafana", 472),
    ):
        name = "opsproof-observability_" + service + "-data"
        existing = subprocess.run(
            ["docker", "volume", "inspect", name],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if existing.returncode:
            subprocess.run(
                [
                    "docker",
                    "volume",
                    "create",
                    "--label",
                    "com.docker.compose.project=opsproof-observability",
                    "--label",
                    "com.docker.compose.volume=" + service + "-data",
                    name,
                ],
                check=True,
                timeout=15,
            )
        metadata = json.loads(
            subprocess.check_output(["docker", "volume", "inspect", name], timeout=15)
        )[0]
        labels = metadata.get("Labels", {})
        if (
            labels.get("com.docker.compose.project") != "opsproof-observability"
            or labels.get("com.docker.compose.volume") != service + "-data"
        ):
            raise RuntimeError("Monitoring volume ownership cannot be established")
        running = subprocess.check_output(
            ["docker", "ps", "--filter", "volume=" + name, "--quiet"], timeout=15
        )
        if running.strip():
            raise RuntimeError("Stop monitoring services before initializing volume ownership")
        # Root is confined to this initialization process and the exact named volume.
        # The service itself keeps its established UID with all capabilities dropped.
        subprocess.run(
            [
                "docker",
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
                f"type=volume,source={name},target=/data",
                "--entrypoint",
                "/bin/chown",
                images["prometheus"],
                str(uid) + ":" + str(uid),
                "/data",
            ],
            check=True,
            timeout=30,
        )
        print("Monitoring persistent volume ownership prepared.")


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
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--storage", action="store_true", help="Initialize the six monitoring Compose volumes"
    )
    args = parser.parse_args()
    if args.storage:
        prepare_storage()
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
