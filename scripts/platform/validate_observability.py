"""Validate telemetry configs with the exact locked runtime binaries, without a cluster."""

import json
import subprocess
from pathlib import Path

from scripts.platform.observability import ROOT, inputs


def validate(output: Path):
    output.mkdir(parents=True, exist_ok=False)
    images = json.loads((ROOT / "observability/images.lock.json").read_text())
    checks = [
        ("prometheus", "/usr/bin/promtool", ["check", "config", "/etc/prometheus/prometheus.yml"]),
        (
            "prometheus",
            "/usr/bin/promtool",
            ["test", "rules", "/etc/prometheus/tests/alerts.test.yml"],
        ),
        ("alertmanager", "/usr/bin/amtool", ["check-config", "/etc/prometheus/alertmanager.yml"]),
        (
            "otel-collector",
            "/otelcol-contrib",
            ["validate", "--config=/etc/prometheus/otel-collector.yml"],
        ),
        (
            "tempo",
            "/usr/bin/tempo",
            ["-config.file=/etc/prometheus/tempo.yml", "-config.verify=true"],
        ),
        ("loki", "/usr/bin/loki", ["-config.file=/etc/prometheus/loki.yml", "-verify-config=true"]),
    ]
    # The validation-only webhook token is a nonsecret fixture, never the owner token.
    fixture = output / "webhook-token"
    fixture.write_text("validation-placeholder\n")
    common = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        "256m",
        "--user",
        "65534:65534",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=134217728,mode=1777",
        "--mount",
        f"type=bind,source={ROOT / 'observability'},target=/etc/prometheus,readonly",
        "--mount",
        f"type=bind,source={fixture.resolve()},target=/etc/alertmanager/webhook-token,readonly",
    ]
    for index, (name, binary, args) in enumerate(checks):
        result = subprocess.run(
            [*common, "--entrypoint", binary, images[name], *args],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        (output / f"{index}-{name}.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"{name} validation failed; see {output}")
        print("PASS:", name, args[0], flush=True)
    for cloud in (False, True):
        configurations, _ = inputs(cloud_profile=cloud)
        directory = output / ("cloud" if cloud else "kubernetes")
        directory.mkdir(exist_ok=True)
        for filename, text in configurations["prometheus"].items():
            (directory / filename).write_text(text)
        result = subprocess.run(
            [
                *common[: common.index("--mount")],
                "--mount",
                f"type=bind,source={directory.resolve()},target=/etc/prometheus,readonly",
                "--entrypoint",
                "/usr/bin/promtool",
                images["prometheus"],
                "check",
                "config",
                "--syntax-only",
                "/etc/prometheus/prometheus.yml",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        (directory / "validation.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Rendered Prometheus configuration failed: {directory}")
    dashboard = json.loads((ROOT / "observability/grafana/dashboards/operations.json").read_text())
    assert dashboard["uid"] and len(dashboard["panels"]) >= 12
    (output / "result.json").write_text(json.dumps({"passed": True, "images": images}, indent=2))


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    validate(parser.parse_args().output.resolve())


if __name__ == "__main__":
    main()
