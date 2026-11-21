"""Deploy the existing M4 telemetry components into the local cluster.

Uses existing local image digests, retained PVCs, and out-of-band credentials.
"""

import json
import subprocess

from scripts.platform.import_local_image import import_image
from scripts.platform.local_cluster import kubectl_prefix
from scripts.platform.observability import inputs, render
from scripts.platform.preflight import ROOT
from scripts.platform.render_local_secrets import read_env
from scripts.platform.telemetry_images import local_grafana_image
from scripts.reliability.build_images_local import context_hash

NS = "opsproof-observability"


def main():
    kube = kubectl_prefix()
    env = read_env(ROOT / ".env")
    _configurations, services = inputs()
    images = []
    identities = {}
    for name, image, *_rest in services:
        if name == "grafana":
            record = json.loads(
                (ROOT / ".runtime/reliability/acceptance/image-provenance.json").read_text()
            )["grafana"]
            actual = subprocess.check_output(
                ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
            ).strip()
            if (
                image != local_grafana_image()
                or record["tag"] != image
                or record["source_content_sha256"] != context_hash(ROOT / "observability/grafana")
                or record["local_image_id"] != actual
            ):
                raise RuntimeError("Build the current secured Grafana artifact before deployment")
            identities[name] = image
            imported = import_image(image, actual, "opsproof")
            images.append({"service": name, **imported})
            continue
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
    (ROOT / ".runtime/platform/acceptance/telemetry-images.json").write_text(
        json.dumps(images, indent=2) + "\n"
    )
    print("Telemetry deployed; real metrics/log/trace verification still required")


if __name__ == "__main__":
    main()
