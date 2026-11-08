"""Fixed in-cluster endpoint, TLS verification, projected short-lived credentials."""

import ssl
from pathlib import Path

import httpx2 as httpx

from .kubernetes_policy import TARGET_PATH

TOKEN = Path("/var/run/secrets/opsproof-kubernetes/token")
CA = "/var/run/secrets/opsproof-kubernetes/ca.crt"


def request(method="GET", patch=None, *, check_scaler=False):
    if method not in ("GET", "PATCH") or (method == "PATCH" and patch is None):
        raise ValueError("Unsupported Kubernetes operation")
    if check_scaler and method != "GET":
        raise ValueError("Scaler inspection is read-only")
    token = TOKEN.read_text().strip()
    if not token:
        raise ValueError("Kubernetes credential unavailable")
    headers = {"Authorization": "Bearer " + token}
    if method == "PATCH":
        headers["Content-Type"] = "application/json-patch+json"
    with httpx.Client(
        base_url="https://kubernetes.default.svc",
        verify=ssl.create_default_context(cafile=CA),
        timeout=5,
        trust_env=False,
        follow_redirects=False,
    ) as client:
        path = (
            "/apis/keda.sh/v1alpha1/namespaces/opsproof-demo/scaledobjects/demo-worker-lag"
            if check_scaler
            else TARGET_PATH
        )
        response = client.request(method, path, headers=headers, json=patch)
        if check_scaler and response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
