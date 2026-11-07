# OpsProof Milestone 4
## AI Investigation and Controlled Recovery

Status: Local recovery, telemetry delivery and full-page automated accessibility verified on 2026-11-06; human UI acceptance and remote CI pending

## Objective

Investigate detected incidents using bounded real evidence,
compare deterministic and optional AI diagnoses, require
explicit authorization for supported recovery actions,
and independently verify recorded outcomes.

## Supported Scope

- Local Docker Compose environment
- Demo queue-burst experiments
- Prometheus/Alertmanager incident detection
- PostgreSQL-backed incident and recovery records
- Deterministic diagnosis
- Optional, bounded AI evaluation
- Operator-approved demo-worker resume
- Independent job and experiment verification

The recovery actuator does not control Docker, Kubernetes,
cloud accounts or arbitrary processes.

## Service Responsibilities

### Control API

- Authenticates the operator
- Creates investigations
- Records recovery proposals and approvals
- Enforces CSRF for browser mutations
- Exposes read-only recovery audit records
- Does not receive the demo recovery credential

### Evidence Worker

- Collects bounded evidence
- Runs deterministic diagnosis
- Performs optional AI evaluation
- Verifies exact jobs and recovery outcomes
- Does not receive the recovery actuator credential

### Action Worker

- Claims approved durable recovery requests
- Revalidates policy-relevant live conditions
- Uses a fixed allowlisted actuator endpoint
- Records the actuator response
- Does not perform independent outcome verification

### Demo Workload

- Supports a temporary Redis-backed worker hold
- Provides an authenticated inspection endpoint
- Provides an authenticated idempotent resume endpoint
- Automatically expires abandoned synthetic holds

## Security Model

- Recovery disabled by default
- AI disabled by default
- Separate inspection and recovery credentials
- No Docker socket mounted into recovery containers
- No arbitrary URLs or shell commands accepted
- No model-directed tool execution
- Typed, bounded API requests
- PostgreSQL-backed state transitions
- Fixed operation allowlist
- Expiring approvals
- Idempotency keys
- Independent evidence verification
- Explicit indeterminate state

## Recovery Preconditions

All conditions are required:

1. Supported queue-backlog alert
2. Incident remains firing
3. Linked queue-burst experiment exists
4. Experiment remains verifying
5. Prometheus scrape evidence is recent
6. Demo API is ready
7. Demo worker hold is confirmed
8. Hold has sufficient remaining TTL
9. Queued jobs exist
10. Exact linked job identifiers are recorded
11. Deterministic diagnosis permits the action
12. Evidence is within its freshness window
13. Operator explicitly approves the action
14. Recovery kill switch is enabled
15. Action worker independently revalidates eligibility

AI output cannot override these conditions.

## Successful Verification

Success requires:

- Acknowledged actuator operation
- Worker hold no longer active
- Every linked job completed
- Linked experiment succeeded
- Relevant alert resolved

Incomplete observations are not success.

## Failure Handling

- Rejected: operator refused the action
- Expired: approval validity ended before execution
- Failed: a known execution or verification failure
- Indeterminate: action effect or recovery evidence
  could not be reliably established

Do not automatically repeat a destructive or
state-changing action after an uncertain result.

The demo-worker resume is an idempotent operation.
It is not a generalized rollback framework.

## Manual Fault Drill

1. Verify the original control and demo workloads.
2. Verify Prometheus and Alertmanager integration.
3. Confirm worker and queue are idle.
4. Enable the local recovery feature explicitly.
5. Create the bounded demo-worker hold.
6. Submit a five-job queue-burst experiment.
7. Observe queued jobs and a firing backlog alert.
8. Link the experiment to a new investigation.
9. Review the deterministic diagnosis.
10. Propose the supported recovery action.
11. Approve using the exact confirmation phrase.
12. Observe the action-worker acknowledgment.
13. Verify linked jobs and experiment results.
14. Verify the alert lifecycle.
15. Inspect PostgreSQL recovery and audit records.
16. Record observed timestamps and failures.
17. Disable the recovery feature.
18. Confirm existing experiment regression tests pass.

