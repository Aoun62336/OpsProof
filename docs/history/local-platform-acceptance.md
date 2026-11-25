> Historical record. Commands, paths and results below describe the recorded revision. See [the current repository guide](../../README.md) for maintained commands and status.

# M5 acceptance report — 9 November 2026

Status: local runtime acceptance passed; final revision and evidence packaging recorded in `final-state.json` and the archive manifest. Changes remain local; no GitHub or registry push and no hosted CI execution.

This report supersedes the November 7 and 8 checkpoints. It maps the repository's foundation and Stage 4–7 acceptance contracts to measured evidence. The originally supplied Desktop `M5 criteria.txt` could not be found during finalization; this is not a claim of a fresh verbatim audit of that missing file.

## Acceptance matrix

Evidence paths below are relative to `.runtime/m5/acceptance/`.

| Gate | Result | Verification and evidence |
|---|---|---|
| 0 — M4 regression | PASS locally | Existing approved recovery, exact jobs and alert resolution: `m4-recovery-trial.json`. Backend/frontend checks: `source-validation.json`. Post-restart smoke: `../k3d-smoke.json`. |
| 1 — Cluster/resources | PASS | Guarded local bootstrap and disposable cleanup: `bootstrap-cleanup.json`; real cluster restarted, all nine PVC identities and default kubeconfig preserved. Full-profile measurements: `final-runtime-resources.json`. |
| 2 — Deployment/security/persistence | PASS | Separate state/credentials, restricted Pod Security, observed network/RBAC denials: `k8s-foundation-security.json`. Dependency Pod replacement preserved data: `persistence.json`. Recovery credentials/permissions: `kubernetes-rbac.json` (23 checks). |
| 3 — Gateway/authentication/UI | PASS | Twelve HTTP checks: `gateway-http.json`. Browser scenarios: ten passed in `final-browser.log`, remaining two passed in `final-browser-retry.log` after API route correction. This is not one uninterrupted twelve-test pass. |
| 4 — GitOps | PASS locally | Reachable local Git SHA, actual revision change, drift correction and comparison-error recovery: `gitops-adoption.json`, `gitops-trial.json`. Read-only in-cluster Git server substitutes for external publication by user instruction. Final reconciliation: `final-state.json`. |
| 5 — Progressive delivery | Pending final correlation | Distinct images, actual healthy promotion and faulty-image rejection/abort/restored traffic: `release-images.json`, `healthy-rollout.json`, `faulty-rollout.json`. Missing metrics fail closed: `missing-metrics-analysis.json`. Scoped route permissions: `rollouts-route-rbac.json`. Final stored incident/failed-request trace correlation: `release-incident-trace.json`. |
| 6 — Capacity and consumer recovery | PASS | Equivalent fixed/HPA/KEDA trials, real scale-out/in and durable completion: `scaling-fixed.json`, `scaling-hpa.json`, `scaling-keda.json`. Interrupted consumer reclaim and duplicate-delivery fencing: `consumer-recovery.json`. |
| 7 — Restricted recovery and source gates | PASS locally | Approved fixed-target restore and independent verification: `kubernetes-recovery-trial.json`. Negative client/policy tests and other regressions: `source-validation.json`. Secret/schema checks: `secret-scan.json`, `schema-check.json`. Operational instructions: `M5_LOCAL_RUNBOOK.md`. Hosted CI remains unexecuted. |

## Measured capacity

Each successful trial used the same load-script SHA-256 `b2954fcebc658ac76c42c917fffcf152dbdbc92db725268a1d0ba77a8a7b61e2`: 60 jobs, 2,000 ms per job, 120 seconds targeting 80 HTTP requests/second, with bounded readiness warmup. One successful trial per mode; these local observations are not a statistical performance guarantee.

