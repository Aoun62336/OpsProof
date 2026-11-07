# OpsProof M3/M4 Acceptance Closure

**Status: locally applied and validated on Python 3.14 and real Docker services.** The isolated audit is historical; the local results below are the acceptance evidence for this working tree. The closure commit records this validated source; remote CI and paid AI evaluation are not claimed.

## Source anchor and scope

Starting ZIP: `OpsProof-M4.zip` at recorded HEAD `8951bbd227259a7f1440a02603fae74ebfe6b4cf` (`feature/ai-investigation-safe-recovery`). The guide originally prepared corrections in a separate audit working copy. They have now been applied locally on top of `fb2d44a` (the later deletion of `NextPhase.txt`), preserving that deletion. The local closure changes are recorded in the commit containing this report; use `git log -1` to identify it.

The preceding November 6–7 M4 evidence, UI acceptance and cooperative worker shutdown fix remain preserved. Existing `0001`–`0004` migrations, Compose/service boundaries, auth/CSRF, Forest & Porcelain UI, idempotent actuator and stored recovery history are unchanged.

## Targeted source corrections

1. **Exact-job verification:** `evidence_contracts.py` provides pure validation for count, distinct canonical UUIDs, submitted count, exact response ID and known job states. `evidence.py` rejects missing/duplicate/malformed/unknown evidence and only emits `verified` if the experiment was still in `verifying` and every expected job completed. A response with zero pending jobs is not sufficient by itself.
2. **Execution-time recovery reauthorization:** `recovery_worker.py` reconstructs the stored deterministic baseline, gathers a fresh snapshot via the existing read-only collector on **each** attempt, checks Prometheus freshness and linked IDs, rechecks current incident/experiment status, checks a fresh bounded worker hold and approval expiry before the allowlisted actuator. Uncertain responses cannot report success.
3. **Actuator acknowledgment:** An explicit `not_paused` result is a definite unsuccessful first attempt, while an unrecognized/malformed acknowledgment is `indeterminate`. After an unknown prior response, a missing hold remains `indeterminate` without an unsafe additional resume. No new actuator, credential, or DB migration was introduced.
4. **Real application logging:** `scripts/verify_observability.py` retains the synthetic OTLP pipeline probe and real Tempo trace, but adds one bounded job and requires the **actual demo worker's** completion log to appear in Loki and through Grafana. The local run below now proves this additional path on the corrected build.
5. **Documentation:** Root README identifies M4 implementation and outstanding M5–M7 rather than claiming work is at the initial foundation stage.

## Guide-reported checks in the separate audit environment

- Python 3.13 `py_compile` on modified Python code and new tests: **PASS** after normalizing one Python 3.14 exception-handler clause in a modified file. A syntax check is **not** a functional test.
- Isolated test harness with stubbed project externals, executing the actual corrected verifier/recovery functions and new unit contracts: **46 tests passed**. This includes 19 pure exact-job contract checks. The stubs are audit-only and are **not** included in the source deliverables.
- Full locked `uv`/Ruff/pytest, real Docker, Alembic migrations, Prometheus, Alertmanager, Loki, Tempo, Playwright and browser E2E for **this corrected source**: **NOT RUN**. The audit container has Python 3.13, lacks project packages and Docker, and cannot download Python 3.14 due network DNS restrictions.
- No paid AI calls, cloud provisioning, Docker volume destruction, pushes or remote publications were performed.

Do not add the 46 isolated tests to the historical M4 suite count. Re-run the **actual** project suite on Python 3.14 before accepting the changes.

## Revalidation procedure (executed locally; retained for repeatability)

