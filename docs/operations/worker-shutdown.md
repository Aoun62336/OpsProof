# Worker shutdown and restart

The November 7, 2026 fix replaces the manual SIGINT workaround. Ordinary Docker
Compose stop now sends SIGTERM to the worker processes and they exit successfully.
The public APIs, database schema, approval rules, and job payloads are unchanged.

## What happens internally

Both independently packaged applications install SIGTERM/SIGINT handlers only for
background roles. The handlers request cooperative shutdown rather than interrupting
a database transaction. Dispatchers finish the current outbox transaction. The demo
worker completes its bounded current job, commits completion, and acknowledges it;
it does not begin the next delivered entry. A paused worker's wait is interruptible.

Control-plane consumers check for shutdown between entries and before secondary
work. Long experiment submission and verification loops stop at safe checkpoints.
A dedicated shutdown exception bypasses business-failure handlers: unfinished Redis
entries remain pending, and the existing consumer-group claim mechanism retries
them after its idle lease. Experiment submission reuses the original per-job
idempotency keys. A read-only investigation interrupted in the running state uses
its existing 60-second stale-work retry; a paid operation already in progress is
allowed to finish its bounded provider call rather than being blindly replayed.
Recovery actuator execution retains its existing durable state and bounded replay
rules. The evidence review thread is joined before connection pools close.

The five Compose background services have a 30-second stop grace period. This is
a cooperative shutdown allowance, not a guarantee against an indefinitely blocked
external dependency or a hard machine failure. Existing lease/retry safeguards
remain relevant for crashes and forced kills.

## Safe full shutdown (Git Bash, project root)

Stop submitting requests; finish or reject pending approvals. Wait for jobs,
experiments and recoveries to reach terminal states. Stop a manually started Vite
frontend with Ctrl+C in its own terminal. Keep databases and target services alive
while their dependent workers finish.

```bash
demo() {
  docker compose -f compose.yaml -f compose.target-integration.yaml \
    -f compose.demo.telemetry.yaml -f compose.demo.recovery.yaml "$@"
}
control() {
  docker compose -f compose.control.yaml -f compose.control.telemetry.yaml \
    -f compose.control.recovery.yaml "$@"
}
observe() { docker compose -f compose.observability.yaml "$@"; }

observe stop prometheus alertmanager
control stop control-api
control stop control-dispatcher action-worker evidence-worker
demo stop api
demo stop dispatcher worker
observe stop otel-collector grafana tempo loki
control stop control-redis control-db
demo stop redis db

# Inspect worker exit codes before removing containers: expect exited / 0 / false.
for id in $(control ps -aq control-dispatcher action-worker evidence-worker) \
          $(demo ps -aq dispatcher worker); do
  docker inspect --format '{{.Name}} {{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}}' "$id"
done

control down
demo down
observe down

docker ps -a --filter name=opsproof
docker volume ls --filter name=opsproof
```

There should be no remaining project containers; named data volumes should remain.
Do not use `down -v`, `docker volume prune`, or delete database/storage directories.
The shared external networks can remain without attached containers.

## Repeatable shutdown drill

With the full local stacks already running and no active work or worker hold:

```bash
python -B scripts/compose/verify_shutdown.py
```

This creates an eight-job experiment, stops the demo worker during a job, stops the
evidence worker while verification is pending, stops the other background roles,
and restarts them. It checks exit code 0, retention of pending evidence, exact job
IDs, one attempt per job, successful resumed verification, and idle shutdown of all
five background processes. It restores workers and saves evidence in
`.runtime/verification/compose/shutdown.json`. It does not perform the final full shutdown;
use the sequence above afterward.

Local validation results and remaining nonlocal scope are recorded in
[local results](../public/README.md#local-results-and-screenshots).
