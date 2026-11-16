> Historical record. Commands, paths and results below describe the recorded revision. See [the current repository guide](../../README.md) for maintained commands and status.

# OpsProof Engineering Log

## Project Baseline

- Project: OpsProof
- Specification: v1.0
- Architecture: Compact service-oriented control plane
- Development: Windows 11, Antigravity IDE, Git Bash
- Primary execution environment: Local
- Cloud verification: Temporary Amazon EKS
- Evidence policy: No unverified claims or invented metrics

## 2026-11-03: Development Foundation

### Objective

Establish the development environment and repository
before implementing application services.

### Engineering Decisions

- Use supported, compatible tool versions.
- Separate the control plane from target workloads.
- Use independent evidence and restricted action workers.
- Develop locally before provisioning AWS infrastructure.
- Apply least-privilege security principles.
- Preserve reproducible experimental evidence.

### Verification

Pending local execution and review.

### Known Risks

- Local memory constraints
- Dependency and integration compatibility
- AI diagnosis accuracy
- AWS credit eligibility and deployment costs

### Next Work

Validate the development foundation and implement
the first controlled workload and incident experiment.

---

## 2026-11-04: Independent Control Plane

### Objective

Implement an independent OpsProof control plane that can create,
execute, verify, and record bounded reliability experiments
against the previously implemented demonstration workload.

### Architecture

- Authenticated FastAPI control API
- Dedicated PostgreSQL experiment and audit storage
- Separate Redis Streams work queue
- PostgreSQL transactional outbox and dispatcher
- Restricted action worker
- Independent evidence verification worker
- Isolated demonstration and control-plane persistence
- Explicit Docker integration network
- Versioned Alembic database migrations

### Engineering Decisions

1. Separate the control plane from the application under test.
2. Use a shared Python package with independently running processes.
3. Keep PostgreSQL authoritative for experiment state.
4. Use Redis Streams for at-least-once work delivery.
5. Apply deterministic idempotency keys to sandbox job submissions.
6. Prevent arbitrary shell, Docker, or Kubernetes execution.
7. Require independent verification before reporting experiment success.
8. Bind the local control API to loopback and require an API key.
9. Keep database and Redis ports unpublished.
10. Preserve raw evidence and unsuccessful experiment outcomes.

### First Supported Experiment

Scenario: queue-burst

Behavior:
- Accept a bounded experiment request.
- Record the experiment durably.
- Publish work through the transactional outbox.
- Submit jobs through the demonstration API.
- Verify completed jobs independently.
- Preserve an experiment event timeline.

This scenario validates the initial control-plane integration.
It does not establish automatic incident recovery or AI diagnosis.

### Verification

Implementation supplied for local execution.

Pending:
- Python dependency resolution
- Ruff and unit tests
- Docker image build
- Database migrations
- End-to-end experiment verification
- GitHub Actions integration run

Do not mark these checks as passed until observed.

### Known Limitations

- Single action-worker and evidence-worker execution model
- Initial local API-key authentication
- Only the queue-burst scenario is available
- Redis delivery remains at least once
- Production-grade distributed worker concurrency is not yet established
- AI, Kubernetes runbooks, incident correlation, and the operations UI
  remain part of subsequent locked milestones

### Next Work

Verify the independent control-plane implementation and continue
with the professional operations UI, telemetry, and incident model.


## 2026-11-05: Forest & Porcelain redesign

Implemented Milestone.txt UI parts A?L in order: fonts, temporary OP identity, semantic states, desktop/mobile shell, real-data pages, modular CSS, protected logout, browser tests and design documentation. Experiment-detail source, workload and worker semantics were preserved.

Validation: control Ruff and 17 tests passed; frontend lint, 3 unit tests and build passed; supplied five Playwright tests passed after correcting login-hint contrast and an ambiguous link selector. A supplemental real-browser run verified all four required viewport sizes, real experiment creation, event history, JSON export, CSRF rejection and logout. The logout check exposed an existing cache-clear issue; removing non-auth queries instead preserves the session observer and returns the login screen. A browser regression test now covers this.

