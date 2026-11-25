"""Generate disposable Redis TLS/Auth Secrets for the isolated cloud namespaces.

Use only within an ignored private runtime directory. Requires OpenSSL on PATH.
Never commit output. Generates separate ephemeral CAs and server certificates
with service-DNS SAN. No passwords or private keys are printed to stdout.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote


def cmd(*args: str) -> None:
    subprocess.run(
        ["openssl", *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=30,
    )


def k8s_secret(namespace: str, name: str, data: dict[str, str]) -> dict:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "type": "Opaque",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": {
                "opsproof.io/environment": "temporary-verification",
                "opsproof.io/ephemeral": "true",
            },
        },
        "data": {k: base64.b64encode(v.encode()).decode() for k, v in data.items()},
    }


def build_for(role: str) -> list[dict]:
    if role not in ("demo", "control"):
        raise ValueError("only demo/control")
    ns = f"opsproof-{role}"
    host = f"{role}-deps-redis.{ns}.svc.cluster.local"
    password = secrets.token_urlsafe(36)
    with tempfile.TemporaryDirectory(prefix="opsproof-cloud-cert-") as tmp:
        d = Path(tmp)
        # CA key is ephemeral and never published. Server key only in the private K8s Secret.
        cmd(
            "req",
            "-new",
            "-x509",
            "-newkey",
            "rsa:3072",
            "-nodes",
            "-days",
            "2",
            "-subj",
            f"/CN=OpsProof-Cloud-{role}-Ephemeral-CA",
            "-addext",
            "basicConstraints=critical,CA:TRUE,pathlen:0",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
            "-addext",
            "subjectKeyIdentifier=hash",
            "-keyout",
            str(d / "ca.key"),
            "-out",
            str(d / "ca.crt"),
            "-sha256",
        )
        cmd(
            "req",
            "-new",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(d / "tls.key"),
            "-subj",
            f"/CN={host}",
            "-out",
            str(d / "tls.csr"),
        )
        (d / "extensions.txt").write_text(
            (
                f"subjectAltName=DNS:{host}\nextendedKeyUsage=serverAuth\n"
                "basicConstraints=critical,CA:FALSE\n"
                "keyUsage=critical,digitalSignature,keyEncipherment\n"
                "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n"
            ),
            encoding="utf-8",
        )
        cmd(
            "x509",
            "-req",
            "-days",
            "2",
            "-sha256",
            "-in",
            str(d / "tls.csr"),
            "-CA",
            str(d / "ca.crt"),
            "-CAkey",
            str(d / "ca.key"),
            "-CAcreateserial",
            "-extfile",
            str(d / "extensions.txt"),
            "-out",
            str(d / "tls.crt"),
        )
        ca = (d / "ca.crt").read_text(encoding="utf-8")
        cert = (d / "tls.crt").read_text(encoding="utf-8")
        key = (d / "tls.key").read_text(encoding="utf-8")
    endpoint = f"rediss://:{quote(password, safe='')}@{host}:6379/0"
    url = (
        endpoint + "?ssl_cert_reqs=required&ssl_check_hostname=true"
        "&ssl_ca_certs=/etc/opsproof/redis-ca/ca.crt"
    )
    env_key = "OPSPROOF_REDIS_URL" if role == "demo" else "OPSPROOF_CONTROL_REDIS_URL"
    return [
        k8s_secret(ns, "opsproof-redis-tls", {"tls.crt": cert, "tls.key": key, "ca.crt": ca}),
        k8s_secret(ns, "opsproof-redis-auth", {"password": password, "tls": "enable", "ca": ca}),
        k8s_secret(ns, f"opsproof-{role}-redis-connection", {env_key: url}),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Refuse writing directly to repository files: opt-in ignored runtime path only.
    if not args.output.resolve().is_relative_to(
        (Path(__file__).resolve().parents[2] / ".runtime/cloud/private").resolve()
    ):
        parser.error("Output must be inside a private .runtime directory")
    if args.output.exists():
        parser.error("Refusing to overwrite existing Redis credentials")
    docs = build_for("demo") + build_for("control")
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"apiVersion": "v1", "kind": "List", "items": docs}, f, indent=2)
        f.write("\n")
    print("GENERATED_PRIVATE_REDIS_SECRETS: 6 objects; do not commit or share")


if __name__ == "__main__":
    main()