| Mode | Replica cycle | Job p95 | Throughput | HTTP failures |
|---|---|---:|---:|---:|
| Fixed | API 1; worker 1 | 110.39 s | 0.50 jobs/s | 0 |
| HPA | API 1 → 2 → 1; worker 1 | 110.34 s | 0.50 jobs/s | 0 |
| KEDA | Worker 1 → 3 → 1; API 1 | 40.09 s | 1.25 jobs/s | 0 |

HPA increased API replicas but did not improve worker throughput in this workload. Queue lag/pending, exact jobs, replica samples and resource measurements are retained in the JSON evidence. Earlier failed startup/memory/interruption attempts remain separately recorded, not counted as passes.

## Recovery and observability evidence

The supported Kubernetes action is only `restore_demo_worker`, targeting `Deployment/opsproof-demo/demo-worker`, from zero to one replica. Approval requires `APPROVE DEMO WORKER RESTORE` and expires after 120 seconds. Execution revalidates target UID/resourceVersion/image, incident, telemetry and controller ownership. Unknown outcomes are indeterminate; independent evidence, not PATCH success, establishes recovery. The action worker has fixed-target mutation rights; the evidence worker is read-only; the API has no Kubernetes mutation credentials.

- M4 run `5227ba60-bc9a-4c94-be55-dc50f421c696`, recovery `0eef5016-9f41-46e2-b88f-96ed4952b6d5`.
- Kubernetes run `f0103cc1-9397-455d-993c-ade8e0125de1`, recovery `5afb1844-27ae-486e-91e3-139444b00279`.
- Negative cases include anonymous access, wrong confirmation, unsupported namespace, unapproved proposal, expired/replayed approval, stale resourceVersion and interrupted/uncertain execution.
- Expiry and interrupted-action tests used explicit stored database fixtures; they were not actual process crashes or elapsed-time expiry drills. The separate consumer recovery test did interrupt a real consumer.
- The recovery test's assertions and durable evidence passed, but its helper emitted a Python pool-shutdown error. The helper now closes its pool; the original log remains preserved.
- `observability-verification.json` proves instrumented traces and worker logs through Tempo/Loki and authenticated Grafana. Its explicit synthetic log is identified separately from real worker logs.

## Source, artifacts and verification scope

The completed source run passed 143 control-plane tests, 23 demo tests, 16 M5 tests, four web unit tests, eight Helm render configurations covering 61 objects, and web lint/build. Strict built-in Kubernetes schema validation passed 25 objects; custom resources were validated by the live API. Gitleaks found no source leaks. Final focused changes are recorded in `final-checks.log`.

Application images retain their tested provenance; a documentation-only Git revision does not imply rebuilt images. `release-images.json` identifies three distinct stable/healthy/faulty image digests and generated release-code hashes. `final-state.json` records the final GitOps revision and deployed image identities.

Installed local profile includes k3s 1.35.5, Argo CD chart 10.14.0/application 3.6.1, KEDA 2.21.0, Traefik chart 42.3.0/application 3.7.17, Gateway API 1.6.1, Argo Rollouts 1.10.2 and Gateway plugin 0.17.0. The plugin binary was checksum-verified and baked into the local controller image. Inspect installer/evidence records for exact image digests.

Memory gates remain enforced: 5 GiB free for bootstrap and 1 GiB minimum during the bounded release trial. The disposable bootstrap test measured sufficient free memory after stopping the preserved main cluster. Full-profile steady-state resource evidence is separate from bootstrap headroom. Capacity UI does not invent a cloud cost estimate.

## Delivery and limitations

The evidence archive contains a curated selection of results/logs, this report, the runbook and a SHA-256 manifest. Credentials, kubeconfigs and Secret objects are excluded. Failed attempts remain in the workspace for audit.

GitHub publication and hosted CI were intentionally not performed. Acceptance is local; any requirement for remote publication or hosted execution remains outside this delivery. The original missing criteria TXT cannot be newly cross-checked verbatim. The source contracts and their observed local results are explicitly mapped above.
