"""Inspect only package metadata in a read-only, networkless local image container."""

import json
import subprocess
from uuid import uuid4

from scripts.m5.preflight import ROOT
from scripts.m6.local_environment import write_json

CODE = r"""
import importlib.metadata as metadata
import json, sys
from pathlib import Path
def packages(path=None):
    return sorted([{"name": d.metadata["Name"], "version": d.version}
                   for d in metadata.distributions(**({"path": path} if path else {}))],
                  key=lambda d:d["name"])
global_site = "/usr/local/lib/python3.14/site-packages"
vendor = Path(global_site) / "pip/_vendor/vendor.txt"
print(json.dumps({"python": sys.version, "executable": sys.executable,
                  "application_packages": packages(), "global_packages": packages([global_site]),
                  "pip_vendor_manifest": vendor.read_text() if vendor.exists() else None}))
"""


def main():
    images = json.loads((ROOT / ".runtime/m6/acceptance/image-provenance.json").read_text())
    output = ROOT / ".runtime/m6/acceptance/images" / ("inventory-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    for component in ("demo", "control"):
        image = images[component]
        run = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--read-only",
                "--network",
                "none",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "-i",
                "--entrypoint",
                "python",
                image["local_image_id"],
                "-",
            ],
            input=CODE,
            text=True,
            capture_output=True,
            timeout=30,
            check=True,
        )
        result = json.loads(run.stdout)
        result["image_id"] = image["local_image_id"]
        write_json(output / (component + ".json"), result)
        print(component, "global tools:", result["global_packages"])
        if result["pip_vendor_manifest"]:
            print(
                "flagged vendored components:",
                [
                    line
                    for line in result["pip_vendor_manifest"].splitlines()
                    if any(name in line for name in ("msgpack", "setuptools", "urllib3"))
                ],
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
