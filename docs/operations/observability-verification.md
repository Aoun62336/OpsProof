# OpsProof Observability Verification

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
