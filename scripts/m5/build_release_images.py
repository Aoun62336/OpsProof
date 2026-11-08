"""Build distinct local release artifacts; the faulty image is a labeled drill only."""

import hashlib
import json
import subprocess

from preflight import ROOT


def main():
    base = "opsproof-demo:m5-d35fd6fc29e0"
    identity = subprocess.check_output(
        ["docker", "image", "inspect", base, "--format", "{{.Id}}"], text=True
    ).strip()
    directory = ROOT / ".runtime/m5/release-images"
    directory.mkdir(parents=True, exist_ok=True)
    source = (ROOT / "apps/demo-workload/src/opsproof_demo/api.py").read_text()
    records = [{"release": "stable", "image": base, "image_id": identity}]
    for release in ("healthy", "faulty"):
        code = source.replace('version="0.1.0"', 'version="0.1.1-m5"')
        if release == "faulty":
            code = code.replace(
                "def stats() -> JobCounts:\n",
                'def stats() -> JobCounts:\n    raise HTTPException(status_code=500, detail="Intentional M5 bad-release drill")\n',
            )
        digest = hashlib.sha256(code.encode()).hexdigest()
        image = "opsproof-demo:m5-" + release + "-" + digest[:12]
        (directory / "api.py").write_text(code)
        (directory / "Dockerfile").write_text(
            f"FROM {base}\nUSER 0\nCOPY api.py /tmp/m5-api.py\n"
            "RUN python -c \"import importlib.util,pathlib; p=pathlib.Path(importlib.util.find_spec('opsproof_demo.api').origin); p.write_bytes(pathlib.Path('/tmp/m5-api.py').read_bytes())\"\n"
            f'LABEL opsproof.io.release="{release}" opsproof.io.source-sha256="{digest}"\nUSER 10001:10001\n'
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
    (ROOT / ".runtime/m5/acceptance/release-images.json").write_text(
        json.dumps(records, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
