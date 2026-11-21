"""Build distinct local release artifacts; the faulty image is a labeled drill only."""

import hashlib
import json
import re
import subprocess

from scripts.platform.preflight import ROOT
from scripts.reliability.build_images_local import context_hash


def base_image(record):
    """Require the current source build receipt instead of an old local image."""
    digest = context_hash(ROOT / "apps/demo-workload")
    if (
        record.get("source_content_sha256") != digest
        or record.get("tag") != "opsproof-demo:src-" + digest[:16]
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", record.get("local_image_id", ""))
    ):
        raise ValueError("Build the current demo source before preparing release drill images")
    return record["tag"], record["local_image_id"]


def main():
    receipt = ROOT / ".runtime/reliability/acceptance/image-provenance.json"
    base, expected_id = base_image(json.loads(receipt.read_text())["demo"])
    identity = subprocess.check_output(
        ["docker", "image", "inspect", base, "--format", "{{.Id}}"], text=True
    ).strip()
    if identity != expected_id:
        raise ValueError("Local base image identity differs from its build receipt")
    directory = ROOT / ".runtime/platform/release-images"
    directory.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "apps/demo-workload/src/opsproof_demo/api.py").read_text()
    records = [{"release": "stable", "image": base, "image_id": identity}]
    for release in ("healthy", "faulty"):
        code = source.replace('version="0.1.0"', 'version="0.1.1-drill"')
        if code == source:
            raise ValueError("Release drill patch no longer matches the application")
        if release == "faulty":
            code = code.replace(
                "def stats() -> JobCounts:\n",
                (
                    "def stats() -> JobCounts:\n    raise "
                    'HTTPException(status_code=500, detail="Intentional local '
                    'bad-release drill")\n'
                ),
            )
        digest = hashlib.sha256(code.encode()).hexdigest()
        image = "opsproof-demo:drill-" + release + "-" + digest[:12]
        (directory / "api.py").write_text(code)
        (directory / "Dockerfile").write_text(
            f"FROM {identity}\nUSER 0\nCOPY api.py /tmp/drill-api.py\n"
            + (
                'RUN python -c "import importlib.util,pathlib; '
                "p=pathlib.Path(importlib.util.find_spec('opsproof_demo.api')"
                ".origin); "
                "p.write_bytes(pathlib.Path('/tmp/drill-api.py').read_bytes())\"\n"
            )
            + f'LABEL opsproof.io.release="{release}" '
            f'opsproof.io.source-sha256="{digest}"\nUSER 10001:10001\n'
        )
        subprocess.run(["docker", "build", "-t", image, str(directory)], check=True)
        subprocess.run(["k3d", "image", "import", image, "-c", "opsproof"], check=True)
        image_id = subprocess.check_output(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"], text=True
        ).strip()
        records.append(
            {
                "release": release,
                "image": image,
                "image_id": image_id,
                "api_sha256": digest,
            }
        )
    if len({r["image_id"] for r in records}) != 3:
        raise RuntimeError("Release images must have distinct content identities")
    (ROOT / ".runtime/platform/acceptance/release-images.json").write_text(
        json.dumps(records, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
