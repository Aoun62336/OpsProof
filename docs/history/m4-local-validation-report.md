> Historical record. Commands, paths and results below describe the recorded revision. See [the current repository guide](../../README.md) for maintained commands and status.

# Milestone 4 local validation and shutdown fix

Date: November 7, 2026 (Asia/Calcutta).

**Result: the reported normal-shutdown defect is fixed and locally verified. The
project is ready for a source ZIP handoff after committing this validated tree.**
This is local acceptance, not a claim of remote CI, paid-provider quality or
production/cloud acceptance. Every Pass below was executed by the assistant; no
manual user action is being counted as an unexecuted pass.

## Scope and behavior

The pre-existing Milestone 4 implementation was preserved and included in the
handoff. The shutdown fix adds cooperative signal handling, safe retry checkpoints,
review-thread joining, resource closure and a 30-second worker stop allowance.
No API contract, approval policy, database schema or persistent data was changed
by this fix. The earlier SIGINT workaround and exit-137 finding are historical;
normal SIGTERM now exits successfully. No commit/push is implied by historical
trial reports; the final commit identifier is available through `git log -1`.

Use [WORKER_SHUTDOWN.md](../operations/worker-shutdown.md) for the Git Bash shutdown sequence and
`python -B scripts/verify_shutdown.py` for the repeatable active-work drill.

## Recorded trials

- Demo/evidence interruption experiment: `f9f00670-b995-4f4a-a51f-67084f8f836c` (eight exact jobs).
- Action interruption experiment: `06b0471e-d631-4b77-834c-8ff6c29c49d3` (five exact jobs).
- Fresh browser experiment: `2ef75521-8a8c-4e0f-a2a0-f8e7c6df0687`.
- Fresh investigation: `a1bbd33d-9ac7-435f-bfad-08686f07cb19`.
- Fresh approved recovery: `bcdf9ceb-2912-4e50-a487-235913546dce` (one actuator attempt).

The action interruption trial briefly paused the demo API while the action worker
had a request in progress, sent normal SIGTERM, then unpaused the API. The worker
exited successfully and left the running experiment retryable. Its restart completed
the original operation using the existing idempotency mechanism.

## Verification matrix