## Evidence to Preserve

- Git commit and source revision
- Container image versions
- Relevant Compose configuration names
- Experiment identifier
- Incident fingerprint
- Investigation identifier
- Recovery identifier
- Fault injection timestamp
- First firing event timestamp
- Approval event timestamp
- Action acknowledgment timestamp
- Verification completion timestamp
- Linked job outcomes
- Experiment outcome
- Incident resolution outcome
- Unit and integration test summaries
- Resource usage measurements
- Any manually applied intervention
- Test limitations

Do not publish raw credentials, authentication cookies
or private environment files.

## AI Benchmark

Initial benchmark:

- Deterministic baseline
- Ten curated synthetic cases
- Explicit expected cause and action labels
- Optional paid provider comparisons
- Maximum two cases per paid invocation initially

Evaluation dimensions:

- Cause accuracy
- Action accuracy
- Unsafe action suggestions
- Abstention behavior
- Output validity
- Latency
- Token usage
- Estimated cost

This dataset is not a production accuracy benchmark.

The active policy does not depend on AI correctness.

## Acceptance

Milestone 4 is accepted only after:

- Required tests pass
- The original experiment workflow still works
- A real paused-worker incident is detected
- The diagnosis identifies the confirmed hold
- Unauthorized actions are rejected
- The operator approval is recorded
- The restricted action executes successfully
- Independent verification establishes the outcome
- The incident and recovery history are preserved
- Kill-switch and expiry behavior are checked
- AI and cost claims remain evidence-based
- The working tree and CI checks are reviewed

## Known Limitations

- Local synthetic failure injection
- Single local operator role
- No two-person approval
- No arbitrary service restart
- No Docker or Kubernetes actuator privileges
- No generalized rollback capability
- No production traffic
- No established production MTTR reduction
- Limited initial diagnosis benchmark
- Paid AI optional
- Full Kubernetes/GitOps remediation remains planned
- Final AWS EKS verification remains cost-gated

## Reconstruction record (2026-11-06)

`NextPhase.txt` contains an earlier abandoned outbox proposal followed by the
corrected Steps 1–69. The latter explicitly retain the existing experiment
outbox and use PostgreSQL polling for investigations/recoveries. That is the
implemented design. Existing migrations 0001–0003 and dispatcher behavior remain
unchanged. No dependencies were added.

The Python snippets for the migration, diagnosis, collector, model adapter,
operations API, recovery worker, benchmark, preparation/security/evidence scripts
and tests were incomplete. Their missing bodies were reconstructed around the
documented contracts. The React workspace's missing hooks, evidence selector and
mutation wiring were completed around the supplied JSX. The supplied TypeScript
contracts, API methods and investigation CSS were retained.

| Files | Responsibility |
|---|---|
| `apps/control-plane/alembic/versions/0004_investigations_recoveries.py` | Durable investigation, recovery and append-only application audit records; foreign keys and unique active recovery constraint |
| `diagnosis.py`, `investigation_worker.py` in control `src/opsproof_control` | Typed bounded facts, deterministic policy, fresh Prometheus samples, linked job evidence, durable polling |
| `model_provider.py`, `benchmark.py` | Optional schema-validated Gemini/OpenAI comparison and ten curated cases; no tools or action authority |
| `operations.py`, `api.py`, `config.py` | Authenticated routes, existing session/CSRF enforcement, idempotency, exact approval phrase, feature gates, atomic daily AI request count |
| `recovery_worker.py`, `action.py`, `streams.py`, `evidence.py` | Independent action and verification loops alongside the original experiment pipeline |
| Demo `worker_control.py`, `worker.py`, `api.py`, `config.py` | Bounded Redis hold, worker checks, separate authenticated inspection and fixed resume actuator |
| `compose.demo.recovery.yaml`, `compose.control.recovery.yaml` | Least-privilege credential distribution and default-disabled flags |
| Web `InvestigationPage.tsx`, `App.tsx`, `IncidentsPage.tsx`, `lib/api.ts`, `lib/types.ts`, styles | Existing Forest & Porcelain workspace, navigation, evidence/diagnosis/approval/audit views |
| New Python tests, `scripts/prepare_recovery.py`, `verify_m4_security.py`, `verify_milestone4.py`, control CI workflow | Preparation, unit/security regression, live authentication checks and recorded recovery evidence validation |
| This runbook, `M4_TRIAL_RESULTS.md`, `docs/ENGINEERING_LOG.md` | Operational procedure, reconstruction choices and actual outcomes |

