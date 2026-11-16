"""Deploy the existing M4 telemetry components into the local cluster.

Uses existing local image digests, retained PVCs, and out-of-band credentials.
"""

import json
import subprocess

from local_cluster import kubectl_prefix
from preflight import ROOT
from render_local_secrets import read_env

from observability import inputs, render

NS = "opsproof-observability"


def main():
    kube = kubectl_prefix()
    env = read_env(ROOT / ".env")
    _configurations, services = inputs()
    images = []
    identities = {}
    for name, image, *_rest in services:
        if "@sha256:" not in image:
            digests = json.loads(
                subprocess.check_output(
                    ["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
                    text=True,
                )
            )
            if not digests:
                raise RuntimeError("Local telemetry image has no registry digest: " + name)
            image = digests[0]
        identities[name] = image
        images.append({"service": name, "image": image})
    rendered = render(identities)
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "opsproof-telemetry-auth", "namespace": NS},
        "stringData": {
            "webhook-token": env["OPSPROOF_CONTROL_ALERT_WEBHOOK_TOKEN"],
            "grafana-password": env["OPSPROOF_GRAFANA_ADMIN_PASSWORD"],
        },
    }
    subprocess.run(
        [*kube, "apply", "-f", "-"],
        input=json.dumps(secret),
        text=True,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [*kube, "apply", "-f", "-"],
        input=json.dumps(rendered),
        text=True,
        check=True,
    )
    for service in images:
        subprocess.run(
            [
                *kube,
                "rollout",
                "status",
                "deployment/" + service["service"],
                "-n",
                NS,
                "--timeout=300s",
            ],
            check=True,
        )
    (ROOT / ".runtime/m5/acceptance/telemetry-images.json").write_text(
        json.dumps(images, indent=2) + "\n"
    )
    print("Telemetry deployed; real metrics/log/trace verification still required")


if __name__ == "__main__":
    main()
