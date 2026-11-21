"""Checksum-pinned native security tools, independent of app/YAML dependencies."""

import hashlib
import os
import tarfile
import zipfile
from urllib.request import urlopen

from scripts.paths import tools

ASSETS = {
    "gitleaks": {
        "windows": (
            "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_windows_x64.zip",
            "d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e",
        ),
        "linux": (
            "https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz",
            "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
        ),
    },
    "kubeconform": {
        "windows": (
            "https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-windows-amd64.zip",
            "e3f56102bcf4f50b034a567e2482a1c5330799983ddd655952310211aef73d93",
        ),
        "linux": (
            "https://github.com/yannh/kubeconform/releases/download/v0.8.0/kubeconform-linux-amd64.tar.gz",
            "9bc2bffbf71f261128533edaf912153948b7ff238f9a531ae6d34466ec287883",
        ),
    },
}


def binary(name):
    platform = "windows" if os.name == "nt" else "linux"
    url, digest = ASSETS[name][platform]
    directory = tools("security")
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / url.rsplit("/", 1)[1]
    if not archive.exists():
        with urlopen(url, timeout=90) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Tool checksum mismatch: " + name)
    filename = name + (".exe" if os.name == "nt" else "")
    if os.name == "nt":
        with zipfile.ZipFile(archive) as package:
            data = package.read(filename)
    else:
        with tarfile.open(archive) as package:
            data = package.extractfile(filename).read()
    target = directory / filename
    target.write_bytes(data)
    target.chmod(0o755)
    return str(target)
