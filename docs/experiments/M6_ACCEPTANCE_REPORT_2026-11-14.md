# M6 implementation and acceptance report — 14 November 2026

> Earlier checkpoint: the owner has authorized a continuation to complete local
> M6, with AWS provisioning and provider evaluations deferred. This report and its
> original archives describe the earlier checkpoint, not the current continuation.
> New source and runtime evidence are being retained separately under `.runtime/m6`.

**Overall result: M6 is partially implemented and is NOT accepted as a complete milestone.**
The durable trial ledger, authenticated API, operator page and isolated validation
are implemented. The six live fault mechanisms and comparison helpers are
experimental source awaiting runtime qualification. No M6 fault, k6 load,
nine-run capacity comparison or second-workload investigation was completed.
Groq and Gemini calls remain disabled by the user's explicit instruction.

Read this with the [execution plan](../engineering/M6_EXECUTION_PLAN_2026-11-14.md),
[criterion-by-criterion matrix](M6_ACCEPTANCE_MATRIX_2026-11-14.md),
[local execution profile](M6_LOCAL_EXECUTION_PROFILE.md) and
[verification runbook](M6_VERIFICATION_RUNBOOK_2026-11-14.md).

## What the project does and where M6 fits

The demo API accepts durable jobs. PostgreSQL records the jobs and an outbox;
Redis Streams carries work to workers. Leases and fencing prevent an old worker
from completing work after a newer owner takes over. A separate control plane
collects evidence, creates investigations and applies the narrowly approved
M4/M5 recovery operations. Its database and Redis are separate from the demo.

The local M5 platform uses k3d, Argo CD, Argo Rollouts/Gateway, API HPA and worker
KEDA. Prometheus, Loki and Tempo provide metrics, logs and traces. The React
console uses existing operator authentication, browser cookies and CSRF checks.
M7 cloud/release work remains separately gated.

M6 adds controlled experiments and proof about their outcomes. A script returning
zero is insufficient: the system must preserve the request, establish what was
actually changed, observe its effect, restore the target and independently
verify the result. Performance and diagnosis claims require their own evidence.

## How the supplied material was applied

The repository and all four supplied files were read before editing. The three
reviewed Markdown files describe a **21-file ledger foundation**, explicitly
short of complete M6. The acceptance TXT defines the larger seven-gate milestone.
Instructions inside those documents were treated as reference requirements;
the user's request and subsequent restrictions determine authorization.

The starting tree was clean at
`38b3a4620882467805b10f36a3260ed55188116a`. Work is on the local branch
`feature/m6-durable-trial-ledger`. Changes are uncommitted. No push, publication,
AWS provisioning or external model evaluation was performed. The source bundle
and SHA-256 inventory identify the actual changed files; the old commit alone
does not contain this implementation.

## What was implemented and why

1. **Durable experiment history.** Additive migration `0006_m6_trials` introduces
   trials, ordered events, approvals, execution reservations, dispatch intent,
   reconciliation and reuse observations. Original migrations remain unchanged.
   The ledger uses PostgreSQL time, transactional claims and fencing. Target
   locks and a shared local-environment reservation prevent conflicting trials.
2. **Safe treatment of uncertainty.** Dispatch intent commits before mutation.
   Lost acknowledgments cannot trigger blind replay. Abort after possible
   dispatch retains uncertainty and reservations. Append-only events and
   immutable terminal trials prevent rewriting history. Cleanup reconciliation
   is recorded separately; it does not turn an indeterminate run into success.
   A database artifact reference is still a claim unless a trusted independent
   producer establishes it; full provenance acceptance remains open.
3. **API and operator page.** `/api/v1/m6/trials` uses existing authentication and
   CSRF. Strict inputs reject unsupported scenarios and invalid types. The
   `/trials` page reads actual trial records and event history, with loading,
   empty, disabled and error handling. There is no HTTP endpoint allowing a
   caller simply to declare injection or success. M6, arming, reuse and the
   separate bookkeeping worker all default to disabled.
4. **Six bounded experimental adapters.** Source now covers saturation, a bad
   release, database connectivity loss, worker death during work, downstream
   delay and misleading evidence. Exact resource identity, bounded load,
   dispatch intent, cleanup and a separate verification process are included.
   Database isolation edits the relevant existing allow rule because Kubernetes
   NetworkPolicy allows are additive. Misleading observations are explicitly
   marked as replayed. These adapters have source tests, **not live acceptance**.