1. Apply only the edited full-file replacements listed below into a feature branch based on the recorded M4 commit. Never copy the audit-only `.isolated_check/` directory.
2. Run `git diff --check`, locked demo/control Ruff, Ruff format, pytest and web lint/unit/build on the local toolchain. Confirm the existing 75 control and 23 demo tests remain green, alongside new tests; do not assume a new total without execution.
3. Check Compose config with secrets redacted. Start the existing documented demo/control/telemetry/recovery overrides, **without** deleting named volumes. Ensure AI/recovery remain disabled unless conducting the explicit approved local fault drill.
4. Run `python scripts/verify_observability.py` after telemetry is healthy. Require both synthetic OTLP and real worker log evidence. Inspect `./.runtime/observability-verification.json` after it succeeds.
5. Run an approved bounded M4 worker-hold/5-job recovery drill; record current Git SHA, experiment ID, incident fingerprint, investigation/recovery ID, fresh metrics and event timestamps; require action acknowledgment, exact job completion, experiment success and alert resolution.
6. Run negative checks for stale Prometheus samples before actuation, job-ID mismatch, duplicate job IDs, unknown state, expired approval, missing hold on retry and unknown actuator acknowledgment. Compare the logged outcomes to the test expectations.
7. Restore both paid AI and recovery feature flags to **false**, preserve all historical records, and repeat the original experiment + clean-shutdown regression. Review diff, runtime metrics and only then mark M4 accepted.

## File inventory for approval and application

- `apps/control-plane/src/opsproof_control/evidence_contracts.py` **new**
- `apps/control-plane/src/opsproof_control/evidence.py` **changed**
- `apps/control-plane/src/opsproof_control/recovery_worker.py` **changed**
- `apps/control-plane/tests/test_evidence_contracts.py` **new**
- `apps/control-plane/tests/test_evidence.py` **new**
- `apps/control-plane/tests/test_recovery_worker.py` **changed**
- `apps/control-plane/tests/test_shutdown.py` **changed test fixture**
- `scripts/verify_observability.py` **changed**
- `README.md` **status text only**
- `docs/operations/M4_ACCEPTANCE_CLOSURE_2026-11-07.md` **new**

All other source, config, migrations, credentials and UI files are intentionally untouched.


## Actual local validation on November 7, 2026

All Pass rows below were executed by the assistant using the real locked project
dependencies and local Docker environment. Mocked negative unit cases are explicitly
distinguished from live integration drills. The 46 guide-reported isolated cases
are not added to these suite totals.

The ten listed deliverables were applied. The only source-style adjustment was
restoring the existing Python 3.14 exception formatting required by Ruff. Four
additional regression cases cover expiry during collection, the experiment becoming
terminal during collection, a permitted retry preserving its recovery UUID, and a
terminal-state race preventing a second verified event. The shutdown implementation,
UI, dependencies, Compose configuration and migrations were not changed.

| Verification | Expected | Observed | Status |
|---|---|---|---|
| Control Ruff lint/format | Clean | Both passed | Pass |
| Control tests | All existing/new tests pass | 113 passed on Python 3.14 | Pass |
| Demo Ruff lint/format and tests | Original behavior preserved | Both checks and 23 tests passed | Pass |
| Frontend | Lint, unit tests and build pass | Lint, 4 tests, TypeScript/Vite build passed | Pass |
| Browser regression | All existing tests pass | 8 passed | Pass |
| Compose configuration | Three merged stacks valid | All three config checks passed | Pass |
| Native monitoring validation | Pinned binaries accept configuration | Prometheus, Alertmanager, Collector and Tempo passed | Pass |
| Container builds | Corrected source builds | Both images built | Pass |
| Original demo/control flow | Jobs, idempotency and events work | Both live verification scripts passed | Pass |
| Authentication | Unauthorized calls rejected | Existing live security verifier passed | Pass |
| Historical recovery proof | Existing data remains valid | User recovery independently reverified | Pass |
| Exact-job negative cases | Empty, duplicate, wrong-count/ID or unknown states cannot succeed | Pure contracts and actual verifier unit cases passed | Pass |
| Recovery negative cases | Stale evidence, changed state, expiry and uncertain replies handled safely | Actual worker functions tested with mocked external services; all passed | Pass |
| Fresh browser recovery | Incident to independent successful proof | One actuator attempt; five exact jobs completed; alert resolved | Pass |
| Populated UI | Accessible and functional | Desktop/mobile axe, no mobile overflow, JSON export match and logout passed | Pass |
| Real telemetry | Trace, synthetic probe and real processed-job log retrievable | Tempo/Loki and authenticated Grafana checks passed | Pass |
| Deterministic benchmark | Correct cause/action, no unsafe recommendation | 10 cases passed; no model calls | Pass |
| Live execution-time evidence loss | Earlier approval cannot override missing current evidence | Prometheus stopped after investigation; approved recovery blocked; hold unchanged; no actuator marker | Pass |
| Active-work shutdown/restart | No forced kill or job loss/duplication | Eight exact jobs completed once; evidence resumed; all five idle roles exited 0 | Pass |
| Final shutdown | No services left running | All 19 container records exited 0; containers removed; eight ports closed | Pass |
| Preservation/defaults | Keep data and disable optional actions | Original volume set and credential hashes preserved; recovery/AI false | Pass |
| Remote GitHub Actions | Exact revision tested remotely | Not run | Pending |
| Paid provider benchmark | Live model quality established | Not enabled or called | Pending |

