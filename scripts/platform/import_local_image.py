"""Import an exact local artifact into an explicitly owned k3d node and verify CRI visibility.

Platform-specific native Docker export avoids incomplete multi-platform exports
in k3d's Docker Desktop importer. A successful CLI exit alone is insufficient.
"""

import hashlib
import json
import re
import subprocess
import tempfile


def configuration_digest(platform, manifest):
    descriptor = platform.get("Descriptor", {})
    if descriptor.get("mediaType") not in {
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    }:
        raise ValueError("An exact platform manifest is required")
    if "sha256:" + hashlib.sha256(manifest).hexdigest() != descriptor.get("digest"):
        raise ValueError("Runtime content differs from the approved platform manifest")
    digest = json.loads(manifest)["config"]["digest"]
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Invalid image configuration digest")
    return digest


def import_image(image, expected_id, cluster):
    if not re.fullmatch(r"opsproof(?:-monitoring-[0-9a-f]{10})?", cluster):
        raise ValueError("Only the project cluster or an owned monitoring fixture is allowed")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected_id):
        raise ValueError("An exact local Docker image identity is required")
    node = "k3d-" + cluster + "-server-0"
    info = json.loads(subprocess.check_output(["docker", "inspect", node], text=True, timeout=15))[
        0
    ]
    if info.get("Config", {}).get("Labels", {}).get("k3d.cluster") != cluster:
        raise ValueError("Node ownership could not be established")
    artifact = json.loads(
        subprocess.check_output(["docker", "image", "inspect", image], text=True, timeout=15)
    )[0]
    if (
        artifact["Id"] != expected_id
        or artifact["Os"] != "linux"
        or artifact["Architecture"] != "amd64"
    ):
        raise ValueError("Local image differs from the approved linux/amd64 artifact")
    platform = json.loads(
        subprocess.check_output(
            ["docker", "image", "inspect", "--platform", "linux/amd64", expected_id],
            text=True,
            timeout=15,
        )
    )[0]
    with tempfile.TemporaryFile() as errors:
        producer = subprocess.Popen(
            ["docker", "image", "save", "--platform", "linux/amd64", image],
            stdout=subprocess.PIPE,
            stderr=errors,
        )
        try:
            imported = subprocess.run(
                [
                    "docker",
                    "exec",
                    "-i",
                    node,
                    "ctr",
                    "--namespace",
                    "k8s.io",
                    "images",
                    "import",
                    "--local",
                    "--platform",
                    "linux/amd64",
                    "--digests",
                    "-",
                ],
                stdin=producer.stdout,
                capture_output=True,
                timeout=180,
                check=False,
            )
            producer.stdout.close()
            exported = producer.wait(timeout=15)
            if imported.returncode or exported:
                errors.seek(0)
                detail = errors.read(2000).decode(errors="replace")
                detail += imported.stderr[:2000].decode(errors="replace")
                raise RuntimeError("Native platform-specific image import failed: " + detail)
        finally:
            if producer.stdout and not producer.stdout.closed:
                producer.stdout.close()
            if producer.poll() is None:
                producer.kill()
                producer.wait(timeout=10)
    metadata = json.loads(
        subprocess.check_output(
            ["docker", "exec", node, "crictl", "inspecti", image], text=True, timeout=30
        )
    )
    descriptor = platform.get("Descriptor")
    if descriptor:
        manifest = subprocess.check_output(
            [
                "docker",
                "exec",
                node,
                "ctr",
                "--namespace",
                "k8s.io",
                "content",
                "get",
                descriptor["digest"],
            ],
            timeout=30,
        )
        config_id = configuration_digest(platform, manifest)
    else:
        # Classic Docker stores use the configuration digest as Id. Modern
        # containerd-backed Docker exposes an OCI index or manifest as Id.
        config_id = platform["Id"]
    if metadata.get("status", {}).get("id") != config_id:
        raise RuntimeError(
            "Imported image is not visible to CRI with the expected configuration digest"
        )
    return {
        "image": image,
        "image_id": expected_id,
        "runtime_config_id": config_id,
        "cri_verified": True,
    }