Unspecified values were kept small: evidence age 60 seconds, underlying scrape
age 30 seconds, approval lifetime 120 seconds, verification deadline 120 seconds,
two actuator attempts separated by a 60-second abandoned-work lease, replay marker
TTL one hour. Collection permits at most eight unique experiment job IDs and eight
errors; list queries return at most 50 records and 200 audit events. No paid work
is retried after an uncertain response. Daily AI requests are serialized by a
PostgreSQL transaction lock and capped at 10 by default. These are request limits,
not monetary guarantees. Retry authorization is rechecked on every attempt.

The benchmark retains the supplied linked/unlinked paused-worker cases and fills
the omitted cases with unpaused backlog, unknown hold, empty queue, missing scrape,
unreachable API, unavailable dependency, unsupported alert and missing queue facts.
These authored expectations test policy consistency, not general diagnostic accuracy.

Corrections to incompatible snippets are separate from reconstruction:

- Redis TTL zero or -1 still means a hold exists; it must not be reported cleared.
  Such holds cannot authorize recovery.
- The action worker rechecks current incident/experiment eligibility and expiry
  on retries, as required by the later correction in Step 43.
- Exact-job verification also requires hold removal, experiment success and a
  post-approval resolved incident, as required by Step 35.
- Demo telemetry Compose explicitly retains the default network for dispatcher
  and worker. Without it the combined stack cannot resolve its Redis/database.
- The supplied SQL audit join used nonexistent `e.fingerprint`; the correct
  existing column is `e.incident_fingerprint`.
- Existing `httpx2`, Python 3.14 and the existing authentication dependencies are
  used rather than introducing replacement libraries.

## How the system runs

1. The authenticated control API saves a queue-burst experiment and its original
   outbox transaction. The dispatcher delivers it through Redis Streams.
2. The action worker submits bounded jobs to the demo API. The demo's own database,
   outbox, dispatcher and worker process them. A temporary Redis hold prevents new
   processing until resume or TTL expiry; it does not terminate an in-flight job.
3. Prometheus scrapes queue metrics; Alertmanager sends authenticated firing and
   resolved notifications to the existing incident API.
4. An operator links the experiment to an investigation. The evidence worker polls
   its durable PostgreSQL request, reads readiness, queue counts, authenticated
   hold state and recent Prometheus samples, and records deterministic diagnosis.
5. Optional AI sees sanitized facts only. Its result is displayed separately and
   never authorizes an action. The API/evidence flags and daily request cap apply.
6. A proposal must pass deterministic policy, live incident/experiment checks and
   freshness bounds. The operator supplies the exact phrase before approval.
7. The action worker claims the approved row, checks current authorization again,
   and calls only the fixed demo resume endpoint. Redis Lua atomically removes
   the fixed hold and records the recovery UUID, recognizing safe replays.
8. Acknowledgment advances to `verifying`, not success. The evidence worker checks
   every linked job identity/status, experiment outcome, cleared hold and resolved
   incident. Missing proof reaches `indeterminate`; known failed work reaches
   `failed`. PostgreSQL records every transition and its evidence.

The deployment is the specified single local action/evidence worker arrangement.
It is not a generalized distributed remediation platform. Credentials remain in
ignored local configuration; the control API and evidence worker never receive the
actuator credential. No Docker socket is mounted into these workers.

## Reproducible commands (PowerShell)

Execute from `C:\Users\AOUN\Desktop\OpsProof` unless another directory is stated.
Run each command independently and stop on nonzero exit. `npm.cmd` avoids the
Windows unsigned `npm.ps1` wrapper. `uv --locked` preserves lockfiles. The commands
below consolidate repeated commands in Steps 18–69 without changing their purpose.