### Exact local evidence identifiers

- Fresh browser experiment: `41a576d7-cf4f-4a79-b6ee-e03972078e1c`.
- Investigation: `fe0a14ab-bef5-487c-9032-63627537d5b9`.
- Successful recovery: `b417b9ef-a65f-4af3-b368-110d48f77d36`; actuator attempts: `1`.
- Real completed-job log: job `cfdc632b-db17-472c-9f29-50a8d3d78eea`.
- Instrumented trace: `f6ce2e287dfc4c0cae80ce5d2681f87c`.
- Negative execution-time freshness trial: experiment `dabe1d61-0288-402d-9f1f-72de3e99d1ee`, recovery `e4810170-3723-490d-b930-3a7d02440d46`.
- Expected refusal reason: `Fresh execution-time policy evidence not established`.
- Shutdown/restart experiment: `22772773-7578-4ea6-b466-2d092f9ec049` (eight jobs, each one attempt).

The live negative case has a **deliberately failed recovery record**: execution-time
policy correctly refused the action. Its worker attempt counter is not a count of
actuator requests. The actuator replay marker was absent and the hold remained active.
After proving that refusal, an explicit test-cleanup call cleared the hold; that
cleanup is not counted as a successful approved recovery. The experiment then
completed. The first 75-second alert-resolution wait expired after the Prometheus
restart; a subsequent live check confirmed the incident resolved and both Prometheus
and Alertmanager had no active alerts. This harness timeout is recorded rather than
counted as an immediate pass. Prometheus and feature defaults were restored.

Local detailed evidence is under `.runtime/m4-closure/`, including
`ui-acceptance.json`, `freshness-negative.json`, `telemetry-proof.json`,
`shutdown-verification.json`, `fixed-final-shutdown.json` and per-check logs.
That ignored directory is not automatically included in a source ZIP; this
report contains the portable summary and exact record identifiers.

### Interpretation and remaining limits

The earlier successful local trials remain valid observations of the ordinary path;
they did not establish correctness for every malformed response or authorization
race. These corrections close those specific gaps and expand coverage. Rechecks
reduce timing races but do not make separate database, HTTP and Redis operations
one atomic transaction. No stronger distributed guarantee is claimed.

The repository's preceding local validation report describes the earlier revision.
This closure report supersedes it for the changed verifier, execution-time policy
and real worker-log checks. Non-failing pytest cache and existing test-client/color
warnings did not affect passing results. Long-duration retention and external cloud
acceptance were not newly evaluated. Recreate any handoff ZIP from a commit containing
these closure changes; an archive of the old HEAD will omit them.
