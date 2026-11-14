"""Build source-identified local images and measure size/time. Never pushes.

Existing M5 images and evidence remain intact. New tags include a source content
hash; local image IDs are recorded separately from registry manifest digests.
"""

import hashlib
import json
import os
import subprocess
import time
from uuid import uuid4

from scripts.m5.preflight import GIB, ROOT, memory_available
from scripts.m6.local_environment import source_identity, utc, write_json

APPS = {"demo": "demo-workload", "control": "control-plane", "web": "web"}


def context_hash(directory):
    files = []
    for name in (
        "Dockerfile",
        ".dockerignore",
        "pyproject.toml",
        "uv.lock",
        "package.json",
        "package-lock.json",
        "nginx.conf",
        "index.html",
        "alembic.ini",
        "tsconfig.json",
        "tsconfig.app.json",
        "tsconfig.node.json",
        "vite.config.ts",
    ):
        path = directory / name
        if path.is_file():
            files.append(path)
    for name in ("src", "alembic", "public"):
        files.extend(
            path
            for path in (directory / name).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
    hashes = {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(files)
    }
    return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def main():
    if memory_available() < 2 * GIB:
        raise RuntimeError("Local image build requires 2 GiB free host RAM")
    output = ROOT / ".runtime/m6/builds" / ("build-" + uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    source = source_identity()
    write_json(output / "source.json", source)
    records = {}
    started = time.monotonic()
    for component, folder in APPS.items():
        directory = ROOT / "apps" / folder
        identity = context_hash(directory)
        tag = "opsproof-" + component + ":m6-" + identity[:16]
        command = [
            "docker",
            "build",
            "--progress",
            "plain",
            "--label",
            "org.opencontainers.image.revision=" + source["head"],
            "--label",
            "opsproof.io/source-content-sha256=" + identity,
            "-t",
            tag,
            str(directory),
        ]
        then = time.monotonic()
        with (output / f"{component}.log").open("x", encoding="utf-8") as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                while process.poll() is None:
                    if memory_available() < GIB:
                        raise RuntimeError("Image build aborted below 1 GiB free RAM")
                    if time.monotonic() - then > 900:
                        raise TimeoutError("Image build deadline exceeded")
                    time.sleep(1)
            except BaseException:
                process.terminate()
                process.wait(timeout=15)
                raise
        if process.returncode:
            raise RuntimeError("Image build failed; inspect " + component + ".log")
        if context_hash(directory) != identity:
            raise RuntimeError(
                "Application source changed during image build; do not deploy this tag"
            )
        info = json.loads(
            subprocess.check_output(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    "{{json .}}",
                    tag,
                ],
                text=True,
                timeout=15,
            )
        )
        records[component] = {
            "tag": tag,
            "local_image_id": info["Id"],
            "size_bytes": info["Size"],
            "build_seconds": round(time.monotonic() - then, 3),
            "source_content_sha256": identity,
            "head": source["head"],
            "source_dirty": source["dirty"],
            "built_at": utc(),
            "registry_manifest_digests": info.get("RepoDigests", []),
        }
        write_json(output / f"{component}.json", records[component])
        print(component, tag, records[component]["local_image_id"], flush=True)
    report = {
        **records,
        "total_seconds": round(time.monotonic() - started, 3),
        "published": False,
        "limitation": "Build timing includes local cache state; no optimization gain inferred",
    }
    write_json(output / "result.json", report)
    pointer = ROOT / ".runtime/m6/acceptance/image-provenance.json"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