Integration: `scripts/verify_control.py` passed all six assertions. Docker Desktop needed startup and the existing integration network needed recreation. No volumes were deleted. Local evidence: `.runtime/redesign/` and `.runtime/control-first-run.json`. No cloud or GitHub Actions run is claimed.

---

## 2026-11-05: Observability and Incident Detection

### Objective

Introduce real telemetry collection, automated alert evaluation,
durable incident registration, and evidence-backed local
fault-detection experiments.

### Architecture

- Prometheus for application and workload metrics
- Alertmanager for alert notification
- OpenTelemetry Collector for logs and traces
- Loki for application logs
- Tempo for request traces
- Grafana for investigation and dashboarding
- Authenticated incident ingestion in the control plane
- PostgreSQL incident state and transition history
- Forest & Porcelain incident registry UI

### Engineering Decisions

- Preserve independent application and control-plane persistence.
- Use an explicit telemetry network.
- Keep monitoring services local and separately deployable.
- Do not provide Docker socket access to monitoring services.
- Use bounded Prometheus labels.
- Avoid false healthy metrics when dependencies are unavailable.
- Authenticate alert ingestion with a separate credential.
- Deduplicate repeated alert notifications.
- Preserve firing and resolved state transitions.
- Separate alert resolution from verified workload recovery.
- Measure actual fault-detection and restoration delays.
- Use fixed, reviewed component versions.

### Verification

Executed:
- Backend contract tests pass (12/12).
- Backend deduplication & webhook tests pass.
- Frontend unit tests pass (4/4, including honest empty-state).
- Frontend production build succeeds (Vite + TypeScript).
- Frontend lint (oxlint) clean with 0 warnings/errors.
- Control plane and demo workload lint (Ruff) clean with 0 warnings/errors.
- Observability and telemetry Compose files syntax-validated.
- Prometheus configuration and alert rules configured.

### Limitations

- Local Compose environment, not production traffic.
- No EKS deployment in this work package.
- No production availability SLO claim.
- Distributed trace propagation across Redis Streams
  requires separate verification.
- Full Kubernetes incident correlation remains pending.
- AI diagnosis is not yet evaluated.
- Alert delivery alone is not automated remediation.

## 2026-11-05: Milestone 4, AI Investigation and Safe Recovery

### Objective

Introduce evidence-driven incident investigation,
a deterministic diagnosis baseline, optional AI
evaluation, and controlled operator-approved
demo-workload recovery.

### Architecture

- Existing authenticated FastAPI control API
- Independent evidence and action workers
- PostgreSQL investigation and recovery state
- PostgreSQL recovery audit events
- Existing Redis Streams experiment pipeline
- Separate durable recovery requests
- Bounded demo-worker hold
- Fixed, idempotent demo-worker resume actuator
- Deterministic diagnosis and policy checks
- Optional structured-output AI evaluation
- Forest & Porcelain investigation interface

### Safety Decisions

- No arbitrary shell execution
- No Docker socket access
- No arbitrary Kubernetes actions
- No AI-authorized recovery
- No unrestricted target selection
- Recovery disabled by default
- AI disabled by default
- Separate inspection and recovery credentials
- Explicit operator approval
- Short-lived evidence and approval validity
- Revalidation before execution
- Idempotent action handling
- Independent post-action verification
- Indeterminate outcome for uncertain results

### Engineering Implementation

- Added migration 0004
- Added investigation persistence and API
- Added deterministic diagnosis rules
- Added bounded evidence snapshots
- Added optional model provider adapter
- Added recovery request lifecycle
- Added restricted recovery execution
- Added independent recovery verification
- Added worker hold/resume controls
- Added investigation UI and API client support
- Extended unit and security tests
- Extended CI authentication checks
- Added operational runbook and results template

### Verification

Local execution completed on 2026-11-06: control lint/format and 67 tests passed;
demo lint/format and 18 tests passed; web lint, 4 tests, TypeScript/Vite build and
8 browser tests passed. Migration 0004 is applied. The original experiment flow
passed before and after the real Prometheus/Alertmanager recovery trial.