5. **Measurements and reuse.** Capacity helpers retain unique run identities,
   submitted-job receipts and durable reconciliation. Explicit opt-in HPA can
   target the existing Rollout without creating a competing API Deployment.
   Downstream spans and fixture metrics support future genuine trace evidence.
   A second-workload observer is read-only, narrowly configured and conservative
   when telemetry is missing. The second workload was not deployed for acceptance.
6. **Packaging and costs.** Runtime images retain locked application dependencies,
   nonroot operation and multistage builds. Unused runtime pip tooling was removed;
   available Debian zlib and Alpine updates were applied. Local image identity,
   size, timing, package inventory, smoke tests and vulnerability reports are
   retained. Public Mumbai pricing was collected for an explicit illustrative
   AWS model; no account billing was accessed and no spending was measured.

Existing M4/M5 recovery implementations, migration history, dependency lockfiles,
M5 benchmark protocol and Grafana's 128 MiB request / 384 MiB limit are preserved.
Source reconciliation records exact protected-file comparisons and explains the
intentional integration changes. Local Python 3.14 app checks use the existing
locks; the native Helm inspection helper uses the installed Python 3.12/PyYAML.

## What the evidence actually proves

The final evidence index is
`.runtime/m6/handover/verification-summary.json`. It points to uniquely named raw
results and records the final source tree hash. The evidence archive contains
selected sanitized results and a SHA-256 manifest. Full raw local results remain
under `.runtime/m6/acceptance`; they are not all suitable for publication.

| Verification | Proven scope | Important limit |
| --- | --- | --- |
| Locked Python regressions, Ruff and formatting | Control plane, M5/M6/M7 source contracts, demo regressions | Ordinary suite skips SQL tests; separate real SQL runner supplies that evidence |
| Disposable PostgreSQL 18 | Migrations, preserved M5 sentinel, concurrent claims/idempotency, rollback, connection restart, fencing, expiry, abort/ack races and immutable history | No migration of the existing M5 database; no real actuator process-kill campaign |
| Real API plus Playwright | Actual SQL trial records, authentication, desktop/mobile navigation and accessibility | Isolated local API; not deployed Kubernetes UI or a completed live trial lifecycle |
| Vitest, TypeScript production build and lint | Frontend behavior and compilation | Mocked unit results remain distinct from the real browser test |
| Native Helm validation | 21 positive/negative chart profiles | Rendering does not prove installed RBAC or NetworkPolicy enforcement |
| Deterministic qualification | 20/20 synthetic hypotheses and 20/20 abstention decisions, zero invalid/error cases | No held-out real incidents, independent ground-truth review or model comparison |
| Image smoke and Trivy | Exact final local image IDs, isolated nonroot runtime, actual vulnerability inventory | Dependency-free readiness is intentionally 503; no end-to-end deployed image acceptance |
| Secret scan | Pinned Gitleaks on tracked plus nonignored new source | No staged/committed release or external independent review |

Final observed counts: **260 Python tests passed, 20 SQL tests skipped in the
ordinary suite and 14 subtests passed; 27 demo tests passed; 12 frontend tests
passed; 20 separate real PostgreSQL/API tests passed; one real Playwright test
passed; and all 21 Helm profiles passed.** The 20 skipped tests are the SQL suite
run separately against disposable PostgreSQL, not ignored verification work.
All 15 source-validation checks passed. A fresh source copy with a newly created
locked Python environment and a fresh npm installation also passed the 260-test
suite, frontend tests and production build. Its log confirms Python imported
the copied source rather than the original working directory.

A fresh source-copy reproduction record states exactly which checks were rerun
from the copied tree. It is not a substitute for a clean committed release and
complete live reproduction. Exact final test counts and command exit codes are
in the evidence index rather than historical counts from the supplied guides.

## Why live execution stopped

The original stopped `k3d-opsproof` cluster was started after the startup resource
check passed. All nine existing PVC UIDs and the default kubeconfig hash were
preserved. Startup exposed a pre-existing Rollouts controller failure: its
NetworkPolicy still allowed an old k3d API node address. A guarded helper refreshed
only the API endpoint peers in the two existing allowlists; selectors, narrow
ports, other rules and RBAC were retained. The controller subsequently recovered.
Controller recovery was observed in command output; no later saved full-stack
readiness result is claimed. This is current local environment maintenance,
not proof of a completed M6 trial.
The earlier startup JSON still correctly records its failed readiness check.

