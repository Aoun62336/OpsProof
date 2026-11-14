# OpsProof

**Cloud Reliability Verification & Safe Operations Platform**

OpsProof is a reproducible engineering platform for investigating
application incidents, evaluating controlled operational actions,
verifying recovery, and measuring reliability outcomes.

## Project Status

Milestones 1-4 have a working source implementation and recorded local
acceptance tests. The post-M4 safety-closure changes have also passed the real
Python 3.14 suites, Docker recovery/shutdown drills and application-log telemetry
checks. See
[the current closure report](docs/operations/M4_ACCEPTANCE_CLOSURE_2026-11-07.md)
and [the preceding local validation](docs/operations/M4_LOCAL_VALIDATION_REPORT.md).

Milestone 5 has recorded local acceptance, with the historical progressive-delivery
correlation caveat retained in its report. M6 now has a validated durable-ledger
source foundation, an authenticated read-only console and experimental local
scenario adapters. Full M6 acceptance remains incomplete: live fault/capacity/reuse
verification is blocked by host memory, and external model calls are disabled by
the owner. M7 cloud verification and publication remain outstanding.

See [the M6 execution plan](docs/engineering/M6_EXECUTION_PLAN_2026-11-14.md)
and [the current M6 acceptance report](docs/experiments/M6_ACCEPTANCE_REPORT_2026-11-14.md).
No production deployment, measured M6 reliability improvement, live model
qualification or AWS EKS verification is claimed.

## Architecture

The implemented foundation and planned extensions include:

- React and TypeScript operations console
- FastAPI control service
- Evidence collection and analysis worker
- Restricted experiment and action worker
- PostgreSQL and isolated Redis control-plane services
- Independent demonstration workload
- Kubernetes, GitOps, and observability integrations
- Reproducible reliability experiments
- AI-assisted incident investigation
- Evidence-backed reporting

## Execution Environments

- Local development and controlled experiments
- Temporary Amazon EKS for final cloud verification
- Public read-only replay of recorded experiments

## Engineering Principles

- Evidence-based verification
- Least-privilege access
- Secure software delivery
- Infrastructure as Code
- Reproducible environments
- Clear service boundaries
- Measured performance and reliability
- Transparent reporting of limitations

## Documentation

Architecture, installation, operational procedures, experiments,
security decisions, and verified results will be documented
throughout development.

## Local Control-Plane Development

The project contains two independently deployed applications:

1. The demonstration workload.
2. The OpsProof control plane.

The control plane uses a dedicated PostgreSQL database and Redis
instance. Only the demonstration API is connected through a shared
Docker integration network.

### Start the integration environment

Create the documented local `.env` credentials first.

```bash
docker network inspect opsproof-integration >/dev/null 2>&1 \
  || docker network create opsproof-integration

docker compose -f compose.yaml \
  -f compose.target-integration.yaml up -d --build --wait

docker compose -f compose.control.yaml up -d --build --wait
```

### Verify the implementation

```bash
uv run --project apps/control-plane \
  pytest apps/control-plane/tests -v

uv run --no-project --python 3.14 \
  python scripts/verify_control.py
```

### Local endpoints

- Demo application: http://127.0.0.1:8088/docs
- Control API: http://127.0.0.1:8090/docs

The management API requires the locally configured API key.

### Stop the environments

```bash
docker compose -f compose.control.yaml down

docker compose -f compose.yaml \
  -f compose.target-integration.yaml down
```

Named volumes are retained by normal shutdown.

The current control plane is a development implementation.
It must not be exposed publicly or connected to uncontrolled
production workloads.

---

## Troubleshooting and Failure Investigation

If the integration fails, use the appropriate targeted checks rather than rebuilding everything.

| Symptom | Likely area | What to inspect |
|---|---|---|
| Dependency lock fails | Python package compatibility | uv resolver message |
| Migration fails | Control PostgreSQL connection or schema | `control-migrate` logs |
| API returns 503 | PostgreSQL or Redis readiness | Control service logs |
| API returns 401 | Missing or incorrect management key | Local `.env` and request header |
| Experiment remains `queued` | Dispatcher or action queue | Outbox and dispatcher logs |
| Experiment remains `running` | Action worker or demo API | Action-worker logs and demo readiness |
| Experiment remains `verifying` | Evidence worker | Evidence-worker logs and Redis pending messages |
| Experiment becomes `failed` | Execution or verification assertion | Experiment events and worker logs |
| Container is killed unexpectedly | Resource pressure | `docker stats`, service state and exit code |
| Control worker cannot reach demo | External network or service alias | Network membership and DNS |

### Useful Diagnostic Commands

Inspect all control-plane services:
```bash
docker compose -f compose.control.yaml ps -a
```

Inspect the dispatcher:
```bash
docker compose -f compose.control.yaml \
  logs --tail=100 control-dispatcher
```

Inspect action execution:
```bash
docker compose -f compose.control.yaml \
  logs --tail=100 action-worker
```

Inspect evidence verification:
```bash
docker compose -f compose.control.yaml \
  logs --tail=100 evidence-worker
```

Inspect the API:
```bash
docker compose -f compose.control.yaml \
  logs --tail=100 control-api
```

Inspect the database migration:
```bash
docker compose -f compose.control.yaml \
  logs --tail=100 control-migrate
```

Check the integration network:
```bash
docker network inspect opsproof-integration \
  --format '{{range .Containers}}{{println .Name}}{{end}}'
```

The integration network should contain the demo API and the workers that need to contact it. It should not contain either PostgreSQL or Redis database service.

### If an experiment is stuck

First inspect its recorded status and worker logs. Do not immediately delete the database, Redis volumes, or messages. They may contain the information needed to diagnose the failure.

In particular, an unacknowledged Redis message is not automatically evidence of a bug. It may be a message awaiting recovery after an interrupted consumer. Investigate the underlying state before resetting anything.

## Milestone 5 foundation

Milestone 5 local runtime acceptance has passed, including GitOps, progressive delivery,
measured autoscaling and restricted approved Kubernetes recovery. Publication and
hosted CI remain unperformed under the instruction to keep changes local.

- [Latest acceptance report](docs/operations/M5_ACCEPTANCE_REPORT_2026-11-09.md)
- [Local operating runbook](docs/operations/M5_LOCAL_RUNBOOK.md)
- Source checks: `python scripts/m5/validate_source.py` (Python, PyYAML, uv, Node, Helm required).
- Upstream Gateway check: `python scripts/m5/validate_gateway.py`.
- Resource gate: `python scripts/m5/preflight.py`.
- Local bootstrap: `python scripts/m5/bootstrap.py`.
- Foundation deployment: `python scripts/m5/deploy_foundation.py`.
- Exact-job Kubernetes smoke: `python scripts/m5/smoke.py`.

The scripts use an isolated local kubeconfig; they never target the default AWS context.
Do not delete PVCs or the cluster as an automatic cleanup step.
