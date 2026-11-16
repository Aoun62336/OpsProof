> Historical record. Commands, paths and results below describe the recorded revision. See [the current repository guide](../../README.md) for maintained commands and status.

# OpsProof Milestone 4 Trial Results

> Update, November 7, 2026: the shutdown defect is fixed and new local regression,
> active-work shutdown/restart and browser recovery trials passed. See
> [the current validation report](m4-local-validation-report.md) and
> [normal shutdown instructions](../operations/worker-shutdown.md). Earlier entries below are historical.


## Verification Status

Local recovery trial passed on 2026-11-06. The three subsequently authorized telemetry/accessibility corrections are verified below; remote CI and human visual review remain pending.

Do not record passing outcomes before performing the test.

## Environment

- Platform: Local Docker Compose on Windows
- Operating system: Windows-11-10.0.26300-SP0
- CPU: Not measured
- Available RAM: Not measured
- Docker version: 29.9.2
- Compose version: v5.6.1
- Git commit: 5b8d6a7 baseline plus uncommitted Milestone 4 changes
- Python version: 3.14 project runtime
- Prometheus version: v3.15.1
- Alertmanager version: v0.34.2

## Controlled Scenario

- Scenario: queue-burst
- Job count: 5
- Duration per job: 250 ms
- Synthetic worker-hold TTL: 420 seconds

## Trial 1

| Measurement | Actual value |
|---|---|
| Fault injection UTC | 2026-11-06T04:56:10.921231+00:00 (recorded immediately after hold command) |
| Experiment ID | 0e74fd1c-a43b-4193-8908-57b8b3c86aa5 |
| First firing event UTC | 2026-11-06T04:57:26.879537Z |
| Incident fingerprint | c2097b8d69697ed2 |
| Investigation ID | 3d5c24f3-e16c-48c8-836b-9fb69e748f17 |
| Diagnosis result | demo_worker_paused / resume_demo_worker |
| Recovery ID | b7c6ca3e-66d6-4356-9be1-91bbdd9fc198 |
| Approval UTC | 2026-11-06T04:57:28.988217Z |
| Action acknowledged UTC | 2026-11-06T04:57:29.856463Z |
| Verification completed UTC | 2026-11-06T04:57:47.674446Z |
| Alert resolved UTC | 2026-11-06T04:57:46.874709Z |
| Linked jobs completed | 5 / 5 exact recorded IDs |
| Experiment status | succeeded |
| Recovery status | succeeded, one actuator attempt |
| Manual intervention | None in successful trial; authenticated API approval supplied by test operator |

## Calculated Measurements

| Measurement | Actual result |
|---|---|
| Detection delay | approximately 75.96 seconds |
| Investigation duration | approximately 0.9 seconds |
| Approval-to-action delay | approximately 0.87 seconds |
| Recovery verification duration | approximately 17.82 seconds |
| Overall trial duration | approximately 96.75 seconds |

## Security Checks

| Check | Result |
|---|---|
| No credentials rejected | PASS: five live HTTP 401 checks |
| Invalid actuator key rejected | PASS: live invalid and missing keys return 401; unit boundary tests also pass |
| Recovery disabled by default | PASS: defaults and authenticated gate tests; restored after trial |
| Stale evidence rejected | PASS: live approval HTTP 409 after 62 seconds |
| Unknown incident rejected | PASS: live authenticated request returns 404 |
| Unsupported action rejected | PASS: live authenticated extra action returns 422 |
| Expiring hold rejected | PASS: unit tests |
| Duplicate action recognized | PASS: live actuator returned replayed for same UUID |
| Operator rejection recorded | PASS: live rejected record, zero attempts |
| Invalid CSRF rejected | PASS: live browser investigation mutation HTTP 403 |

## Diagnosis Evaluation

| Measurement | Deterministic | AI candidate |
|---|---|---|
| Cases evaluated | 10 | Not enabled |
| Cause accuracy | 10/10 | Not enabled |
| Action accuracy | 10/10 | Not enabled |
| Unsafe suggestions | 0 | Not enabled |
| Abstention behavior | All nine no-action cases matched | Not enabled |
| Token usage | Not applicable | Not enabled |
| Provider cost | 0 | Not enabled |

## Resource Usage

Record observed CPU, memory and disk consumption.

Do not substitute configured container memory limits
for measured consumption.

## Findings

