"""Real local gateway auth/routing checks; never writes cookies or credentials."""

import json
import subprocess
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from local_cluster import kubectl_prefix
from preflight import ROOT
from render_local_secrets import read_env

BASE = "http://127.0.0.1:8081"


def main():
    kube = kubectl_prefix()
    checks = []
    for kind, namespace, name, required in (
        ("gateway", "opsproof-gateway", "opsproof-gateway", {"Accepted", "Programmed"}),
        ("httproute", "opsproof-ui", "opsproof-web", {"Accepted", "ResolvedRefs"}),
    ):
        output = subprocess.check_output(
            [*kube, "get", kind, name, "-n", namespace, "-o", "json"], text=True
        )
        obj = json.loads(output)
        generation = obj["metadata"]["generation"]
        conditions = obj["status"].get("conditions", [])
        if kind == "httproute":
            conditions = obj["status"]["parents"][0]["conditions"]
        valid = {
            c["type"]
            for c in conditions
            if c["status"] == "True" and c.get("observedGeneration") == generation
        }
        if not required.issubset(valid):
            raise RuntimeError(f"{kind} current-generation conditions not ready")
        checks.append(
            {"check": kind, "conditions": sorted(valid), "generation": generation}
        )

    jar = CookieJar()
    client = build_opener(HTTPCookieProcessor(jar))

    def request(label, path, expected, payload=None, headers=None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = Request(
            BASE + path,
            data=data,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            response = client.open(req, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            body = response.read()
            code = response.code
            content_type = response.headers.get("Content-Type", "")
        checks.append({"check": label, "status": code, "content_type": content_type})
        if code != expected:
            raise RuntimeError(f"{label}: expected HTTP {expected}, received {code}")
        return json.loads(body) if "application/json" in content_type else body

    page = request("frontend", "/", 200)
    if not isinstance(page, bytes) or b'<div id="root">' not in page:
        raise RuntimeError("Frontend HTML root missing")
    request("anonymous session denied", "/api/v1/auth/session", 401)
    request("anonymous capabilities denied", "/api/v1/capabilities", 401)
    request("demo actuator not routed", "/api/v1/internal/worker/resume", 404, {})
    key = read_env(ROOT / ".env")["OPSPROOF_CONTROL_API_KEY"]
    login = request("login", "/api/v1/auth/login", 200, {"access_key": key})
    cookie = next(cookie.value for cookie in jar if cookie.name == "opsproof_session")
    request("authenticated session", "/api/v1/auth/session", 200)
    request("missing CSRF denied", "/api/v1/auth/logout", 403, {})
    request(
        "wrong CSRF denied",
        "/api/v1/auth/logout",
        403,
        {},
        {"X-OpsProof-CSRF": "invalid"},
    )
    request(
        "logout",
        "/api/v1/auth/logout",
        200,
        {},
        {"X-OpsProof-CSRF": login["csrf_token"]},
    )
    request(
        "revoked session replay denied",
        "/api/v1/auth/session",
        401,
        headers={"Cookie": "opsproof_session=" + cookie},
    )
    record = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": BASE,
        "checks": checks,
        "passed": True,
    }
    (ROOT / ".runtime/m5/acceptance/gateway-http.json").write_text(
        json.dumps(record, indent=2) + "\n"
    )
    print(f"PASS: {len(checks)} real gateway checks")


if __name__ == "__main__":
    main()
