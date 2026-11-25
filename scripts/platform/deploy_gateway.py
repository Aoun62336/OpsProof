"""Install the pinned Gateway and production web on the guarded local cluster."""

import hashlib
import json
import subprocess
from urllib.request import urlopen

from scripts.platform.local_cluster import helm_prefix, kubectl_prefix
from scripts.platform.preflight import ROOT


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def main():
    kube = kubectl_prefix()
    helm = helm_prefix()
    directory = ROOT / ".runtime/platform"
    deployment = json.loads((directory / "acceptance/deployment.json").read_text())
    tag = deployment["source_content_tag"]
    url = "https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.1/standard-install.yaml"
    with urlopen(url, timeout=60) as response:
        payload = response.read(20 * 1024 * 1024)
    path = directory / "gateway-api-v1.6.1.yaml"
    path.write_bytes(payload)
    run([*kube, "apply", "--server-side", "-f", str(path)])
    run(
        [
            *kube,
            "wait",
            "--for=condition=Established",
            "crd/gateways.gateway.networking.k8s.io",
            "crd/httproutes.gateway.networking.k8s.io",
            "--timeout=60s",
        ]
    )
    flags = [
        "--repository-config",
        str(directory / "helm/repositories.yaml"),
        "--repository-cache",
        str(directory / "helm/cache"),
    ]
    run(["helm", "repo", "add", "traefik", "https://traefik.github.io/charts", *flags])
    run(
        [
            *helm,
            "upgrade",
            "--install",
            "traefik",
            "traefik/traefik",
            "--version",
            "42.3.0",
            "-n",
            "opsproof-gateway",
            "-f",
            "infra/k8s/traefik/values-local.yaml",
            *flags,
            "--wait",
            "--timeout",
            "6m",
        ]
    )
    image = f"opsproof-web:{tag}"
    run(["docker", "build", "-f", "apps/web/Dockerfile", "-t", image, "apps/web"])
    run(["k3d", "image", "import", image, "-c", "opsproof"])
    run(
        [
            *helm,
            "upgrade",
            "--install",
            "web",
            "infra/helm/opsproof-web",
            "-n",
            "opsproof-ui",
            "--set-string",
            f"image.tag={tag}",
            "--wait",
            "--timeout",
            "5m",
        ]
    )
    identity = run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    record = {
        "crd_url": url,
        "crd_sha256": hashlib.sha256(payload).hexdigest(),
        "traefik_chart": "42.3.0",
        "web_image": image,
        "web_image_id": identity,
        "status": "installed; route and browser verification required",
    }
    (directory / "acceptance/gateway-deployment.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
