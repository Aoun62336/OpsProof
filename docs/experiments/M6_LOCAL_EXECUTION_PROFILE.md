# Local M6 execution profile

This profile is declared before any M6 fault or benchmark is dispatched. It
preserves the M5 application, data, security policies, controllers and telemetry.
No production or cloud environment is in scope. External model calls are disabled
by the owner's explicit decision on 14 November 2026.

## Resources and staged UI checks

- Comprehensive environment startup retains M5's 5 GiB available host RAM,
  5 GiB Docker capacity and 15 GiB free workspace disk requirements.
- Bounded active-cluster trials require 2 GiB available host RAM before starting.
  The emergency stop remains 1 GiB. These are separate startup/steady-state
  profiles; the M5 bootstrap guard and existing k6 guard are unchanged.
- Earlier startup attempts had insufficient active-trial headroom. The accepted
  runs subsequently passed the recorded resource checks. The resumed session
  measures the running node through Kubernetes when Docker pipe access is denied.
  The verified node exposes six CPUs and approximately 9.7 GiB memory.
- The optional measurement profile temporarily scales only Grafana and the
  Argo CD UI server to zero. It preserves exact Deployment UID, Pod template,
  original replica count, images, resource limits, credentials and PVCs.
- Prometheus, Alertmanager, Loki, Tempo, OTLP collection, Argo CD reconciliation
  and repository server, Rollouts, KEDA, demo/control services and the OpsProof
  web interface remain running. The two paused UIs are verified in a separate
  stage and restored with readiness verification after measurements. The final
  local cluster is running with both UIs restored.
- All comparable capacity runs must use this same declared profile. Results
  cannot be mixed with historical M5 runs or called full-profile measurements.
- If this profile cannot satisfy the unchanged trial/abort floors, runtime work
  remains BLOCKED. No reduced-memory limits or missing telemetry substitute.

## Bounded scenarios

| Scenario | Mechanism and limit | Required outcome |
|---|---|---|
| Worker saturation | 60 ordinary 2,000-ms jobs; fixed healthy worker | Observed backlog; exact jobs and queue drain |
| Faulty release | Existing reviewed bad candidate through Argo-owned parameters; bounded traffic | Actual errors, failed AnalysisRun, controller abort and stable service |
| Database connectivity | Exclude only demo PostgreSQL from its existing additive allow policy; observe for <=10 s | Authenticated fresh database connections fail, control stays healthy, exact policy restoration and fresh-connection recovery. Existing pooled connections may remain usable. |
| Worker failure | One observed worker Pod, UID/resourceVersion-preconditioned zero-grace termination | Real in-flight interruption, replacement, lease reclaim and durable duplicate fencing |
| Downstream latency | GitOps opt-in fixed internal HTTP dependency; 1,000-ms delay, 400-ms client timeout | Timeout log, actual correlated client/server trace and normal completion after restoration |
| Misleading evidence | Interrupt only the owned observer connection; controlled stale/contradictory variants labeled separately | Abstention, no workload mutation and restored fresh telemetry |

Dispatch intent is committed before any adapter runs. Unknown acknowledgment,
abort or cleanup retains the reservation and indeterminate outcome. A separate
read-only process must collect fresh postconditions before release. Each complete
execution has a 600-second ledger deadline; cleanup remains required afterward.

## Capacity and qualification

The M6 Python capacity-v3-local protocol retains 60 jobs of 2,000 ms, 120 seconds of
80-request/second background traffic, bounded warmup and nearest-rank p95.
It uses a bounded local generator over an owned port-forward, emits immediate
intents/receipts and keeps every attempt in a unique directory. It does not grant
the actuator permission to create arbitrary Pods. Five consecutive readiness
requests form the warmup; raw failures and all measurements remain recorded.
At least three independently passing trials per fixed/API-HPA/worker-KEDA mode
are required. HPA explicitly targets an existing Rollout's scale subresource
when that profile is opted in; no duplicate API Deployment or ownership cutover
is introduced. The separate k6 protocol retains its own limits and evidence.

Synthetic deterministic qualification is distinct from held-out real incidents.
No held-out labels, model accuracy, optimization gain or savings are invented.
The owner deferred Groq/Gemini qualification and AWS provisioning to the next
milestone. The retained AWS cost model records its prospective assumptions.

## Recorded completion on 15 November 2026

All six scenarios have passing independent verification. The worker-crash pass
used the owner's separately approved exact-container SIGKILL in the local k3d
node. Ordinary Pod deletion can allow the short job to finish during shutdown,
which is recorded as a failed hypothesis when restoration is verified.

The accepted capacity comparison has three passing runs per mode. Actual served
background rates are retained alongside the nominal 80-request/second target.
The report and matrix identify the retained failed attempts, the owner-deferred
provider work and the independent review steps.
