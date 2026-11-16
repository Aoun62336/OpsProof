"""Real bounded traffic through the private Gateway, promotion and failed canary."""

import argparse
import json
import subprocess
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from forward import services
from gitops_config import configure
from local_cluster import kubectl_prefix
from preflight import ROOT, memory_available


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--faulty-only", action="store_true")
    args = parser.parse_args()
    kube = kubectl_prefix()
    output = ROOT / ".runtime/m5/acceptance"
    images = {
        row["release"]: row for row in json.loads((output / "release-images.json").read_text())
    }

    def get(kind, name=None):
        return json.loads(
            subprocess.check_output(
                [
                    *kube,
                    "get",
                    kind,
                    *([name] if name else []),
                    "-n",
                    "opsproof-demo",
                    "-o",
                    "json",
                ],
                text=True,
                timeout=15,
            )
        )

    def query(expression):
        with urlopen(
            "http://127.0.0.1:19090/api/v1/query?" + urlencode({"query": expression}),
            timeout=5,
        ) as response:
            return json.load(response)

    stable = get("rollout", "demo-api")
    if stable["status"]["phase"] != "Healthy":
        raise RuntimeError("Healthy initial Rollout required")
    # Initial Rollout has its own distinct selector and is already serving.
    old = subprocess.run(
        [
            *kube,
            "get",
            "deployment",
            "demo-api",
            "-n",
            "opsproof-demo",
            "-o",
            "name",
            "--ignore-not-found",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    if old.stdout.strip():
        subprocess.run(
            [
                *kube,
                "delete",
                "deployment",
                "demo-api",
                "-n",
                "opsproof-demo",
                "--wait=true",
                "--timeout=45s",
            ],
            check=True,
        )

    with services(
        [
            ("opsproof-gateway", "demo-release-gateway", 18081, 8001),
            ("opsproof-observability", "prometheus", 19090, 9090),
        ]
    ):
        stop = threading.Event()
        requests = []

        def traffic():
            while not stop.is_set():
                started = time.monotonic()
                trace_id = uuid4().hex
                try:
                    request = Request(
                        "http://127.0.0.1:18081/api/v1/stats",
                        headers={"traceparent": f"00-{trace_id}-{uuid4().hex[:16]}-01"}
                        if trace_id
                        else {},
                    )
                    with urlopen(request, timeout=3) as response:
                        code = response.status
                        json.load(response)
                except HTTPError as exc:
                    code = exc.code
                except URLError, TimeoutError:
                    code = 0
                requests.append(
                    {
                        "time": time.time(),
                        "trace_id": trace_id,
                        "status": code,
                        "milliseconds": round((time.monotonic() - started) * 1000, 2),
                    }
                )
                stop.wait(max(0, 0.2 - (time.monotonic() - started)))

        thread = threading.Thread(target=traffic)
        thread.start()
        try:
            # Establish real baseline under the same route before candidate analysis.
            time.sleep(20)
            baseline = list(requests)
            if len(baseline) < 50 or any(r["status"] != 200 for r in baseline):
                raise RuntimeError("Healthy traffic baseline not established")
            (output / "rollout-baseline.json").write_text(
                json.dumps(
                    {
                        "requests": baseline,
                        "allowed_error_ratio": 0.01,
                        "rationale": (
                            "Baseline had zero errors; reject candidates exceeding one "
                            "percent errors, with at least 20 measured requests."
                        ),
                    },
                    indent=2,
                )
            )
            for release in ("faulty",) if args.faulty_only else ("healthy", "faulty"):
                begin = len(requests)
                before = get("rollout", "demo-api")
                old_runs = {r["metadata"]["uid"] for r in get("analysisruns")["items"]}
                configure("demo", {"rollout.image": images[release]["image"]}, wait=False)
                samples = []
                deadline = time.monotonic() + 300
                accepted = False
                while time.monotonic() < deadline:
                    if memory_available() < 1024**3:
                        raise RuntimeError("Release trial stopped: host free memory below 1 GiB")
                    rollout = get("rollout", "demo-api")
                    route = get("httproute", "demo-release")
                    runs = [
                        r
                        for r in get("analysisruns")["items"]
                        if r["metadata"]["uid"] not in old_runs
                    ]
                    samples.append(
                        {
                            "time": time.time(),
                            "phase": rollout.get("status", {}).get("phase"),
                            "abort": rollout.get("status", {}).get("abort", False),
                            "weights": route["spec"]["rules"][0]["backendRefs"],
                            "analysis": [
                                {
                                    "name": r["metadata"]["name"],
                                    "status": r.get("status", {}),
                                }
                                for r in runs
                            ],
                        }
                    )
                    candidate_live = (
                        rollout["spec"]["template"]["spec"]["containers"][0]["image"]
                        == images[release]["image"]
                    )
                    phases = [r.get("status", {}).get("phase") for r in runs]
                    if (
                        candidate_live
                        and release == "healthy"
                        and rollout["status"].get("phase") == "Healthy"
                        and "Successful" in phases
                    ):
                        accepted = True
                        break
                    if (
                        candidate_live
                        and release == "faulty"
                        and rollout["status"].get("abort")
                        and "Failed" in phases
                    ):
                        accepted = True
                        break
                    time.sleep(5)
                record = {
                    "release": release,
                    "passed": False,
                    "images": images,
                    "before": before,
                    "after": rollout,
                    "samples": samples,
                    "requests": requests[begin:],
                    "analysisruns": runs,
                    "metrics": query(
                        'sum(increase(opsproof_http_requests_total{job="opsproof-demo'
                        '-canary",route="/api/v1/stats",status!~"2.."}[1m]))'
                    ),
                }
                if accepted and release == "faulty":
                    # Observe the abort return actual traffic to the last promoted image.
                    time.sleep(20)
                    check_start = len(requests)
                    time.sleep(10)
                    route = get("httproute", "demo-release")
                    record["restored_route"] = route
                    record["restored_requests"] = requests[check_start:]
                    weights = {
                        b["name"]: b["weight"] for b in route["spec"]["rules"][0]["backendRefs"]
                    }
                    accepted = (
                        weights == {"demo-api": 100, "demo-api-canary": 0}
                        and len(record["restored_requests"]) >= 30
                        and all(r["status"] == 200 for r in record["restored_requests"])
                        and any(r["status"] == 500 for r in record["requests"])
                    )
                    pods = get("pods")["items"]
                    stable_hash = rollout["status"]["stableRS"]
                    stable_pods = [
                        p
                        for p in pods
                        if p["metadata"]["labels"].get("rollouts-pod-template-hash") == stable_hash
                    ]
                    record["stable_images"] = [
                        c["image"] for p in stable_pods for c in p["spec"]["containers"]
                    ]
                    record["stable_image_ids"] = [
                        c.get("imageID")
                        for p in stable_pods
                        for c in p["status"].get("containerStatuses", [])
                    ]
                    accepted = accepted and record["stable_images"] == [images["healthy"]["image"]]
                if release == "healthy":
                    accepted = accepted and not any(r["status"] != 200 for r in record["requests"])
                record["passed"] = accepted
                (output / f"{release}-rollout.json").write_text(json.dumps(record, indent=2))
                if not accepted:
                    raise RuntimeError(release + " release acceptance failed; evidence retained")
                print("PASS:", release, "release", flush=True)
        finally:
            stop.set()
            thread.join(timeout=5)
            configure("demo", {"rollout.image": images["healthy"]["image"]}, wait=False)


if __name__ == "__main__":
    main()