```powershell
Set-Location C:\Users\AOUN\Desktop\OpsProof
$env:UV_CACHE_DIR="$PWD/.cache/uv"
$demo=@('-f','compose.yaml','-f','compose.target-integration.yaml','-f','compose.demo.telemetry.yaml','-f','compose.demo.recovery.yaml')
$control=@('-f','compose.control.yaml','-f','compose.control.telemetry.yaml','-f','compose.control.recovery.yaml')
python scripts/prepare_observability.py
python scripts/prepare_recovery.py
docker network inspect opsproof-integration
# Only if the network is absent:
docker network create opsproof-integration
docker network inspect opsproof-telemetry
# Only if the network is absent:
docker network create opsproof-telemetry
docker compose @demo config --quiet
docker compose @control config --quiet
```

Preparation preserves existing keys and creates missing local credentials without
printing them. Quiet Compose validation should exit zero. Missing variables or
networks indicate preparation/configuration problems; never paste resolved Compose
environment output into a public report.

```powershell
uv run --project apps/demo-workload --locked ruff check apps/demo-workload
uv run --project apps/demo-workload --locked ruff format --check apps/demo-workload
uv run --project apps/demo-workload --locked pytest apps/demo-workload/tests -v
uv run --project apps/control-plane --locked ruff check apps/control-plane
uv run --project apps/control-plane --locked ruff format --check apps/control-plane
uv run --project apps/control-plane --locked pytest apps/control-plane/tests -v
Set-Location apps/web
npm.cmd run lint
npm.cmd run test
npm.cmd run build
npm.cmd run test:e2e
Set-Location ../..
```

Lint/format must report no issues, pytest/Vitest no failures, and build must finish
TypeScript checking and Vite bundling. Browser tests require the local API and
operator key in `.env`; inspect skipped tests as well as failures. Investigate the
first assertion/trace, dependency setup or API readiness rather than treating a
successful shell's last command as proof all earlier commands passed. Python has
no separately configured static type-checker; frontend build performs its type check.

```powershell
docker compose -f compose.observability.yaml up -d
docker compose -f compose.observability.yaml ps
docker compose -f compose.observability.yaml logs --tail 100 prometheus alertmanager
docker compose @demo up -d --build --wait
docker compose @demo ps
curl.exe -fsS http://127.0.0.1:8088/health/ready
curl.exe -fsS http://127.0.0.1:8088/api/v1/stats
docker compose @demo exec -T worker python -m opsproof_demo.worker_control status
docker compose @control up -d --build --wait
docker compose @control ps
docker compose @control run --rm control-migrate alembic current
curl.exe -fsS http://127.0.0.1:8090/health/ready
python scripts/verify_control.py
python scripts/verify_demo.py smoke
python scripts/verify_m4_security.py
```

Expect healthy services, migration `0004`, completed regression jobs and five HTTP
401 checks. An unavailable service is a failure, not an authentication pass.
The original unavailable collector pin was corrected to verified release 0.164.0
with its immutable multi-platform manifest digest. Start the full stack. Check
`http://127.0.0.1:9090/targets` for healthy demo/control targets and Alertmanager
logs for webhook failures before fault injection.

Tempo 3.1.1 uses `backend_worker.compaction.block_retention: 24h`; both the
legacy `compactor` block and the newer documentation's top-level `compaction`
block are invalid for this exact version. This was checked against the pinned
source and binary, retaining monolithic mode, local volume and OTLP endpoint.
After the user's explicit follow-up authorization, the footer was also corrected
to the existing `--ink-soft` token (5.53:1 contrast on porcelain), and the full-page
desktop/mobile accessibility scan was restored.

Run these checks from the repository root before accepting a version change:

```powershell
docker compose -f compose.observability.yaml run --rm --no-deps otel-collector validate --config=/etc/otelcol/config.yaml
docker compose -f compose.observability.yaml run --rm --no-deps tempo '-config.file=/etc/tempo/config.yaml' '-config.verify=true'
python scripts/verify_observability.py
```

