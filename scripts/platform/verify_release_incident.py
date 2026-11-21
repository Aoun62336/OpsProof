"""Correlate a real failed release request, stored incident lifecycle and trace."""

import base64
import json
import time
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import urlopen

from scripts.platform.forward import services
from scripts.platform.preflight import ROOT
from scripts.platform.render_local_secrets import read_env
from scripts.platform.verify_k3d import http


def main():
    key = read_env(ROOT / ".env")["OPSPROOF_CONTROL_API_KEY"]
    output = ROOT / ".runtime/platform/acceptance"
    deadline = time.monotonic() + 360
    with services([("opsproof-observability", "tempo", 13200, 3200)]):
        while time.monotonic() < deadline:
            status, incidents = http("http://127.0.0.1:8081", "GET", "/api/v1/incidents", key)
            incident = (
                next(
                    (i for i in incidents if i["name"] == "OpsProofDemoCanaryErrors"),
                    None,
                )
                if status == 200
                else None
            )
            if incident:
                code, events = http(
                    "http://127.0.0.1:8081",
                    "GET",
                    "/api/v1/incidents/" + incident["fingerprint"] + "/events",
                    key,
                )
                trial = json.loads((output / "faulty-rollout.json").read_text())
                trial_start = min(r["time"] for r in trial["requests"])
                current_events = (
                    [
                        e
                        for e in events
                        if datetime.fromisoformat(e["created_at"]).timestamp() >= trial_start
                    ]
                    if code == 200
                    else []
                )
                if incident["status"] == "resolved" and {"firing", "resolved"} <= {
                    e["status"] for e in current_events
                }:
                    traces = [
                        r["trace_id"]
                        for r in trial["requests"]
                        if r["status"] == 500 and r.get("trace_id")
                    ]
                    for trace_id in traces:
                        try:
                            with urlopen(
                                "http://127.0.0.1:13200/api/traces/" + trace_id,
                                timeout=5,
                            ) as response:
                                trace = json.load(response)
                        except HTTPError:
                            continue
                        spans = [
                            span
                            for batch in trace.get("batches", trace.get("resourceSpans", []))
                            for scope in batch.get("scopeSpans", [])
                            for span in scope.get("spans", [])
                        ]
                        identities = {
                            trace_id,
                            base64.b64encode(bytes.fromhex(trace_id)).decode(),
                        }
                        matched = [span for span in spans if span.get("traceId") in identities]
                        if matched and trial["passed"]:
                            result = {
                                "passed": True,
                                "incident": incident,
                                "incident_events": current_events,
                                "failed_request_trace_id": trace_id,
                                "trace_span_count": len(matched),
                                "request_status": 500,
                                "rollout_aborted": trial["after"]["status"].get("abort"),
                                "final_stable_images": trial["stable_images"],
                            }
                            (output / "release-incident-trace.json").write_text(
                                json.dumps(result, indent=2)
                            )
                            print(
                                "PASS: failed request trace and stored firing/resolved canary "
                                "incident"
                            )
                            return
            time.sleep(5)
    raise RuntimeError(
        "Release incident lifecycle and matching failed-request trace not established"
    )


if __name__ == "__main__":
    main()
