"""Deploy the foundational services to the verified local cluster, sequentially.

No teardown, Git push, recovery enablement, or controller ownership transition.
"""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime

from local_cluster import helm_prefix, kubectl_prefix
from preflight import ROOT
from render_local_secrets import read_env, render


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def source_tag():
    files = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    digest = hashlib.sha256()
    for name in sorted(set(files)):
        if (
            name
            and (ROOT / name).is_file()
            and name.startswith(("apps/", "infra/", "scripts/"))
        ):
            digest.update(name.encode() + b"\0" + (ROOT / name).read_bytes())
    return "m5-" + digest.hexdigest()[:24]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()
    kube = kubectl_prefix()
    helm = helm_prefix()
    releases = run([*helm, "list", "-A", "-o", "json"], capture_output=True, text=True)
    managed = run(
        [*kube, "get", "deployments", "-A", "-o", "json"],
        capture_output=True,
        text=True,
    )
    for obj in json.loads(managed.stdout)["items"]:
        metadata = obj["metadata"]
        if metadata.get("namespace", "").startswith("opsproof-") and (
            "argocd.argoproj.io/tracking-id" in metadata.get("annotations", {})
            or "argocd.argoproj.io/instance" in metadata.get("labels", {})
        ):
            raise SystemExit(
                "Argo-owned resources detected; refusing Helm ownership conflict"
            )
    secrets = render(read_env(ROOT / args.env))
    run([*kube, "apply", "-f", "infra/k8s/namespaces.yaml"])
    run(
        [*kube, "apply", "-f", "-"],
        input=json.dumps(secrets),
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    tag = source_tag()
    images = []
    for component, directory in (
        ("demo", "demo-workload"),
        ("control", "control-plane"),
    ):
        image = f"opsproof-{component}:{tag}"
        run(
            [
                "docker",
                "build",
                "-f",
                f"apps/{directory}/Dockerfile",
                "-t",
                image,
                f"apps/{directory}",
            ]
        )
        info = run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            capture_output=True,
            text=True,
        )
        images.append({"image": image, "id": info.stdout.strip()})
        run(["k3d", "image", "import", image, "-c", "opsproof"])
    for component in ("demo", "control"):
        run(
            [
                *helm,
                "upgrade",
                "--install",
                f"{component}-deps",
                "infra/helm/opsproof-dependencies",
                "-n",
                f"opsproof-{component}",
                "--wait",
                "--timeout",
                "5m",
            ]
        )
    for component in ("demo", "control"):
        run(
            [
                *helm,
                "upgrade",
                "--install",
                component,
                "infra/helm/opsproof-services",
                "-n",
                f"opsproof-{component}",
                "-f",
                f"infra/helm/opsproof-services/values-{component}.yaml",
                "--set-string",
                f"image.tag={tag}",
                "--wait",
                "--timeout",
                "6m",
            ]
        )
    record = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "source_content_tag": tag,
        "images": images,
        "previous_releases": json.loads(releases.stdout),
        "status": "Helm ready; smoke and security runtime acceptance still required",
    }
    (ROOT / ".runtime/m5/acceptance/deployment.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