The complete metrics-driven recovery path succeeded with real local jobs, Prometheus/Alertmanager notifications and independent verification. AI was not called. Local evidence is retained in ignored `.runtime/m4-drill.json`, `milestone4-verification.json`, and `m4-negative.json`. These are evidence artifacts, not committed secrets or fabricated fixtures.

## Failures and Corrections

Historical initial-trial findings are preserved here. The three telemetry/accessibility issues were subsequently resolved in the follow-up section below.

- Initial regression failed because the demo telemetry override dropped worker/dispatcher default network membership. Added the two memberships and reran successfully; the failed experiment remains in history.
- Collector image `otel/opentelemetry-collector-contrib:0.164.1` returned `no such manifest`; its pin was not changed. Detection services ran independently with their original versions.
- Existing Tempo 3.1.1 rejects `observability/tempo.yml:23`: `field compactor not found in type app.Config`, and restarts. No prior-milestone tracing redesign or version change was made.
- First browser run reported seven successful tests but did not finish process cleanup in the restricted environment; it was interrupted. Elevated rerun completed.
- Full-page axe scan found a pre-existing footer contrast violation (4.3:1 vs 4.5:1). The new workspace passes its scoped scan; the footer remains an explicit unrelated limitation.
- New test assertions initially mistook SELECT FOR UPDATE for a mutating UPDATE; corrected the assertions and all tests passed.
- A trial command initially used unsupported --ttl; corrected to --seconds before fault injection. A replay probe initially looked up the wrong environment variable name and made no request; corrected probe returned replayed.

## Limitations

This local simulated experiment does not establish
production availability or production MTTR.

## Final local verification results

Commands, execution directories, expectations and troubleshooting are in
`M4_INVESTIGATION_RECOVERY.md` under Reproducible commands. These results describe
checks actually executed, not the completion of a remote CI workflow.

| Check | Actual result |
|---|---|
| Control Ruff lint/format | PASS; 32 files formatted |
| Demo Ruff lint/format | PASS; 14 files formatted |
| Control pytest | PASS; 67 tests |
| Demo pytest | PASS; 18 tests |
| Web lint / Vitest | PASS; 4 tests |
| TypeScript / Vite build | PASS |
| Playwright | PASS; 8 tests, including investigation mobile overflow, full-page desktop/mobile axe and missing-CSRF rejection |
| Migration | Live database reports 0004; prior experiment records preserved |
| Combined Compose configuration | Validated and demo/control images built; services healthy after network correction |
| Original experiment regression | PASS before and after recovery; final run `65ef20ba-0c7e-4b88-9024-7040340e4673` |
| Demo smoke | PASS before and after recovery |
| Authentication smoke | All five live unauthenticated requests return 401 |
| Authenticated kill switches | Recovery and AI requests return 403 with both runtime flags false |
| Investigation idempotency | Same key/payload returned same UUID; changed run link returned 409 |
| Proposal idempotency | Same key/payload returned same UUID |
| Exact approval phrase | Invalid phrase returned 422; valid phrase recorded approved event |
| Rejected proposal | `6f621da8-d98d-40d5-9547-63455cad8816`, zero attempts |
| Stale approval | Live request after 62 seconds returned 409 |
| Unapproved proposal expiry | Live worker transitioned to expired with zero attempts |
| Actuator replay | Same successful recovery UUID returned `replayed` |
| Independent recovery verifier | PASS; exact jobs, hold, experiment, resolved incident and ordered audit evidence |
| AI quota / interrupted work / unsafe evidence | Covered by isolated unit tests; no paid calls |
| Deterministic benchmark | 10/10 cause and action labels, ten valid responses, zero unsafe suggestions, zero provider cost |
| Whitespace / working tree | `git diff --check` passed; source changes reviewed; no files staged |

Pytest emitted a nonfatal existing local cache-directory warning. Demo tests also
emitted the Starlette TestClient httpx deprecation warning. Neither is reported as
a test failure or silently removed by changing dependencies.

The second fault trial intentionally tested rejection and expiry. Its hold was
allowed to expire naturally; it is not counted as an action-worker recovery.
Both feature flags were restored to false and authenticated capability/gate checks
confirmed the resting state. `.env` retains false defaults. No paid calls, cloud
provisioning, push, merge or release occurred.

## Acceptance boundaries and pending human checks

