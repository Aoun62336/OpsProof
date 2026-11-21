"""Bounded operator-side monitoring through explicit loopback port-forwards.

No cluster startup, remote notification, credentials or configuration mutation.
Keep this foreground watch running during the temporary deployment window.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener

EXPECTED = frozenset(
    (
        "opsproof-demo-api",
        "opsproof-control-api",
        "prometheus",
        "alertmanager",
        "otel-collector",
        "loki",
        "tempo",
        "grafana",
    )
)


def loopback(value):
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not parsed.port
    ):
        raise argparse.ArgumentTypeError("An explicit credential-free loopback URL is required")
    return value.rstrip("/")


def fetch(url):
    opener = build_opener(ProxyHandler({}))
    with opener.open(url, timeout=3) as response:
        if response.status != 200:
            raise RuntimeError("Health endpoint rejected request")
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise RuntimeError("Monitoring response exceeded bound")
        return data


def inspect(prometheus, alertmanager, *, getter=fetch, now=None):
    now = time.time() if now is None else now
    failures = []
    for name, url in (("prometheus", prometheus), ("alertmanager", alertmanager)):
        try:
            getter(url + "/-/ready")
        except Exception:
            failures.append(name + " unavailable; inspect its port-forward and service")
    try:
        data = json.loads(getter(prometheus + "/api/v1/targets"))
        if data.get("status") != "success":
            raise ValueError("Unsuccessful target response")
        targets = data["data"]["activeTargets"]
        for job in sorted(EXPECTED):
            rows = [r for r in targets if r.get("labels", {}).get("job") == job]
            healthy = False
            for row in rows:
                sampled = datetime.fromisoformat(row["lastScrape"].replace("Z", "+00:00"))
                healthy |= row.get("health") == "up" and 0 <= now - sampled.timestamp() <= 30
            if not healthy:
                failures.append(job + " has no fresh healthy target")
    except Exception:
        failures.append("Prometheus target evidence unavailable")
    try:
        alerts = json.loads(getter(alertmanager + "/api/v2/alerts"))
        critical = sorted(
            {
                a.get("labels", {}).get("alertname", "unknown")
                for a in alerts
                if a.get("labels", {}).get("severity") == "critical"
                and a.get("status", {}).get("state") == "active"
            }
        )
        failures.extend("critical alert: " + name for name in critical)
    except Exception:
        failures.append("Alertmanager active-alert evidence unavailable")
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "healthy": not failures,
        "failures": failures,
        "scope": "Foreground operator watch; not independent 24/7 paging",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus", type=loopback, default="http://127.0.0.1:19090")
    parser.add_argument("--alertmanager", type=loopback, default="http://127.0.0.1:19093")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--duration", type=int, default=300)
    args = parser.parse_args()
    if not 1 <= args.duration <= 3600:
        parser.error("Watch duration must be 1..3600 seconds")
    deadline = time.monotonic() + args.duration
    ever_failed = False
    try:
        while True:
            report = inspect(args.prometheus, args.alertmanager)
            ever_failed |= not report["healthy"]
            print(json.dumps(report), flush=True)
            if not args.watch or time.monotonic() >= deadline:
                return int(ever_failed)
            time.sleep(min(5, max(0, deadline - time.monotonic())))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
