# Monitoring and alerting

## Metrics and alerts

Prometheus scrapes APIs and monitoring components every ten seconds. Kubernetes
uses per-Pod headless metrics Services with `publishNotReadyAddresses`; missing
and failed API targets both alert. The ordinary application Service still routes
only to Ready Pods. Shared PostgreSQL counts/ages use `max`, never a sum across
observers. Failed database probes publish unknown values and retain the previous
successful observation timestamp. Counts are jobs/experiments, ages are seconds,
and freshness/completion timestamps are Unix seconds.

The initial experimental objectives are: oldest queued work >45 seconds; no
completion alongside processing older than 60 seconds (demo) or 300 seconds
(control); HTTP errors >1% with >=100 application requests in five minutes; and
p95 >1 second with a traffic floor. These are explicit demonstration objectives,
not a measured production SLO. Health/metrics requests are excluded from HTTP
quality objectives. Rules separately cover dependencies, partial replicas,
backend availability, notification failures, Collector rejection and queue pressure.

The Collector has a dedicated bounded persistent queue volume, 256 requests per
exporter, 120-second retry budget and memory limiter. Persistence covers queued
exports, not the preceding in-memory batch or unlimited backend outages. All six
services have bounded storage/resources, nonroot users and read-only roots.
Kubernetes has startup/liveness/readiness probes and 60-second termination grace.
Only Prometheus receives a projected, expiring node-metrics identity. Direct
kubelet TLS verification stays enabled; `nodes/proxy` is not granted.

Grafana provisions actual CPU/memory, PVC free space, freshness, progress and
telemetry-health panels. Reservations are not measured utilization. Loki trace-ID
metadata links to Tempo; traces link back to logs. W3C trace context is carried
through both durable outboxes and Redis streams, preserving legacy messages.
Trace/span and job/run identifiers appear in logs; baggage and credentials are
not propagated.

For Compose, prepare existing credentials and the exact named volume roots once:

```sh
python -m scripts.compose.prepare_observability --storage
```

This never recursively changes existing data. Compose disables volume copy-up
so vendor directory ownership cannot override these explicit service UIDs.
Grafana is built from `observability/grafana/Dockerfile`; the other five images
are pinned in `observability/images.lock.json`. Cloud uses the secured Grafana
digest from the approved five-artifact release manifest, never its source image.

Run the independent foreground owner watch during the deployment session with
explicit loopback Prometheus/Alertmanager forwards. It needs no OpsProof API:

```sh
python -m scripts.platform.watch_observability --watch --duration 300
```

This is an attended session safeguard, not independent 24/7 paging. Unknown or
stale evidence and unavailable monitoring endpoints return failure. No external
notification provider or paid service is configured.

Exact pinned binaries, behavioral alert tests and rendered profiles are checked
by `scripts.platform.validate_observability`. The disposable
`scripts.platform.verify_observability_runtime` requires exact built image IDs,
uses only owned fixtures/volumes and tests the actual export/query/webhook path.
The security workflow retains comprehensive raw inventories, SBOMs and policy
outcomes. It rejects unsupported OS feeds instead of treating missing coverage
as a clean scan. The exact official scratch Collector has no OS packages;
its complete Go binary inventory is required instead.
