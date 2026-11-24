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
[repository review](docs/history/repository-review-2026-11-16.md). The repository cleanup and local verification baseline has passed;
[verification results](docs/engineering/verification.md) record the actual checks and limits
on a separate branch;
see [cloud readiness](docs/cloud/readiness.md). The Python image security issue is
fixed and all four final images scanned clean; [details](docs/engineering/container-security.md).
AI remains disabled. AWS acceptance still requires the
owner-run deployment and teardown. No AWS resources have been provisioned here.

The NVIDIA advisory integration passed the frozen 42-case development qualification
on 24 November 2026: ten runtime cases and 32 broader evidence-contract cases.
All answers passed mechanical checks and the frozen decision labels; independent
review found no material unsupported explanation or unsafe recommendation.
Runtime AI remains disabled; this evaluation does not activate it or establish
production reliability on unseen incidents. Cause/action disagreements are
rejected by deterministic policy, and model output never authorizes recovery.

Evidence paths come from the actual request. Broad wire citations use sparse
true-only selections, requiring at least one citation for a positive finding
and at most six. They decode losslessly to the unchanged public list; invalid
answers are rejected rather than repaired. Explicit units, freshness, thresholds,
missing-value semantics and conservative abstention are part of the contract.
The final source-only reproduction passed 550 tests and 21 subtests, 39 demo
tests and 46 web tests. Its 36 skipped SQL cases passed separately against
disposable PostgreSQL. Lint, formatting, production build and infrastructure
checks passed; see the [release closeout](docs/engineering/verification.md#pre-cloud-release-closeout--24-november-2026). Gemini/Groq execution
commands and local credentials are retired; their historical failures remain
preserved. See the [evaluation decision](docs/engineering/advisory-evaluation.md).
The updated source was built into local release images and tested. No registry
publication or Kubernetes/AWS deployment has occurred.

## Architecture

| Component | Responsibility |
|---|---|
| `apps/control-plane/` | Authenticated API, durable ledger, investigation, restricted action and independent verification processes |
| `apps/demo-workload/` | Independent API, PostgreSQL job state, Redis Streams dispatcher and fenced worker |
| `apps/web/` | React and TypeScript operator console, operational cards and read-only trial evidence |
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
- [Trial execution](docs/operations/local-trials.md) and [verification](docs/operations/reliability-verification.md)
- [Scenario catalog](docs/operations/scenario-catalog.md)
- [Observability verification](docs/operations/observability-verification.md)
- [Worker shutdown](docs/operations/worker-shutdown.md)

The original forest and porcelain UI palette is retained. Capacity reservations
are configured requests, not measured usage. Stale or unavailable observations
are shown explicitly.

## Cloud and evidence

Cloud [implementation and runtime guides](docs/cloud/readiness.md) distinguish
local validation from AWS acceptance. The owner applies reviewed saved Terraform
plans only after pre-cloud checks and fresh account/cost approval. Publication and
model requests stay behind their separate approval gates.

Historical acceptance, security findings, failed attempts and integration notes
are retained in [docs/history](docs/history/README.md). Old evidence is never
presented as a newly executed test. Ignored `.runtime` directories retain raw
receipts, source/image manifests and cluster identity. Compatibility names in
persisted SQL, environment variables, Helm values and API routes are documented
rather than renamed destructively.