- The Milestone 4 local diagnosis → approval → restricted action → independent
  verification path is demonstrated. The eight browser checks cover navigation,
  session security, the new empty investigation view and mobile layout. A human
  walkthrough of the populated approval/audit interface remains pending; use the
  exact manual drill in the runbook. Do not equate the API-driven trial with a
  manually typed browser approval.
- The original collector/Tempo startup failures and footer contrast issue were resolved in the authorized follow-up below. Exact trace/log retrieval through Grafana and full-page automated accessibility now pass. Human visual review and long-duration retention testing remain distinct checks.
- Total Windows host RAM/CPU and human Task Manager inspection remain pending.
  Container readings below are actual samples, not configured memory limits.
- Remote CI was not run because no push was authorized. Step 69's conditional
  acceptance commit was not made. The branch remains
  `feature/ai-investigation-safe-recovery` with reviewable uncommitted changes.
- Optional live AI evaluation/provider selection remains disabled by instruction.
  Mocked adapter tests establish parsing/gating only, not provider availability or
  model quality. Paid costs and production improvements are not claimed.

## Measured container sample

Immediately after Prometheus/Alertmanager startup, `docker stats --no-stream`
reported the following. Workload timing differs across samples; no performance
comparison is inferred.

| Container | CPU | Memory |
|---|---:|---:|
| Control API | 0.57% | 76.43 MiB |
| Action worker | 0.10% | 73.63 MiB |
| Evidence worker | 0.42% | 73.80 MiB |
| Demo API | 0.27% | 73.84 MiB |
| Demo worker | 0.07% | 79.32 MiB |
| Prometheus | 0.09% | 30.57 MiB |
| Alertmanager | 0.25% | 11.57 MiB |

Trial durations above use terminal and database UTC timestamps and are approximate.
Clock synchronization was not independently calibrated; subsecond numbers should
not be presented as calibrated timing precision.

A later sample after starting the remaining available monitoring images measured
Loki 35.33 MiB / 1.40% CPU and Grafana 248 MiB / 2.29% CPU. Tempo was restarting,
so its reported zero memory is not a valid running-service measurement. Grafana
health returned HTTP 200. Docker disk accounting reported 6.292 GB images,
403.8 MB local volumes and 4.614 GB build cache (whole local Docker environment,
not an incremental Milestone 4 footprint). No cleanup deleted these volumes.

Final database inspection found 12 succeeded experiments and the one preserved
initial failed regression; no experiment remained verifying. Recovery rows were
one succeeded (one attempt), one rejected (zero attempts) and one expired (zero
attempts). Worker hold inspection reported inactive with zero remaining TTL.

Final Loki readiness returned HTTP 200 (`ready`). Both combined Compose definitions
passed `config --quiet`. Preparation was rerun and its before/after `.env` hash
was identical; both default flags remain false. The three new helper scripts also
passed Ruff lint/format after formatting corrections. All local task stacks were
stopped using the Step 66 `down` commands without volume deletion; `docker ps`
then returned no running containers. Evidence volumes and ignored runtime JSON
remain available for subsequent review. No commit or staging was performed.

## Changed-file manifest

Follow-up corrections also modify `.github/workflows/observability.yml`,
`compose.observability.yaml`, `observability/tempo.yml`,
`apps/web/src/styles/shell.css`, the existing browser test and documentation;
`scripts/verify_observability.py` is the added reproducible delivery probe.

`NextPhase.txt` was supplied by the user and remains unmodified/untracked.

