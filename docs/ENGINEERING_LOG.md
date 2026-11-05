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
