"""Render the pinned upstream chart and verify the intended local exposure."""

import json
import subprocess

import yaml
from preflight import ROOT


def main():
    directory = ROOT / ".runtime/m5/helm"
    (directory / "cache").mkdir(parents=True, exist_ok=True)
    flags = [
        "--repository-config",
        str(directory / "repositories.yaml"),
        "--repository-cache",
        str(directory / "cache"),
    ]
    subprocess.run(
        ["helm", "repo", "add", "traefik", "https://traefik.github.io/charts", *flags],
        check=True,
        timeout=60,
    )
    result = subprocess.run(
        [
            "helm",
            "template",
            "traefik",
            "traefik/traefik",
            "--version",
            "42.3.0",
            "--namespace",
            "opsproof-gateway",
            "-f",
            str(ROOT / "infra/k8s/traefik/values-local.yaml"),
            *flags,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    objects = [obj for obj in yaml.safe_load_all(result.stdout) if obj]
    services = [obj for obj in objects if obj["kind"] == "Service"]
    if len(services) != 1 or services[0]["spec"]["type"] != "NodePort":
        raise ValueError("Gateway must expose one NodePort service, never LoadBalancer")
    ports = services[0]["spec"]["ports"]
    if len(ports) != 1 or ports[0]["nodePort"] != 30080:
        raise ValueError("Unexpected exposed gateway port")
    gateway = next(obj for obj in objects if obj["kind"] == "Gateway")
    listener = gateway["spec"]["listeners"]
    if {item["name"]: item["port"] for item in listener} != {
        "web": 8000,
        "release": 8001,
    }:
        raise ValueError("Incorrect gateway listener")
    if any(item["allowedRoutes"]["namespaces"]["from"] != "Selector" for item in listener):
        raise ValueError("Cross-namespace routes must be selected")
    output = ROOT / ".runtime/m5/acceptance"
    output.mkdir(parents=True, exist_ok=True)
    (output / "traefik-render.yaml").write_text(result.stdout, encoding="utf-8")
    record = {
        "chart": "traefik",
        "version": "42.3.0",
        "passed": True,
        "objects": len(objects),
        "service_type": "NodePort",
        "node_port": 30080,
        "scope": "upstream schema/render; live routing and RBAC not tested",
    }
    (output / "gateway-contracts.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