The first two commands must exit zero: they validate the actual configuration
against the exact binaries, not just YAML syntax. The existing observability CI
workflow now runs these same validators. The final command requires the full demo,
control and monitoring stacks. It makes a sampled read-only demo API request,
sends one clearly marked synthetic log through the internal collector, and polls
for the exact trace/log in Tempo/Loki and through authenticated Grafana datasources.
Expect five PASS lines and `.runtime/observability-verification.json`. Credentials
are read from `.env` and never written to the evidence file. No new ports are exposed.

If a lookup times out, inspect `docker compose -f compose.observability.yaml logs
--tail 100 otel-collector tempo loki`, confirm backend readiness and datasource
credentials, then retry the probe with a fresh marker. Never treat an OTLP 200
alone as end-to-end success. A missing binary image/unknown configuration field
fails validation and must be resolved before deployment. The test establishes
immediate delivery/querying, not a 24-hour retention soak or production durability.

### Manual UI and fault drill

In `apps/web`, run `npm.cmd run dev`, open `http://127.0.0.1:5173`, and sign in using
the local operator key. Check the investigation workspace reports recovery disabled.
Invalid inspection/actuator credentials must also return 401:

```powershell
curl.exe -sS -o NUL -w '%{http_code}' -H 'X-OpsProof-Inspect-Key: invalid' http://127.0.0.1:8088/api/v1/internal/worker-state
curl.exe -sS -o NUL -w '%{http_code}' -X POST -H 'X-OpsProof-Recovery-Key: invalid' -H 'Content-Type: application/json' --data '{\"recovery_id\":\"00000000-0000-0000-0000-000000000001\"}' http://127.0.0.1:8088/api/v1/internal/worker/resume
$env:OPSPROOF_CONTROL_RECOVERY_ENABLED='true'
docker compose @control up -d --no-deps --force-recreate control-api action-worker evidence-worker
curl.exe -fsS http://127.0.0.1:8088/api/v1/stats
[DateTime]::UtcNow.ToString('o')
docker compose @demo exec -T worker python -m opsproof_demo.worker_control pause --seconds 420
docker compose @demo exec -T worker python -m opsproof_demo.worker_control status
```

Record UTC immediately around injection. Queue/processing counts must initially
be zero, then the hold must be active with a decreasing TTL. Existing holds are
not extended. Create a `queue-burst` experiment in the UI with five jobs and
250 ms duration; retain its UUID. Within the rule's 45-second pending period plus
scrape/evaluation/notification delay, a real `OpsProofDemoQueueBacklog` incident
must fire. Do not inject a synthetic webhook and call it a real detection trial.

Open that incident's Investigate link, select the experiment, collect evidence,
and inspect the exact job IDs, recent scrape, ready API, queue and hold. Expected
diagnosis is `demo_worker_paused`, recommendation `resume_demo_worker`. Missing
or stale data must prevent action. If collection fails, inspect evidence-worker
logs, inspection credential distribution, Prometheus target/sample age and run
status. An expired experiment requires a new trial, not database status editing.

Propose the recovery, review the action, type `APPROVE DEMO WORKER RESUME`, and
approve promptly (evidence expires after 60 seconds). Observe proposed → approved
→ attempt_started → action_acknowledged → succeeded audit events. Also exercise
Reject on a separate proposal and let another proposal expire without approving;
expect `rejected` and `expired`, with no actuator execution for those records.
Repeat API requests with the same idempotency key: they must retain one record;
changing the payload with that key must return 409. Unsupported actions/invalid
confirmation must return 422. Invalid session CSRF must return 403.

```powershell
docker compose @demo exec -T worker python -m opsproof_demo.worker_control status
curl.exe -fsS http://127.0.0.1:8088/api/v1/stats
python scripts/verify_milestone4.py --recovery-id REPLACE_WITH_ACTUAL_UUID
docker compose @control logs --tail 100 action-worker evidence-worker
```

Expect hold inactive, linked jobs completed, experiment succeeded, incident
resolved, and the evidence checker to write `.runtime/milestone4-verification.json`.
Acknowledgment alone is insufficient. A verifier failure means examine each proof
and audit event; never rewrite terminal outcomes. If emergency intervention is
needed, `docker compose @demo exec -T redis redis-cli DEL opsproof:demo:worker:hold:v1`
removes only the synthetic hold; record manual intervention and do not attribute
that recovery to the action worker. Otherwise the hold expires by itself.

