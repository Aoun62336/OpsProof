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
