# OpsProof v1.0 | M6 engineering implementation record

**Status:** An additive M6 source/contract and evidence-harness implementation has been prepared against the historical `OpsProof(3).zip` source. **Milestone 5 remains unaccepted and the user has announced a newer final repository ZIP.** No cluster tests, fault injection, paid AI or AWS calls were performed here. This is not a completed or accepted Milestone 6.

## Exact architectural baseline

The existing source has a demo API, transactional PostgreSQL job/outbox state, Redis Streams delivery and leased workers; a separately credentialed control API and action/evidence workers; an operator UI; Prometheus, Alertmanager, Loki and Tempo; and Kubernetes/GitOps/rollout/scaling/recovery source introduced in M5. Existing contracts matter:

- `apps/control-plane/src/opsproof_control/contracts.py` restricts the operator queue-burst to **1–8 jobs** and `duration_ms` 50–750. The M6 k6 runner **never uses this recovery-authorized experiment endpoint**.
- `apps/demo-workload/src/opsproof_demo/api.py` permits regular durable `POST /api/v1/jobs` with **50–2000 ms duration** and an idempotency key. M6's bounded load generator uses this ordinary endpoint.
- `scripts/m5/verify_scaling.py` already implements actual fixed/HPA/KEDA local trials using `scripts/m5/capacity_load.py`. The M6 analyzer consumes its **existing** JSON format; it does not replace that harness or reinterpret API HPA as worker scaling.
- Existing M4 recovery policy and M5 `restore_demo_worker` authorization are unchanged. New M6 diagnosis is **advisory** and the action field is literally `none`.

## Added source and purpose

| New exact path | Purpose and trust boundary |
|---|---|
| `apps/control-plane/src/opsproof_control/m6_diagnosis.py` | Conservative multi-signal signature detection with abstention, never recovery permission |
| `apps/control-plane/src/opsproof_control/m6_trial_state.py` | Pure, explicit state-transition rules; must later be backed by durable transactional state and target leases |
| `scripts/m6/contracts.py` | Exactly six approved scenario IDs, known targets, injection and cleanup contracts, bounded workload guard |
| `scripts/m6/preflight.py` | Read-only k3d identity, node and namespace preflight using an explicit kubeconfig |
| `scripts/m6/collect_queue_state.py` | Read-only Redis consumer-group lag/pending, Kubernetes desired/ready replicas and actual durable job counts |
| `benchmarks/k6/jobs.js` | Local-only constant-arrival-rate durable job POSTs; strict count/duration/VU/url limits and exact receipts |
| `scripts/m6/reconcile_jobs.py` | Independent GET verification of exact job IDs and terminal state, retries and duration |
| `scripts/m6/run_k6_local.py` | Owns a k3d-only loopback port-forward; requires explicit test-data consent, caps HTTP load, continuously guards host RAM and closes its process on failure |
| `scripts/m6/analyze_capacity.py` | Requires 3+ independent, passing, equivalent trials for **each** fixed/HPA/KEDA configuration |
| `benchmarks/ai/qualification_v1.json` | Twenty independently authored synthetic labels spanning five recognizable signatures and abstentions |
| `scripts/m6/qualify.py` | Offline deterministic comparison by default; separately consent-gated Groq/Gemini calls, at most 2 cases/run |
| `scripts/m6/evidence_manifest.py` | Explicit selected-file SHA-256 identities with secret-path and symlink checks |
| `scripts/m6/verify_scenarios.py` | Metadata consistency on exactly six run records; explicitly **not** evidence of live successful scenarios |
| `scripts/m6/tests/` | Isolated positive and negative tests of safety, diagnosis, metrics, qualification and trial contracts |
| `docs/experiments/M6_FULL_SYSTEM_VERIFICATION.md` | Local-to-cloud commandbook and execution profiles |
| `docs/experiments/M6_SCENARIO_CATALOG.md` | Six scenario fault/test contracts and postconditions |

## Important engineering boundaries

### 1. Experiment authority is separate from action authority

The M6 scenario catalog describes a test intent, but **does not implement** a general-purpose Kubernetes fault injector. A typed trial-state transition is not a security credential or distributed lock. The accepted M5 source must determine how local test-only faults acquire and release narrow namespace resources. The existing recovery executor remains a separate, human-approved operation with its own permissions.

### 2. Synthetic label equality is not accuracy on real incidents

`M6_diagnosis` uses conservative, corroborated **signatures**, not causal root-cause proof. It intentionally rejects stale Prometheus evidence, contradictory observations, multiple competing signatures, absent relevant log/trace observations, and unknown classes. It cannot change M4's `allowed_recovery()` or any Kubernetes approval decision.

The 20-case dataset is useful for regression tests. A later frozen, manually reviewed held-out dataset from actual faults is required. The known trial's scenario ID, fault injection metadata and expected label must **not** be passed to the AI or diagnostic evaluator as evidence.

### 3. Capacity performance must be scientifically interpretable

`analyze_capacity.py` will not compute an improvement until each mode supplies three passed, distinct, same-source, same-load records. It rejects retries and HTTP failures in the clean capacity comparison, because the current M5 benchmark expects no retries. Worker-crash experiments are a **different** protocol and may legitimately have multiple attempts without duplicate durable completion.

If the user changes M5's benchmark format, revise the adapter after auditing the final source. Do not rewrite or silently reinterpret M5's historical run records.

### 4. Receipt does not mean completion

k6 prints one receipt for each attempted job. `reconcile_jobs.py` rejects missing receipts, duplicate keys, mismatched/duplicate IDs, wrong response identities, failed jobs, unsupported states, missing timestamps and non-completion by its deadline. Its recorded job p95 uses nearest-rank on the exact completed job set. This is an **observed local job latency**, not a production latency percentile or proof of exactly-once execution.

### 5. Credibility of evidence

`evidence_manifest.py` emits SHA-256 file hashes, not cryptographic signatures. `verify_scenarios.py` only checks metadata shape, never declares the six scenarios independently passed. The final reviewer must open the actual logs, traces, database results, kubectl events, Prometheus samples and source-linked reports.

## Remaining integrated M6 source implementation after authoritative final ZIP

The following **mandatory** work is *not* silently claimed as implemented by these preparatory files:

1. Transactional durable M6 trial orchestration, target lease/lock and audited crash/retry/cleanup. Reconcile against final migration chain before adding `0006` or a higher revision.
2. Six approved, bounded, **actual** fault injection and independent verification adapters. Reuse M5's Rollouts and consumer-recovery tests where appropriate; do not duplicate controllers.
3. Application-integrated test-only downstream HTTP dependency, bounded timeouts/backoff and real traces.
4. Complete database-connectivity isolation with GitOps-aware ownership and demonstrable safe restoration.
5. Actual retained Prometheus/Loki/Tempo incident correlation for all scenarios and a real missing-telemetry trial.
6. k6 plus exact-job integration runs and three+ repeated, comparable fixed/HPA/KEDA trials under a measured resource profile.
7. Independent held-out fault benchmarks, model provider qualification only with separate explicit permission, and reviewed cost results.
8. Second independent workload deployment, read-only investigation adapter and verified cross-target isolation.
9. Real API-backed experiment/measurement views in the existing Forest & Porcelain UI, Playwright/axe tests and appropriate CI checks.
10. Sanitized public replay candidate, complete evidence pack, FinOps model and full acceptance on the actually tested source revision.

**Gate:** None of those are waived because an offline contract or metadata fixture passes. The final M5 ZIP must be reconciled first; no working higher-level implementation may be overwritten by this older-snapshot addition.
