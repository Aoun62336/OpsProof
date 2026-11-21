# OpsProof Observability Verification

## Maintained operational contracts

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
not propagated. The product UI and palette are separate and unchanged.

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

## Environment

- Platform: Local Docker Compose
- Target: OpsProof demonstration workload
- Control plane: Independent FastAPI/PostgreSQL/Redis services
- Observability: Prometheus, Alertmanager, OpenTelemetry,
  Loki, Tempo, Grafana
- Cloud deployment: Not part of this measurement
- Production traffic: Not used

## Hypothesis

A metrics-driven alerting pipeline should detect a
deliberately introduced service failure and preserve
its lifecycle in the OpsProof incident registry.

This is a hypothesis to verify, not an established result.

## Scenarios

1. Demo API process stopped
2. Demo API restarted
3. Demo worker stopped while jobs are queued
4. Demo worker restarted
5. Invalid alert webhook credential
6. Duplicate alert notification

## Required Timestamps

For each trial, record:

- Fault injection UTC timestamp
- First failed scrape or metric observation
- First firing alert notification received by OpsProof
- Recovery action UTC timestamp
- First successful application readiness check
- Resolved notification received by OpsProof

## Measurement Definitions

Detection delay:

First firing notification received by OpsProof
minus fault injection timestamp.

Observed application restoration delay:

First successful verified readiness check
minus recovery action timestamp.

Alert lifecycle duration:

Resolved notification received
minus first firing notification received.

These measurements answer different questions and
must not be presented as the same metric.

## Trial Requirements

- Use consistent failure scenarios.
- Repeat each comparison with identical thresholds.
- Run at least five valid trials for a preliminary comparison.
- Record failed or inconclusive trials.
- Preserve configuration and relevant container versions.
- Use UTC timestamps.
- Do not discard slow results simply because they are inconvenient.

## Comparison Formula

Percentage reduction:

(Baseline median - New median) / Baseline median * 100

Only calculate this when baseline and new measurements
represent comparable procedures and conditions.

## Evidence

Record:

- Prometheus alert state
- Alertmanager delivery evidence
- OpsProof incident ID/fingerprint
- Incident transition timestamps
- Target health checks
- Experiment records
- Relevant metrics/logs/traces
- Actual test and CI results

## Limitations

- Local simulated traffic is not production traffic.
- Alert resolution is not equivalent to verified application recovery.
- A successful demonstration does not establish production uptime.
- AI diagnosis accuracy is not evaluated in this milestone.
- Results are limited to the tested hardware, environment,
  configurations and scenarios.