### Database evidence, benchmark and measurement

```powershell
docker compose @control exec -T control-db psql -U opsproof -d opsproof -c "SELECT name,status,started_at,resolved_at FROM incidents WHERE name='OpsProofDemoQueueBacklog' ORDER BY last_seen_at DESC LIMIT 5;"
docker compose @control exec -T control-db psql -U opsproof -d opsproof -c "SELECT i.name,e.status,e.created_at FROM incident_events e JOIN incidents i ON i.fingerprint=e.incident_fingerprint WHERE i.name='OpsProofDemoQueueBacklog' ORDER BY e.id DESC LIMIT 10;"
docker compose @control exec -T control-db psql -U opsproof -d opsproof -c "SELECT id,status,baseline->>'cause' AS cause,baseline->>'action' AS recommendation,ai_status,created_at,completed_at FROM investigations ORDER BY created_at DESC LIMIT 5;"
docker compose @control exec -T control-db psql -U opsproof -d opsproof -c "SELECT id,status,action,attempts,result->>'actuator' AS actuator,result->>'worker_hold_cleared' AS hold_cleared,created_at,approved_at,completed_at FROM recoveries ORDER BY created_at DESC LIMIT 5;"
docker compose @control exec -T control-db psql -U opsproof -d opsproof -c "SELECT r.action,r.status,e.type,e.created_at FROM recovery_events e JOIN recoveries r ON r.id=e.recovery_id ORDER BY e.id DESC LIMIT 30;"
docker compose @control exec -T evidence-worker python -m opsproof_control.benchmark --mode deterministic
docker stats --no-stream
docker system df
```

Inspect matching UUIDs, ordered audit transitions, firing/resolved timestamps and
`ai_status=not_requested`. No rows means no evidence, not a pass. Benchmark expects
ten valid cases, cause/action accuracy 1.0 and zero unsafe actions; synthetic
success does not establish production accuracy. Resource output is an instantaneous
measurement; inspect Windows Task Manager separately for total host usage.

Paid comparison is **not authorized in this task** and was not run. For a future
explicitly authorized evaluation, the supplied command is
`docker compose @control exec -T evidence-worker python -m opsproof_control.benchmark --mode ai --max-cases 2 --start 0 --allow-paid`.
Configure the chosen provider/key/model and enable AI only then; recreate the
evidence worker. Use starts 0,2,4,6,8 to cover ten cases in separate explicitly
budgeted invocations. Record actual tokens, latency and provider pricing; paid
cost is not fabricated by the harness (reported as null). No live model selection
or accuracy improvement is claimed. Disable AI and recreate afterward.

Detection delay = first firing receipt minus injection; investigation delay =
completed minus requested; approval-to-action = acknowledgment minus approval;
verification delay = success minus acknowledgment. Preserve failures and clock
uncertainty; do not invent percentage MTTR improvements.

### Restore, regress and review

```powershell
$env:OPSPROOF_CONTROL_RECOVERY_ENABLED='false'
$env:OPSPROOF_CONTROL_AI_ENABLED='false'
docker compose @control up -d --no-deps --force-recreate control-api action-worker evidence-worker
python scripts/verify_control.py
python scripts/verify_m4_security.py
git status --short
git diff --check
git diff --stat
git diff --cached --name-only
git diff --cached --check
git log -3 --oneline
docker compose -f compose.observability.yaml down
docker compose @control down
docker compose @demo down
```

Ensure `.env` also retains both false defaults. Recheck disabled UI state and rerun
the Python/frontend commands above after corrections. Shutdown preserves named
volumes; do not add `-v`. Review changed/new source and ensure no `.env`, `.runtime`,
credentials, dumps or browser traces are staged. Step 69's commit is conditional
on full acceptance; do not commit while required checks remain pending. No push,
merge, release, AWS provisioning or Milestone 5 work is part of this task.
