# Investigation and controlled recovery

This guide describes current code. Dated local results are in
[engineering verification](../engineering/verification.md#local-results-and-screenshots). A past passing drill
does not establish the state of a current deployment.

## Scope and responsibilities

The authenticated API records investigations, proposals, expiring approvals and
audit events. The evidence worker collects facts, runs deterministic diagnosis
and independently verifies outcomes. The action worker alone receives the fixed
demo resume credential. Model output cannot authorize an operation.

Compose supports bounded demo-worker holds/resume. The separate local Kubernetes
runbook restores only the supported worker under explicit target/scaler/freshness
guards. Temporary EKS allows observation; both recovery mechanisms remain off.
See [local operation](local-runbook.md) and [cloud runtime](../cloud/runtime-deployment.md).

## Evidence and incident semantics

Investigations collect readiness, durable queued/processing counts, authenticated
hold state and Prometheus samples. Queue counts are jobs; hold TTL and evidence
ages are seconds. At most eight unique linked experiment jobs are eligible.
Scrape health and underlying sample timestamps must refer to the same unique
targets. Every returned replica must be healthy with a sample age from zero to
30 seconds. Empty, duplicate, changed, future-dated or stale target evidence
cannot establish freshness. Investigation evidence expires after 60 seconds.

Alert delivery is authenticated. Per-fingerprint transaction locks serialize first
and repeated delivery; batches acquire locks in fingerprint order. `started_at`
identifies the current alert occurrence, while events preserve earlier transitions.
Older occurrences cannot change the current state. A repeated firing cannot reopen
the same resolved occurrence; a later start identifies a new occurrence. Repeated
notifications do not duplicate transition events. Event `occurred_at` retains source occurrence/resolution time, while event
`created_at` retains database receipt time. `last_seen_at` is receipt time
and does not move backwards. Resolution uses `endsAt` when supplied, otherwise
receipt time; a resolution ending before its start is ignored. Times require
timezone information. Ignored stale deliveries do not refresh current evidence.

## Controlled recovery

Recovery requires a firing supported incident, ready API, recent scrape, confirmed
bounded worker hold, positive queued work, an eligible verifying queue-burst
experiment and exact linked job IDs. Deterministic policy must permit the action.
The operator proposes recovery and types `APPROVE DEMO WORKER RESUME`; approval
expires after 120 seconds. The action worker rechecks eligibility before acting.

Actuator acknowledgement is not success. Independent verification checks hold
removal, every linked completed job, experiment success and a post-action incident
resolution. Missing/uncertain proof becomes indeterminate; known failure is failed.
Never replay an uncertain operation automatically or edit terminal outcomes.

## Compose procedure

Run from the repository root with locked dependencies. Preparation preserves
existing secrets; inspect the baseline before starting any service or fault drill.

```powershell
uv run --project apps/control-plane --locked python -m scripts.compose.prepare_observability --storage
uv run --project apps/control-plane --locked python -m scripts.compose.prepare_recovery
```

Use the demo base/integration/telemetry/recovery overlays and the control base/
telemetry/recovery overlays together. Refer to their actual root Compose files;
do not print resolved configuration containing credentials. Dependencies must be
healthy before migrating applications. The current control migration head is
`0008`; use `alembic upgrade head`, not an old pinned migration expectation.

With the owned local environment running, verify the original experiment and
authentication flow before deliberately pausing a worker:

```powershell
uv run --project apps/control-plane --locked python -m scripts.compose.verify_control
uv run --project apps/control-plane --locked python -m scripts.compose.verify_authentication
uv run --project apps/control-plane --locked python -m scripts.compose.verify_observability
```

For an explicitly approved hold drill, record UTC injection, firing receipt,
investigation, approval, acknowledgement and verification times. Create the bounded
hold, submit an eligible experiment, investigate its real alert and review the
exact evidence before approval. Synthetic webhook injection is not real detection
proof. Verify the result using its actual recovery UUID:

```powershell
uv run --project apps/control-plane --locked python -m scripts.compose.verify_recovery --recovery-id ACTUAL_RECOVERY_UUID
```

Afterward disable recovery/AI, verify restored state and stop only owned services.
Preserve named volumes and historical failures. Do not run broad volume deletion.

## Optional AI

The default provider/model is the qualified NVIDIA adapter. AI stays disabled;
neither this runbook nor preparation authorizes calls. The API's daily request cap
is a request limit, not a monetary guarantee. Durable running claims and exclusive
worker ownership prevent overlapping dispatch/reconciliation. Interrupted unknown
requests are failed without automatic retries. See the
[current qualification and limitations](../engineering/advisory-evaluation.md).
Retired Gemini/Groq setup and reconstruction notes are historical, not prerequisites.
