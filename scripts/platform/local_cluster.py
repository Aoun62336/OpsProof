"""Fail closed before cluster access: isolated kubeconfig and loopback API only."""

import json
import subprocess
from urllib.parse import urlparse

from preflight import ROOT

KUBECONFIG = ROOT / ".runtime/m5/kubeconfig.yaml"


def validate_server(server):
    parsed = urlparse(server)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 6550
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Only the local https://127.0.0.1:6550 API is authorized")


def kubectl_prefix():
    if not KUBECONFIG.is_file():
        raise RuntimeError("Run bootstrap.py first; isolated M5 kubeconfig missing")
    args = ["kubectl", "--kubeconfig", str(KUBECONFIG), "--context", "k3d-opsproof"]
    result = subprocess.run(
        [*args, "config", "view", "--minify", "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    config = json.loads(result.stdout)
    validate_server(config["clusters"][0]["cluster"]["server"])
    return args


def helm_prefix():
    kubectl_prefix()
    return ["helm", "--kubeconfig", str(KUBECONFIG), "--kube-context", "k3d-opsproof"]