- `.github/workflows/control-plane.yml`
- `apps/control-plane/src/opsproof_control/action.py`
- `apps/control-plane/src/opsproof_control/api.py`
- `apps/control-plane/src/opsproof_control/config.py`
- `apps/control-plane/src/opsproof_control/evidence.py`
- `apps/control-plane/src/opsproof_control/streams.py`
- `apps/demo-workload/src/opsproof_demo/api.py`
- `apps/demo-workload/src/opsproof_demo/config.py`
- `apps/demo-workload/src/opsproof_demo/worker.py`
- `apps/web/e2e/operations.spec.ts`
- `apps/web/src/app/App.tsx`
- `apps/web/src/lib/api.ts`
- `apps/web/src/lib/types.ts`
- `apps/web/src/pages/IncidentsPage.tsx`
- `apps/web/src/styles/app.css`
- `apps/web/src/styles/incidents.css`
- `compose.demo.telemetry.yaml`
- `docs/ENGINEERING_LOG.md`
- `apps/control-plane/alembic/versions/0004_investigations_recoveries.py`
- `apps/control-plane/src/opsproof_control/benchmark.py`
- `apps/control-plane/src/opsproof_control/diagnosis.py`
- `apps/control-plane/src/opsproof_control/investigation_worker.py`
- `apps/control-plane/src/opsproof_control/model_provider.py`
- `apps/control-plane/src/opsproof_control/operations.py`
- `apps/control-plane/src/opsproof_control/recovery_worker.py`
- `apps/control-plane/tests/test_diagnosis.py`
- `apps/control-plane/tests/test_model_provider.py`
- `apps/control-plane/tests/test_operations_security.py`
- `apps/control-plane/tests/test_recovery_worker.py`
- `apps/demo-workload/src/opsproof_demo/worker_control.py`
- `apps/demo-workload/tests/test_worker_control.py`
- `apps/web/src/pages/InvestigationPage.tsx`
- `apps/web/src/styles/investigations.css`
- `compose.control.recovery.yaml`
- `compose.demo.recovery.yaml`
- `docs/operations/M4_INVESTIGATION_RECOVERY.md`
- `docs/operations/M4_TRIAL_RESULTS.md`
- `scripts/prepare_recovery.py`
- `scripts/verify_m4_security.py`
- `scripts/verify_milestone4.py`

## Authorized telemetry/accessibility correction — 2026-11-06

The user explicitly requested correction of the three outstanding issues while
preserving the existing architecture and design. All three are now resolved.

- Collector: release 0.164.0, verified multi-platform manifest digest
  `sha256:340c9ca6a36617084c6661bdc4f0fe92b7cda5a805d61673ec8db375fddc522b`.
  The image pulled successfully and its native configuration validator exited 0.
- Tempo 3.1.1: moved 24-hour retention to
  `backend_worker.compaction.block_retention`. The earlier proposed top-level
  `compaction` key was rejected by this binary; current/latest documentation was
  newer than the installed version. The exact v3.1.1 source and native verifier
  established the correct path. Effective `/status/config` confirms 24h retention.
  No image downgrade, new service, Kafka deployment, volume deletion or port change.
- Footer: reused existing `--ink-soft` rather than changing the global palette.
  Contrast improves from 4.31:1 to 5.53:1. Removed the scoped axe exclusion and
  verified full-page desktop and mobile scans without serious/critical violations.

Validation actually performed:

| Check | Result |
|---|---|
| Collector native `validate` | Exit 0 |
| Tempo native `-config.verify=true` | Exit 0 |
| All six observability services | Running, zero restarts at inspection |
| Instrumented demo trace through collector to Tempo | Retrieved exact trace ID |
| Marked synthetic log through collector to Loki | Retrieved exact log marker |
| Authenticated Grafana Tempo/Loki datasource queries | Retrieved same trace and log |
| Web lint, 4 unit tests, TypeScript/Vite build | Passed |
| Browser suite | 8 passed, full-page desktop/mobile accessibility included |
| Original experiment workflow | Passed; run `aec32130-7c8b-4abd-af1b-95278355c4a0` |
| Demo smoke and five authentication checks | Passed |
| Probe Ruff lint/format and `git diff --check` | Passed |

The telemetry evidence is in ignored `.runtime/observability-verification.json`:
trace `efda97c89ca34dc2a9c684cf98549cd6`, verified at
`2026-11-06T06:37:59.522198+00:00`. The log is deliberately labeled synthetic;
the trace comes from the real instrumented demo stats endpoint. This proves the
write/read path, including Grafana's datasource proxy, not a manual visual review
of every Grafana panel or a long-duration retention/durability test.

The existing observability CI workflow now validates both pinned binaries against
their mounted configs. Its commands passed locally; remote CI has not been run.
Exact repeatable commands and troubleshooting are in the M4 operational runbook.
After validation, authenticated capabilities confirmed both recovery and AI still
disabled. All local stacks were stopped again without deleting named volumes.
Changes remain unstaged and uncommitted; nothing was pushed or released.

Version-specific references:

- [Collector v0.164.0 release](https://github.com/open-telemetry/opentelemetry-collector-releases/releases/tag/v0.164.0)
- [Tempo v3.1.1 root schema](https://github.com/grafana/tempo/blob/v3.1.1/cmd/tempo/app/config.go)
- [Tempo v3.1.1 backend worker schema](https://github.com/grafana/tempo/blob/v3.1.1/modules/backendworker/config.go)
