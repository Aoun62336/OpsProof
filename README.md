# OpsProof

Cloud reliability verification and safe operations.

OpsProof investigates incidents, records controlled operational trials and verifies
recovery against independent evidence. It is an engineering demonstration for
explicitly managed workloads, with an authenticated operator console.

## Current status

The local system has recorded acceptance for six fault scenarios, nine accepted
capacity trials across fixed replicas, HPA and KEDA, exact-job k6 verification,
second-workload observations, durable trial records and cleanup. See the
[local acceptance report](docs/history/m6-acceptance-report-2026-11-14.md) and
[operational UI and offline evidence report](docs/history/m6-workspace-ui-and-offline-evidence-2026-11-15.md).
Those are historical results for their recorded source and image identities.

The current repository standardization and checks are described in the
[repository review](docs/engineering/repository-review.md). Cloud preparation
exists, but M7 implementation and AWS acceptance await owner approval. No AWS
resources have been provisioned by this review.

AI comparison is optional and disabled. The earlier Groq and Gemini fixture
comparison failed qualification for both candidates. Metric units, freshness,
mechanical evidence-path validation and a four-case offline held-out set are
implemented. Fresh external candidate comparison is deferred and requires
separate authorization. Model output never authorizes recovery.

## Architecture

| Component | Responsibility |
|---|---|
| `apps/control-plane/` | Authenticated API, durable ledger, investigation, restricted action and independent verification processes |
| `apps/demo-workload/` | Independent API, PostgreSQL job state, Redis Streams dispatcher and fenced worker |
| `apps/web/` | React and TypeScript operator console, operational cards and read-only trial evidence |
| `infra/helm/` | Application and dependency deployment profiles |
| `infra/k8s/` | Namespaces, network boundaries, recovery RBAC and local platform settings |
| `infra/terraform/` | Existing temporary AWS infrastructure preparation, disabled by default |
| `observability/` | Prometheus, Grafana, Alertmanager, OpenTelemetry, Loki and Tempo configuration |
| `scripts/platform/` | Local bootstrap, GitOps, gateway, deployment and platform verification |
| `scripts/reliability/` | Bounded trials, evidence, source/image/database verification and capacity/cost analysis |
| `scripts/cloud/` | Existing cost guard, read-only inventory and sanitized static replay helpers |
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
- [Trial execution](docs/operations/local-trials.md) and [verification](docs/operations/reliability-verification.md)
- [Scenario catalog](docs/operations/scenario-catalog.md)
- [Observability verification](docs/operations/observability-verification.md)
- [Worker shutdown](docs/operations/worker-shutdown.md)

The original forest and porcelain UI palette is retained. Capacity reservations
are configured requests, not measured usage. Stale or unavailable observations
are shown explicitly.

## Cloud and evidence

Cloud runbooks under `docs/cloud/` describe existing preparation. They do not
represent a verified AWS release. M7 requires a separate reviewed implementation
and an owner-run Terraform apply after local validation and cost approval.

Historical acceptance, security findings, failed attempts and integration notes
are retained in [docs/history](docs/history/README.md). Old evidence is never
presented as a newly executed test. Ignored `.runtime` directories retain raw
receipts, source/image manifests and cluster identity. Compatibility names in
persisted SQL, environment variables, Helm values and API routes are documented
rather than renamed destructively.
