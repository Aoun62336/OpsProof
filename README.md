# OpsProof

OpsProof investigates incidents, runs controlled reliability trials, and verifies
recovery for explicitly managed Kubernetes workloads. Its authenticated operator
console shows operational evidence and recovery outcomes.

## Getting started

- [Run OpsProof locally](docs/operations/local-platform.md) using the local Kubernetes guide.
- [Read the system design](docs/architecture/system.md) for service boundaries and recovery flow.
- [Prepare an AWS deployment](docs/cloud/owner-deployment-session.md) using the owner runbook.

## Architecture

| Component | Responsibility |
|---|---|
| `apps/control-plane/` | Authenticated API, durable ledger, investigation, restricted action and independent verification processes |
| `apps/demo-workload/` | Independent API, PostgreSQL job state, Redis Streams dispatcher and fenced worker |
| `apps/web/` | React and TypeScript operator console, operational cards and read-only trial evidence |
| `apps/edge-proof/` | Isolated, read-only public evidence viewer |
| `infra/helm/` | Application and dependency deployment profiles |
| `infra/k8s/` | Namespaces, network boundaries, recovery RBAC and local platform settings |
| `infra/terraform/` | Separate state bootstrap, private platform and read-only public edge roots; disabled by default |
| `observability/` | Prometheus, Grafana, Alertmanager, OpenTelemetry, Loki and Tempo configuration |
| `scripts/platform/` | Local bootstrap, GitOps, gateway, deployment and platform verification |
| `scripts/reliability/` | Bounded trials, evidence, source/image/database verification and capacity/cost analysis |
| `scripts/cloud/` | Cloud preparation, release, credential/bootstrap, inventory, validation and sanitized replay tools |
| `benchmarks/` | Versioned AI fixtures and bounded k6 load definitions |

The demo and control services have separate databases and queues. The API does
not hold Kubernetes mutation credentials. Recovery uses explicit approval,
restricted workers, durable ownership and independently verified postconditions.
See [repository structure and compatibility](docs/engineering/repository-structure.md).

## Development and verification

Use Python 3.14, the project's pinned uv version, Node.js 24 and the committed
Python and npm lockfiles. Each Python application builds independently.

```sh
uv sync --project apps/control-plane --locked
uv sync --project apps/demo-workload --locked
npm --prefix apps/web ci

uv run --project apps/control-plane --locked python -m pytest apps/control-plane/tests scripts/platform/tests scripts/reliability/tests scripts/cloud/tests -q
uv run --project apps/demo-workload --locked python -m pytest apps/demo-workload/tests -q
uv run --project apps/control-plane --locked ruff check apps/control-plane
uv run --project apps/demo-workload --locked ruff check apps/demo-workload
uv run --project apps/control-plane --locked ruff check --config apps/control-plane/pyproject.toml scripts conftest.py
npm --prefix apps/web run lint
npm --prefix apps/web run test
npm --prefix apps/web run build
```

On Windows, the aggregated source gate is
`uv run --project apps/control-plane --locked python -m scripts.reliability.validate_source`.
It records commands, exit codes and source hashes in ignored local runtime evidence.
The pinned native secret scanner must already be installed as documented by the
platform security tooling. CI runs its Linux counterpart.

SQL tests intentionally skip without an explicitly disposable database. Run
`uv run --project apps/control-plane --locked python -m scripts.reliability.validate_postgres --browser`
to create an owned local PostgreSQL container, test migration preservation,
concurrency, permissions and authenticated browser access, then remove that
container. This does not start Kubernetes or use provider keys.

## Local operation

Start only the components needed for the current task. Keep `.env`, API keys,
kubeconfigs, database state and raw operational evidence private.

- [Local platform](docs/operations/local-platform.md) and [runbook](docs/operations/local-runbook.md)
- [GitOps ownership](docs/operations/gitops.md) and [gateway](docs/operations/gateway.md)
- [Investigation and recovery](docs/operations/investigation-and-recovery.md)
- [Reliability trials and verification](docs/operations/reliability-verification.md)
- [Scenario catalog](docs/operations/scenario-catalog.md)
- [Monitoring and alerting](docs/operations/observability-verification.md)
- [Worker shutdown](docs/operations/worker-shutdown.md)

## Deployment status

AWS deployment and teardown verification are pending. See
[cloud readiness](docs/cloud/readiness.md) for prerequisites and acceptance checks.
Runtime AI is disabled. See the [advisory decision](docs/engineering/advisory-evaluation.md)
for qualification details.
