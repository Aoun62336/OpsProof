# M5 acceptance checkpoint — 8 November 2026

**M5 is not complete. Changes remain local; nothing was pushed to GitHub.**
This checkpoint supersedes the older report's status statements. Evidence is
under `.runtime/m5/acceptance/`; implementation in the working tree includes
unfinished changes and is not a tested final release.

## Acceptance criteria

| Gate | Result | Evidence and remaining work |
|---|---|---|
| 0 — M4 regression | Partial | Earlier backend/frontend/browser checks passed. Real Kubernetes trace and synthetic log retrieval passed directly against Tempo/Loki. Grafana proxy verification failed; full approved M4 recovery and final-source regression remain outstanding. |
| 1 — Cluster/resources | Partial | Local k3d node and workloads operate; resource preflight previously passed. Build cache was reclaimed without deleting data. Full-profile resource capture and tested safe teardown remain outstanding. |
| 2 — Deployment/security | Verified on earlier deployed revision | Five exact jobs, persistent PostgreSQL/Redis data, namespace boundaries, restricted Pod Security and RBAC/network denials passed. Recheck changed recovery permissions against final deployment. |
| 3 — Gateway | Verified on earlier deployed revision | Real HTTP/authentication/CSRF/logout and eight browser tests passed. Newly prepared internal release listener has not been deployed or live-verified. |
| 4 — GitOps | Local runtime verified | Five Applications are Synced/Healthy. Actual Git revision change, harmless drift correction and sync-error recovery passed using a read-only in-cluster Git server. GitHub publication and remote CI remain intentionally unperformed. |
| 5 — Rollouts | Incomplete | Namespaced controller installed; plugin checksum verified; three distinct image identities built. Healthy promotion, measured faulty release, analysis failure and independently verified abort/routing remain unperformed. |
| 6 — Autoscaling | Live trials passed | Equivalent fixed/HPA/KEDA runs completed; scale-out and scale-in observed. Interrupted consumer recovery and duplicate-delivery fencing passed. Results below. |
| 7 — Restricted recovery/UI/CI | Incomplete | Typed recovery policy, schema migration, worker/API integration and scoped RBAC drafted; 21 policy tests passed. Not deployed or accepted. Full negative/integration tests, UI extensions, CI/security gates and final runbooks remain outstanding. |

## Comparable capacity trials

Each successful run used the same script SHA-256
`b2954fcebc658ac76c42c917fffcf152dbdbc92db725268a1d0ba77a8a7b61e2`:
60 jobs, 2,000 ms per job, 120 seconds of HTTP traffic targeting 80 requests/second,
and a bounded readiness warmup. One successful trial per mode; these are observed
local results, not a statistically established performance guarantee.

| Mode | Observed replica cycle | Job p95 | Throughput | Measured HTTP failures |
|---|---|---:|---:|---:|
| Fixed | API 1; worker 1 | 110.39 s | 0.50 jobs/s | 0 |
| HPA | API 1 → 2 → 1; worker 1 | 110.34 s | 0.50 jobs/s | 0 |
| KEDA | Worker 1 → 3 → 1; API 1 | 40.09 s | 1.25 jobs/s | 0 |

Exact job records, Redis lag/pending, replica samples and resource metrics are in
`scaling-fixed.json`, `scaling-hpa.json`, and `scaling-keda.json`.
Earlier failed startup/memory trials were preserved separately rather than counted
as passes. CPU scaling increased API capacity; it did not improve worker throughput
in this workload.

`consumer-recovery.json` records a real interrupted consumer and job
`c9b18aa3-07eb-4c3d-965d-e6fa86e67733`: pending work was reclaimed, the job completed
on its second attempt, and duplicate stream delivery left the completed record
unchanged. Earlier unsuccessful interruption attempts remain recorded separately.

## Current live state

The latest read-only check found all five Argo CD Applications Synced/Healthy and
all six observability Pods Running/Ready. This does not certify telemetry delivery
through Grafana or the unfinished recovery/rollout features.

## Implementation issues to resolve before deployment

- Recovery verification must expire to indeterminate even when telemetry collection
  fails continuously; currently its deadline check is inside successful collection.
- The recovery actuator must independently reject an active KEDA controller before
  restoring the worker. The Helm ownership conflict guard alone is insufficient.
- Recovery-mode worker replica ownership needs a narrowly scoped Argo CD exception
  before a stopped-worker drill; otherwise self-healing could be misattributed.
- Complete lint cleanup and test client/RBAC, uncertain PATCH, crash/restart,
  stale resourceVersion, approval expiry/replay and independent verification paths.
- Diagnose authenticated Grafana datasource proxy 404 responses before claiming
  full telemetry acceptance.

## Next bounded work

Resolve Grafana delivery and run one telemetry verification; then complete the
healthy/faulty release trials. Do not rebuild unrelated images or repeat completed
capacity trials unless their implementation or test inputs change. Keep unfinished
recovery disabled until the issues above and its full tests are resolved.

Never distribute `.env`, kubeconfig, tokens, cookies or Secret contents with this report.