Recovery b7c6ca3e-66d6-4356-9be1-91bbdd9fc198 succeeded after one actuator attempt,
independent verification of five exact jobs, experiment success, hold removal and
alert resolution. Live rejection, stale approval, expiry, idempotency, invalid
credentials, CSRF and disabled-feature checks also passed. AI remained disabled.
Both runtime flags were restored to false after the drill.

The full telemetry stack remains blocked by the existing collector image
otel/opentelemetry-collector-contrib:0.164.1 (no such manifest). A pre-existing shell
footer contrast defect was recorded, without unrelated UI changes. The existing Tempo config also rejects its compactor field under the pinned
3.1.1 image. Human populated UI review and remote CI remain pending. See the M4 runbook and trial results for
reconstruction choices, exact commands, measurements and acceptance boundaries.

Record the actual results for:

- Python lint and formatting
- Python unit tests
- Browser tests and accessibility checks
- Existing experiment integration
- Incident detection
- Diagnosis evidence
- Approval rejection and expiry
- Recovery execution
- Idempotency handling
- Exact-job verification
- Alert resolution
- Audit history
- Resource consumption
- AI comparison, if enabled

### Known Limitations

- Local demonstration workload only
- Synthetic bounded worker pause
- No arbitrary process restart
- No production traffic
- No two-person authorization
- No production MTTR claim
- No automatic generalized rollback
- Small curated AI benchmark
- AI disabled unless explicitly configured
- Kubernetes and GitOps remediation planned later

### Completion Criteria

Milestone 4 is complete only when the required
security, regression, runtime and recovery checks
have passed and the evidence is recorded.

## 2026-11-06: Authorized telemetry and accessibility corrections

Resolved the three issues recorded above without changing the deployment design:
pinned the verified Collector 0.164.0 manifest digest, used Tempo 3.1.1's exact
`backend_worker.compaction.block_retention` schema with the original 24h value,
and reused the existing accessible ink-soft color for the footer. Corrected the
initial top-level compaction recommendation after the actual 3.1.1 binary rejected
it; latest documentation must not substitute for version-specific validation.

Collector and Tempo native validation passed, and all six monitoring services ran
with zero restarts. A real instrumented demo trace and marked synthetic log were
retrieved from their backends and through authenticated Grafana datasource queries.
Added a reproducible standard-library verification script and native configuration
checks to the existing observability CI workflow. Restored full-page axe scanning
and added a mobile scan; all eight browser tests, four web unit tests, lint/build,
original workload regression and authentication smoke checks passed.

See the updated M4 runbook and trial report for commands, exact artifact digest,
version-specific sources and evidence. Remote CI, human populated UI review and
long-duration retention testing are not claimed as performed.

## 2026-11-07: Cooperative worker termination and local acceptance

Fixed the five background roles that previously ignored SIGTERM as container PID 1.
Signal handlers request cooperative stop; dispatchers finish their outbox transaction,
the demo worker finishes its current bounded job, and interrupted control work stays
durable and unacknowledged for retry. Long read-only/submission loops use safe
checkpoints that bypass business-failure handlers. The evidence review thread is
joined before Redis and PostgreSQL resources close. Compose now allows 30 seconds
for normal worker shutdown. APIs, approval rules, persistent data and credentials
are unchanged by the shutdown fix.

Added signal, acknowledgement, action interruption and thread-join regression tests,
and scripts/verify_shutdown.py for the real container stop/restart drill. Final unit
suites passed: 75 control, 23 demo; web lint/build, 4 unit tests and 8 browser tests
passed. Live active demo/evidence/action shutdowns exited 0 and resumed their exact
jobs with one attempt each. Fresh browser-driven recovery and independent proof,
telemetry delivery, authentication checks and deterministic benchmark passed.

See docs/operations/M4_LOCAL_VALIDATION_REPORT.md for exact trials, cleanup results,
and remaining remote-CI/paid-provider/long-duration scope. The old SIGINT workaround
is superseded by docs/operations/WORKER_SHUTDOWN.md.
