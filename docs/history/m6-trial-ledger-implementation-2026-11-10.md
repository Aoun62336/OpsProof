> Historical record. Commands, paths and results below describe the recorded revision. See [the current repository guide](../../README.md) for maintained commands and status.

# OpsProof M6 implementation checkpoint: durable trial ledger candidate

> This is the historical reviewed-candidate description supplied on 10 November.
> The applied implementation and additional dispatch/concurrency safeguards are
> documented in the [14 November report](m6-acceptance-report-2026-11-14.md).

**Source baseline:** commit `38b3a46`, `feature/opsproof-m6-m7-integration`.
**Acceptance:** NOT ACCEPTED as complete M6. This document describes new source to test, not recorded deployment evidence.

## What was actually implemented

- Additive Alembic revision `0006` with M6 trial, event, outbox, retained target fence, and artifact tables. No M4/M5 table mutation.
- Fixed six-scenario target catalog under the control-plane wheel (the existing `scripts.m6` catalog remains available offline and must be checked for alignment).
- Authenticated, opt-in M6 trial API with create/list/detail/events, gated arming, and operator abort.
- PostgreSQL idempotency fingerprint, an active-target unique index, immutable audit events and short-lived arming intent.
- A separately deployed, non-mutating `trial` worker role for source-contract preflight bookkeeping and expiry of un-injected approvals.
- Fenced service-only methods for recording an injection receipt, transitions, artifact identities, independent/cleanup proof and uncertain status. They are NOT wired to an actuator or public routes.
- Read-only M6 trial list/timeline in the existing React UI, using existing CSS and auth helper.
- Unit/contract/negative security tests and an opt-in real PostgreSQL integration test.
- M6 Helm switches default to `false` for API, arming and dedicated worker; no projected Kubernetes service-account token on the trial worker.

## Explicit limitations

1. A recorded `preflight` phase currently means **source-contract preflight only**, not a successful live k3d preflight. Do not arm for real faults on that basis.
2. There is no six-scenario actuator engine in this candidate. The M6 API cannot run a Kubernetes command or mark a trial succeeded.
3. Source-verification of submitted hash references does not authenticate the actual evidence producer; future restricted evidence collection and receipt/provenance are required.
4. PostgreSQL model and concurrency tests in a real disposable DB, plus local Helm render and React builds, remain to be performed in the user's environment.
5. M6's A-G deliverable, including six real faults, benchmark repetitions, model qualification, second-workload proof and independent acceptance, remains incomplete.
6. M5 Gate 5 progressive-delivery correlation status still requires explicit final report reconciliation. M7 cloud provisioning and EKS are deliberately deferred.

## Safety and rollback

Do not enable `m6.armEnabled` or grant Kubernetes authority to this trial worker. Keep the cluster stopped until the source, DB and deployment contracts pass. If source tests fail, preserve the output and restore from the local baseline branch or fix only the relevant files. Do not use Alembic downgrade on the existing M5 control database or remove PVCs.

## Evidence status

- 50 pre-existing M6 offline tests passed in the source audit container (Python 3.13, pure Python tests only).
- 17 pre-existing M5 scripts passed, plus five subtests.
- 12 pre-existing M7 offline tests passed.
- Seven new trial-state safety functions passed under a stubbed database module.
- New Python AST syntax parsed; this is not Python 3.14 Ruff, actual PostgreSQL, Helm or frontend build acceptance.
- Real PostgreSQL, API/auth regression, Helm rendering and frontend verification are **NOT RUN** in the source-audit container. Use the `M6_VALIDATION_AND_APPLICATION_GUIDE.md` before accepting the candidate.