With the complete stack running, host free RAM settled around 1.96 GiB after
cache reclamation. There were no leftover test servers to reclaim. The user
confirmed no further memory could be freed. A reversible attempt to pause only
Grafana and the Argo CD UI crossed the 1 GiB emergency floor; execution stopped
before any M6 fault or benchmark. Original desired replica counts were restored
and the cluster was stopped. The UI restoration record does **not** claim ready
pods, because readiness was not reverified before stopping.

The existing M5 5 GiB startup floor remains unchanged. The new written profile
requires 2 GiB free after startup for a bounded trial and stops below 1 GiB.
Changing that profile does not manufacture passing resource evidence: even the
bounded profile failed on this host. Removing observability, weakening safety or
reducing acceptance requirements to obtain a pass was not used.

## Security findings remain open

The final Trivy results report **zero web vulnerabilities**. Each Python image
reports **0 critical and 47 high package findings**, covering **11 unique CVEs**,
with no fixed version offered for those high findings in the scan. They remain
open upstream security debt, not waived findings. Nonroot, read-only smoke tests
and dropped capabilities are useful controls, not proof of non-exploitability.
The report includes medium, low and unknown findings as well; no
`ignore-unfixed` filter was used. Scanner exit zero means the scan ran, not that
the image passed a vulnerability policy.

The experimental host actuator currently relies on local administrator
kubeconfig access. Dedicated least-privilege fault execution and real negative
RBAC/NetworkPolicy tests still require implementation/review and runtime proof.
Trusted artifact producers, independently verified authority boundaries and
actual process-crash behavior are also incomplete acceptance work. M6 must not
be promoted on the strength of SQL artifact-shape checks alone.

## FinOps result and its meaning

The illustrative Mumbai model uses eight hours of one EKS standard-support
cluster and one Linux t3.large, one public IPv4, 39 GB of gp3, explicit small
logging/query/transfer volumes and a T3 CPU-credit range. It produces about
**$2.38–$2.94**, or **$3.53 including a 20% reserve on the upper estimate**.
Actual spending is unknown; credits, taxes and free tiers are not assumed.
NAT gateways, load balancers, snapshots and hosted zones are excluded because
the modeled topology does not include them. This is an unapproved example, not
a cloud deployment budget or a measurement of M6 savings.

Raw selected price rows, region, fetch time, source hashes and all assumptions
are retained in `finops-analysis.json` and its pricing evidence. Sources are the
[AWS Price List Bulk API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-the-aws-price-list-bulk-api-fetching-price-list-files-manually.html),
[EKS pricing](https://aws.amazon.com/eks/pricing/) and
[VPC pricing](https://aws.amazon.com/vpc/pricing/).
Pod autoscaling alone does not reduce a fixed EC2 node bill. Comparable runtime
before/after measurements and any actual savings claim remain blocked.

## What remains before M6 can be accepted

1. Review and complete restricted fault authority, trusted evidence production,
   real process-crash handling and live UI evidence integration. Resolve the
   acceptance matrix's source-level gaps as well as its runtime blockers.
2. Provide a local environment that passes startup and sustained trial headroom.
   Recheck all M5 dependencies, the repaired API pins and final application health.
3. Deploy identifiable M6 images and additive migration through the intended
   ownership path. Keep defaults off until the explicit trial configuration is
   reviewed. Do not replace local image IDs with invented registry digests.
4. Execute all six faults with genuine telemetry, incident correlation, bounded
   cleanup, independent current-state verification and retained failed attempts.
5. Execute real bounded k6 and at least three passing comparable trials each for
   fixed capacity, API HPA and worker KEDA. Reconcile every job and report all
   declared performance measures; source syntax checks do not satisfy this gate.
6. Deploy the independent second workload and investigate real observations.
   Build independently reviewed held-out cases from actual incidents. Keep real
   model calls disabled until the user changes the current instruction.
7. Review outstanding image vulnerabilities, run actual policy enforcement and
   lifecycle/UI checks, reproduce from a clean committed source, and obtain
   independent final review. Only then evaluate complete A–G acceptance.

The current deliverable is a validated ledger foundation plus additional
experimental source, explicit evidence and a documented continuation path.
Existing M5 persistent data and historical evidence were preserved. Disposable
verification containers were removed; the original cluster is stopped.
