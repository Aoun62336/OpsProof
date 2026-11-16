# OpsProof M6 | Versioned six-scenario experiment protocol

These definitions preserve the canonical frozen v1.0 scope. `scripts/reliability/contracts.py` is the machine-readable companion. **All controlled faults require accepted M5 local Kubernetes, an explicit authorized test window, CPU/RAM headroom, an abort plan and verified cleanup.** No production targets and no public cloud injection.

## Shared preparation and evidence contract

For every trial capture: actual source SHA and dirty-state; deploy image digests; Kubernetes context; component versions; available host memory; test hypothesis; exact target UID and pre-state; start/end UTC; injection artifact; actual observations (metrics, logs, traces, jobs, alerts); independent verification and full cleanup; unexpected behavior; raw artifacts and SHA-256 hashes.

Never rely on the scenario name as diagnosis evidence. A deterministic baseline or LLM must receive independent **observations**, not the known injection cause.

The selected end state must be one of succeeded, failed, aborted or indeterminate with truthful explanation. Natural controller recovery, worker retry and approved OpsProof recovery require separate causal attribution.

## 01 | Worker saturation

- **Hypothesis:** With one worker, a bounded influx of durable jobs raises queue age/backlog; KEDA can increase worker capacity under the same load while maintaining correctness.
- **Allowed mechanism:** Ordinary bounded POSTs to the demo API, via the existing M5 capacity harness and M6 k6 benchmark. No stop/kill or arbitrary target required.
- **Independent sources:** PostgreSQL exact jobs/attempts and timestamps, Redis `XINFO GROUPS` lag/pending and `XPENDING`, actual Deployment ready/desired replicas, Prometheus queue/request metrics and CPU/RAM samples.
- **Controlled configurations:** Fixed worker, HPA API and KEDA worker, identical job count, duration and HTTP background traffic. Do not call HPA versus KEDA a direct apples-to-apples worker-scaler competition.
- **Abort:** Less than 1 GiB free RAM, unresolved previous work, excessive retries/errors, unexpected resource growth or lost target identity.
- **Proof:** Every exact submitted job reaches the recorded expected durable terminal state, no silent loss, actual replicas change where expected, no duplicate durable completion; repeated comparative metrics retain failures.

## 02 | Faulty release

- **Hypothesis:** A distinct bad candidate causes measurable degradation and Argo Rollouts aborts while the stable revision continues to serve.
- **Allowed mechanism:** An **approved Git-owned candidate image revision** installed through the accepted M5 Argo CD/Rollouts/Gateway API configuration. No imperative manual rollback that Argo immediately reverses.
- **Independent sources:** Stable/candidate digests, AnalysisRun decisions, HTTPRoute backend weights/conditions, actual request error/latency metrics, Prometheus scrape timestamps, final service responses and controller events.
- **Abort:** Unexpected unrelated service degradation, missing metric analysis, unbounded traffic, incorrect routing ownership or deployment revision ambiguity.
- **Proof:** Bad candidate failure is observed, analysis abort recorded, routing/ready Pods/stable image health verified. Argo controller rollback must not be credited to a human-approved OpsProof action.

## 03 | Database connectivity

- **Hypothesis:** A reversible test-only DB network disruption produces real connection failures and recovery without data corruption.
- **Allowed mechanism:** Only a pre-reviewed, dedicated temporary network policy or equally narrow isolated fault mechanism. Must account for **additive NetworkPolicy semantics**, CNI enforcement and Argo CD ownership. No deleting volumes or rotating DB credentials.
- **Independent sources:** demo DB probe, readiness, connection errors, application jobs, SQL row counts/job identities before and after, NetworkPolicy event/state and signal timestamps.
- **Abort:** Control-plane database affected, unexpected namespace impact, unknown NetworkPolicy ownership or inability to revoke the fault promptly.
- **Proof:** Target demo DB calls fail during the intended window, recover afterwards, new and existing durable jobs can be read/written, and row integrity remains consistent.

## 04 | Worker failure (not worker pause)

- **Hypothesis:** Actual worker loss while jobs are in-flight results in lease/PEL recovery and complete work without duplicate durable completion.
- **Allowed mechanism:** Controlled single demo worker Pod termination or equivalent approved fault against exact `opsproof-demo` target. Reuse `scripts/platform/verify_consumer_recovery.py` if accepted, rather than introducing duplicate logic.
- **Independent sources:** Job attempts, lease fencing, Redis PEL and `XAUTOCLAIM` evidence, actual Pod UID/restarts, timestamps and completed exact IDs.
- **Abort:** Unexpected unbounded job retries, missing workload baseline, multiple unintended Pods targeted or resource thresholds crossed.
- **Proof:** Real termination, appropriately recovered pending work, correct durable state and at-least-once semantics. Do not claim exactly-once execution.

## 05 | Downstream latency

- **Hypothesis:** A bounded internal downstream HTTP delay causes real request/trace latency, timeout/backoff behavior and safe restoration.
- **Allowed mechanism:** A new test-only, off-by-default FastAPI HTTP dependency controlled by strictly validated delay/error settings and allowlisted service addressing. The real demonstration workload must actually call it when the test profile is enabled. A standalone dummy response that no workload calls is **not** sufficient.
- **Independent sources:** Client and server spans, HTTP request duration distributions, timeout/retry counts, job outcomes, resource use and recovery timestamps.
- **Abort:** Error propagation outside test scope, unbounded retries/backoff, accidental public exposure, timeout > configured ceiling.
- **Proof:** Actual delayed dependency request, correct propagated timeout/retry behavior, bounded recovery and equivalent healthy baseline after disable.

## 06 | Incomplete and misleading evidence

- **Hypothesis:** Missing, stale or contradictory observations must prevent unsupported diagnosis and recovery success claims.
- **Allowed mechanism:** First pure replay of sanitized test observations; then a time-bounded, isolated telemetry-interruption test that does not alter persisted factual job outcomes.
- **Independent sources:** Actual scrape age, missing trace/log lookup, contradictory source values with clocks, policy denial and unchanged target state.
- **Abort:** Any mutation or authorization unexpectedly granted, inability to restore telemetry or loss of canonical records.
- **Proof:** Deterministic classification abstains, AI (if approved) is evaluated separately, unauthorized recovery denied, no success recorded from absent observations.

## Shared execution warning

The M6 implementation package presently provides the catalog, diagnostic tests, bounded load, queue observations and evidence/measurement harnesses. The six live injection/verification adapters and complete trial orchestration remain **integration work** until the final M5 source and operational approval gates are established. No script in this package claims to execute every scenario or certify their runtime result.