| Verification | Expected result | Actual result | Status |
|---|---|---|---|
| Python lint and format | Both packages clean | Both checks passed | Pass |
| Control unit suite | No failures | 75 passed, including 8 shutdown regression cases | Pass |
| Demo unit suite | No failures | 23 passed, including 5 shutdown regression cases | Pass |
| Frontend | Lint, tests and build pass | Lint; 4 tests; TypeScript/Vite build passed | Pass |
| Existing browser suite | All tests pass | 8 passed | Pass |
| Container builds | Current source builds | Both images rebuilt successfully | Pass |
| Monitoring configuration | Native pinned-version validators pass | Prometheus, Alertmanager, Collector and Tempo passed | Pass |
| Demo API and job flow | Exact submitted work completes | Smoke verification passed | Pass |
| Control API experiment flow | Idempotency and complete event trail | Fresh experiment E2E passed | Pass |
| Authentication | Unauthenticated requests blocked | Five endpoint checks passed | Pass |
| Existing recovery history | Durable proof still validates | User recovery 45d11e2a-dc9f-4eed-a775-f1061f0a06e3 reverified | Pass |
| Fresh browser recovery | Approved action independently verified | New run succeeded with one actuator attempt; five exact jobs completed | Pass |
| Populated browser UI | Accessible desktop/mobile; working export/logout | Axe, 390px overflow, export equality and revoked session checks passed | Pass |
| Telemetry | Exact trace and log retrievable | Fresh telemetry verifier passed | Pass |
| Deterministic benchmark | Correct cause/action; no unsafe action | 10 cases passed; no paid model request | Pass |
| SIGTERM/SIGINT unit behavior | Stop requested without interrupting a commit | Both signal tests passed in both packages | Pass |
| Consumer acknowledgement | Unfinished entries stay pending | Interrupted handler not acknowledged; next entry not begun | Pass |
| Evidence review thread | Joined before connections close | Thread-join regression passed | Pass |
| Active demo worker stop | Current job finishes; next job waits | Exit 0 in 0.782s; active job completed on attempt 1 | Pass |
| Active evidence worker stop | No false failure or lost pending entry | Exit 0 in 0.687s; experiment stayed verifying; Redis pending retained | Pass |
| Demo/evidence restart | Same exact work completes | Eight original job IDs completed, one attempt each; experiment succeeded | Pass |
| Active action worker stop | No false failure; retry remains possible | Exit 0 in 0.953s; experiment remained running | Pass |
| Action restart | Safe idempotent replay | Five exact jobs completed once; experiment succeeded | Pass |
| Idle workers | Normal Compose stop needs no signal override | All five roles exited 0; no OOM | Pass |
| Outboxes and streams | No unfinished published work | Both outboxes empty; all three groups pending=0 and lag=0 | Pass |
| Final shutdown | No timeout kills | All 19 container records including completed migration containers exited 0; no OOM | Pass |
| Final cleanup | No running project processes | No Docker containers remained; ports 5173/8088/8090/9090/9093/3100/3200/3000 closed | Pass |
| Data and credentials | Preserved | Original volume set retained; .env/webhook-token hashes unchanged; shared networks idle | Pass |
| Feature defaults | Recovery and AI disabled | Capabilities false after restoring local defaults | Pass |
| Remote CI | Exact committed revision validated remotely | Not executed or pushed in this session | Pending |
| Paid AI quality | Live provider evaluation | Not enabled or called; deterministic recovery validated | Pending |
| Retention duration | Observed over full retention interval | Not waited for; immediate delivery and configuration verified | Pending |
| External cloud inventory | Cloud account resources audited | No cloud resources created or account inventory performed | Pending |

## Earlier complete-system acceptance retained

The preceding November 6 session also checked configuration/credential consistency,
live schemas (demo 0001, control 0004), container hardening and network isolation,
worker-to-target connectivity, three healthy Prometheus targets, webhook transition
deduplication, invalid inspection/actuator/webhook credentials, authenticated kill
switches, investigation/proposal idempotency and conflict rejection, invalid approval
phrases and unsupported actions, rejection with zero attempts, stale approval (409),
expiry with zero attempts, and safe actuator replay during a different worker hold.
The original JSON export matched its live database record. API/dependency outage
histories were corroborated against persisted alert events. Exact job, experiment,
investigation and recovery identities/states survived a full stack restart.
Grafana queries and screenshots showed four populated panels; populated desktop
and mobile UI screenshots were visually inspected. Those checks passed before the
shutdown fix; the matrix above identifies the checks rerun on the fixed build.

## Evidence and limitations

Portable trial evidence is in [M4_SHUTDOWN_EVIDENCE.json](m4-shutdown-evidence.json).
Detailed local logs, screenshots and prior negative-check records remain under
`.runtime/acceptance/`; that ignored directory is not part of a Git source archive.
The portable evidence and this report are included in the source handoff.

Final tests emitted non-failing warnings about the local pytest cache permissions,
the existing Starlette/httpx test-client deprecation, and browser console color
settings. They did not fail tests. Early development checks caught fixture/format
issues, which were corrected before the passing runs recorded above.

A stop grace period does not protect against an indefinitely unresponsive dependency
or machine failure. Existing durable leases and recovery rules still apply to hard
crashes. Normal shutdown and the documented active-work cases passed locally.

The existing historical failed experiment was retained as history, not deleted to
make the dashboard green. No credentials, databases, volumes, dependency folders,
or local runtime artifacts should be included in the source ZIP. Use `git archive`
from the final commit rather than zipping the entire working directory.
