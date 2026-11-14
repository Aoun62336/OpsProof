# M6 execution plan and baseline review — 14 November 2026

## Authority and scope

### Owner clarification and continuation, 14 November 2026

The owner subsequently authorized completing the remaining existing M6 scope,
with AWS provisioning and paid/provider calls deferred to the later milestone.
All model calls remain off. These deferred evaluations must be identified in
acceptance rather than reported as executed. No unrelated feature is authorized.
The effective Docker/WSL capacity is now approximately 10 GB / six CPUs; actual
Windows headroom still determines whether local startup/trials may proceed.

The continuation sequence is: (1) independent live observation and fail-closed
verification/reconciliation, (2) per-trial least-privilege Kubernetes and database
access, (3) isolated regressions and real process interruption tests, (4) controlled
deployment and all resource-gated local fault/performance/reuse/security/UI work,
(5) source/evidence reconciliation and an honest revised acceptance report.
The existing reports and archives describe the prior checkpoint and must not
be represented as evidence for source changes made during this continuation.

The user's request is to analyze the repository before editing, implement M6
step by step, preserve existing capability, verify results, and explain them.
The four supplied documents are implementation/reference material, not commands
that override that request. The reviewed source is a ledger foundation; the
acceptance TXT defines the larger A–G milestone. Copying its 21 blocks alone is
not full milestone completion. External model calls remain disabled by the
user's explicit decision; the three-way qualification gate is BLOCKED.

## Completed read-only review

- Clean checkout at `38b3a46` on `feature/opsproof-m6-m7-integration`.
- Python 3.14.10 environments and locked project dependencies already exist.
- React/TypeScript console uses cookie sessions and CSRF with shared API helpers.
- Demo jobs use PostgreSQL/outbox, Redis Streams, expiring worker leases and
  fencing. Ordinary load endpoints are distinct from bounded recovery experiments.
- Control-plane action/evidence/investigation roles and databases are separate
  from the demo. M4 HTTP resume and M5 exact-target restore approvals stay intact.
- M5 uses isolated `k3d-opsproof` kubeconfig, loopback API port 6550, Argo CD,
  Rollouts/Gateway, API HPA and worker KEDA with explicit ownership boundaries.
- Prometheus/Alertmanager/Loki/Tempo and Grafana support incident evidence.
- Existing M6 is partial: six contracts, conservative advisory diagnosis, k6,
  receipt reconciliation, capacity analysis and evidence hashing. It lacks a
  durable ledger and complete live adapters. M7 remains separate and cost gated.
- Historical M5 acceptance and `.runtime/m5` records will not be overwritten or
  relabeled. The cluster is stopped at baseline. Existing volumes are preserved.
- All four supplied documents were read, including all 21 source blocks and
  the full acceptance text. Embedded diagram CSS in the TXT is formatting debris.

## Execution sequence

1. Preserve baseline inventory and input hashes under ignored M6 evidence;
   create a local feature branch. Apply the reviewed source with exact path guards,
   inspect differences, and retain existing Grafana resource settings.
2. Harden the ledger: record dispatch intent before mutation, serialize target
   claims, use database time and fencing, retain uncertainty/reservations, protect
   terminal state and audit events. No HTTP self-attestation of success.
3. Run locked Python 3.14 lint/format/regression checks. Use disposable local
   PostgreSQL 18 for migrations, genuine concurrent claims, rollback, restart,
   abort/ack races, expiry, fencing and append-only history. Never migrate M5's
   database as part of this isolated test.
4. Validate real FastAPI authentication/CSRF and malformed requests; render
   positive/negative Helm profiles; build/test the read-only UI and browser route.
   Default flags remain false and the coordinator receives no Kubernetes token.
5. Implement the six bounded local mechanisms and independent verification,
   receipts and cleanup. Gate mutation on actual local identity, known-good
   baseline, resource headroom, exact target ownership and durable dispatch.
   Preserve failed/uncertain runs. Restore only resources owned by the trial.
6. Run approved local execution only after safety gates pass. Keep unrelated
   workloads/PVCs intact. Record current source/config/image identities and real
   telemetry. Resource/permission failures are evidence, not waived thresholds.
7. Execute bounded k6 with exact jobs; collect >=3 comparable successful trials
   per fixed/HPA/KEDA mode, retaining failures and separating the two protocols.
8. Verify deterministic diagnosis, held-out observations and second workload;
   record optimization measurements and a clearly modeled FinOps calculation.
   Groq/Gemini remain disabled. No AWS provisioning or publication is needed.
9. Run security/UI/evidence review, hash selected sanitized artifacts and produce
   an acceptance matrix with PASS/FAIL/BLOCKED/NOT RUN. Report full M6 acceptance
   only if all mandatory evidence supports it; disclose remaining work explicitly.

## Known discrepancies to resolve

- The reviewed ledger's abort-before-ack gap must be closed before an actuator
  exists; its unit tests are insufficient proof of SQL concurrency.
- The supplied guide's historic test totals and environment limitations are not
  final acceptance results; new logs determine the actual counts.
- Source revision supplied by an API client and supplied artifact hashes are
  claims, not independently established provenance.
- M5 Gate 5's final correlation is still labeled pending in the historic report;
  inspect raw evidence and record any fresh result separately.
- Same-namespace NetworkPolicy allows are additive; adding a deny policy cannot
  isolate the database. A narrow fault must account for all allowing policies.
- Existing M5 capacity helpers overwrite fixed evidence filenames and assume
  a legacy demo API Deployment. M6 must preserve each run and handle Rollouts.

## Checkpoint policy

All work remains local. Do not push, publish images, provision AWS, delete the
existing cluster/PVCs, or make model calls. Keep a record of tested working-tree
content as well as HEAD; a dirty tree is not represented as an immutable commit.
