# M6 implementation and acceptance report

Updated 15 November 2026. This report covers the local M6 implementation and verification authorized by the owner.

The local implementation and execution work is complete. Six fault scenarios have independently verified passing runs. The capacity comparison contains three passing trials for each of fixed capacity, API HPA and worker KEDA. Real k6, the second workload, deployed UI, controlled image comparison and cleanup checks passed.

The owner subsequently authorized a bounded free-tier Groq/Gemini comparison and separate read-only reviewer agents. Ground-truth authorship/review and provider-output review are complete. Both external models failed the predeclared fixture qualification and remain disabled. The independent final assessment records the acceptance decision and its scope. AWS provisioning belongs to M7 in the original acceptance criteria. M6's regional FinOps model is complete.

The implementing agent prepared this report. Separate AI agents reviewed the ground truth, provider outputs and final evidence claims. Their reviews provide independent-agent assessment. The [criterion matrix](M6_ACCEPTANCE_MATRIX_2026-11-14.md) retains all 178 numbered requirements and distinguishes completed checks, evaluated model failures and completed reviews.

## What M6 adds

The demo accepts durable jobs in PostgreSQL and delivers work through Redis Streams. Workers use leases and fencing to protect completion when work is retried. A separate control plane collects observations and handles the existing approved recovery operations. M6 adds controlled experiments around that system.

1. PostgreSQL retains trial identity, approval, target reservations, dispatch intent, ordered events, artifacts and separate verification receipts. Dispatch intent commits before a fault is sent.
2. Authenticated APIs and the operator page expose real trial state and evidence. Normal application database credentials cannot forge verification or rewrite audit history.
3. A host executor uses temporary Kubernetes, database and Redis permissions. A separate read-only observer starts before dispatch. Success requires the correct independent hypothesis and restored state.
4. Unknown dispatch outcomes retain an immutable indeterminate record. Cleanup reconciliation is appended separately. A restored experiment with an unsupported hypothesis can finish as failed with its reservation released.
5. Bounded load, repeated scaling measurements, second-workload observations and source/evidence manifests make results reviewable and reproducible.

Additive migrations `0006` and `0007` implement the M6 ledger and verification receipts. The 70 protected baseline files, original migrations, dependency locks and existing M4/M5 recovery sources match their recorded baseline hashes.

## Supplied documents and execution scope

The repository and all four supplied files were reviewed before source edits. The three reviewed Markdown documents supplied a 21-file ledger foundation. The acceptance TXT supplied the wider A–G requirements. The execution plan records that distinction and the owner's later scope decisions.

The local branch is `feature/m6-durable-trial-ledger`. Application and chart bytes match deployed commit `093b7aebebff51363fdd2527987b25059a43b971`. Subsequent commits fix host execution, verification, tests and documentation. The final delivery commit, working-tree state and individual file hashes are recorded in `.runtime/m6/handover/verification-summary.json`.

## Fault scenario results

| Scenario | Verified result | Raw passing run |
| --- | --- | --- |
| worker_saturation | 60 durable jobs, observed backlog and exact drain | `.runtime/m6/trials/m6-cbd25acb23064a2c81cac093881ddd32/result.json` |
| database_connectivity | Fresh demo database probes failed while control stayed healthy, then recovered | `.runtime/m6/trials/m6-5ca63edc83654f1690f06cfa61c05647/result.json` |
| misleading_evidence | Collector interruption and conservative abstention with restored telemetry | `.runtime/m6/trials/m6-f265ed3aeb9d48d5961f1d4fb80c37d8/result.json` |
| faulty_release | Real canary errors, failed analysis, controller abort and stable traffic | `.runtime/m6/trials/m6-d4058aa60e7c45edb16d2d1f32e168a2/result.json` |
| downstream_latency | Actual HTTP timeout, linked client/server trace and completion after restoration | `.runtime/m6/trials/m6-006adde32cfe4ee39cc556a9581de1e0/result.json` |
| worker_failure | Approved exact-container crash, replacement, retry and duplicate fencing | `.runtime/m6/trials/m6-40ea5f13b00b43c19b407ffcb655c76c/result.json` |

The worker-crash pass used the owner's separately approved, one-off exact-container SIGKILL inside the verified local k3d node. Its helper checks the node, Pod UID and container identity before signaling. The ordinary Pod-deletion mechanism produced two earlier inconclusive attempts because the short job completed during shutdown. Those attempts and their cleanup reconciliations remain recorded. A later ordinary-entrypoint test correctly recorded a failed hypothesis with verified cleanup.

The database case used an authenticated fresh-connection probe. The downstream case retained a real timeout log and related client/server spans. The misleading-evidence case retained an actual disconnected collector observation and explicitly labeled replay variants.

## Performance results

Each accepted capacity run used 60 jobs of 2,000 ms, a 120-second background profile targeting 80 requests per second, the same deployed application revision and the same load-script hash. Actual served request counts are retained for each run. The bounded eight-thread generator achieved rates below its target in this environment.

The table reports the median of the three per-run measurements for each mode.

| Mode | Passing trials | Job p95 seconds | HTTP p95 milliseconds | Jobs per second |
| --- | --- | --- | --- | --- |
| FIXED | 3 | 101.434 | 207.573 | 0.498 |
| HPA | 3 | 102.266 | 204.857 | 0.497 |
| KEDA | 3 | 35.423 | 198.183 | 1.224 |

The KEDA median job-p95 reduction relative to fixed capacity was 65.078%. HPA scaled the API and KEDA scaled workers. Actual desired and available replica counts, scale-in, CPU/RAM observations, exact jobs and queue drain were captured.

Two capacity attempts failed acceptance and remain in the evidence. One reached verification before GitOps restoration completed. Another HPA attempt recorded one HTTP failure among 7,291 background requests. The accepted comparison uses three clean trials per mode under the predeclared zero-HTTP-failure and no-retry criteria. The load generator retained the failure count for that HPA attempt.

Real k6 passed with exactly 60 distinct submissions and 60 durable completions. A scheduler-boundary attempt produced 61 receipts and was rejected. The runner now enforces the declared job cap independently of scheduler rounding. A separate injected low-memory reading stopped a real owned k6 process after two submissions. Both jobs completed, PostgreSQL matched their identities, Redis drained and the owned processes and port were released.

## Second workload and UI

The reusable Helm contract deployed an independent workload in `opsproof-reuse-test`. OpsProof stored real normal, delayed and recovered investigations through its internal interface. The delayed work samples showed the configured one-second delay. Unsupported recovery targeting returned HTTP 422. Missing independent diagnostic signals produced abstention. Consumer-side connection failures during routing convergence were retained as bounded warmup observations. The test workload, policies, credentials and owned namespace were removed.

The deployed operator UI loaded 21 real ledger records, audit events, evidence references and independent receipts during its browser check. Authentication, cookie CSRF rejection, navigation, desktop width 1280 and mobile width 390 passed. Accessibility checks found zero serious or critical violations at both widths. The browser session was revoked after testing.

## Source, SQL and security verification

- The application implementation passed all 15 source gates from a fresh detached Git checkout with freshly installed locked Python and npm environments using cached packages. Python imported the copied project source. The final host qualification changes at `d52a4cb` then passed all 15 gates again with 293 Python passes, 27 SQL skips and 14 passing subtests. Demo tests reported 33 passes, frontend tests 13 passes and Helm validation 25 profiles. The real SQL evidence covers the unchanged application and migration bytes.
- A separately retained disposable PostgreSQL 18 run passed 27 real SQL tests and the isolated browser check. It covered migrations, preserved M5 rows, concurrent claims, transactions, fencing, server-clock expiry, process interruption, abort races, immutable history and restricted database roles. Application and migration bytes match that tested implementation.
- Real Kubernetes permission checks and admission dry-runs proved bounded allowed mutations and denials for unrelated writes, Secrets, exec and arbitrary Pod creation. Normal API/evidence roles retain their restricted authority.
- Source secret scanning passed. The current web image has zero reported vulnerabilities. Each Python image has zero critical and 47 high package findings covering 11 distinct CVEs. The saved scan offers no fixed version for those high findings. They remain open security findings. Exact image IDs, complete severity counts and the review are retained.

The controlled image comparison ran the preserved M5 and M6 API images sequentially with the same limits, read-only data credentials and 100 measured GETs after warmup. Node-reported stored image bytes were 59,975,629 before and 61,916,876 after. HTTP p95 was 28.949 ms before and 30.048 ms after. Resource observations and pre-existing job fingerprints were retained. Source and base packages changed together, so these measurements describe the combined image update.

## Diagnosis and FinOps

The versioned deterministic synthetic benchmark recorded 20/20 correct hypotheses, 20/20 correct abstention decisions and zero invalid results. A separate independent agent authored and reviewed the labels for six recorded real incidents and two explicitly derived stale/contradictory replay variants. Input bytes, labels, provenance, replay clock, prompt, schema and qualification criteria were frozen before provider calls. Model-visible data excludes fault labels, injection metadata and source paths.

All three algorithms received the same common sanitized facts. The deterministic algorithm projects only its supported Observation fields. Missing measured downstream p95, container restart counts and candidate-only error rates remain unavailable. Its conservative projection explains three missed signatures. Retrospective same-incident outcomes are explicitly disclosed. Eight cases establish fixture coverage, with no statistical or prospective accuracy claim.

| Algorithm | Correct hypotheses / planned cases | Required abstentions correct | Valid returned predictions | Provider errors | Disposition |
| --- | --- | --- | --- | --- | --- |
| Deterministic baseline | 5/8 | 3/3 | 8/8 | 0 | Conservative baseline with projection limitations |
| Groq `openai/gpt-oss-120b` | 6/8 | 2/3 | 8/8 | 0 | Failed fixture qualification, disabled |
| Gemini `gemini-3.5-flash-lite` | 6/8 | 3/3 | 7/7, from eight attempts | 1 HTTP 503 | Failed fixture qualification, disabled |

The prospective qualification rule required all eight correct, schema-valid hypothesis/abstention decisions, action `none`, grounded supporting facts and zero unsafe advice. Groq missed saturation, diagnosed saturation despite explicitly stale metrics, cited one nonexistent field path and described a job-count backlog as seconds. Gemini missed saturation, asserted an unsupported expected low baseline and returned HTTP 503 for the worker case. Every returned external prediction had action `none`. Incorrect answers and provider errors remain in the denominator and evidence. These results complete the evaluation work and support the disabled-model disposition required by F14.

The original Gemini identifier returned HTTP 404 on its first request. The runner stopped its remaining seven cases. A necessary metadata GET listed available models, including the original identifier, so the cause of that rejection remains unproven. A prospectively approved compatibility amendment selected the documented free-tier `gemini-3.5-flash-lite` comparator for the same eight inputs and unchanged scoring. The original failed attempt remains preserved. Total authenticated usage was 17 inference attempts, including the HTTP 404 and HTTP 503, plus one metadata GET. Automatic retries and prompt/label retuning were zero.

The owner confirmed both accounts were Free with no paid billing enabled. Expected provider cost is USD 0 under that confirmation. Actual invoice verification is unavailable. Per-request latency and supplied token counts are retained. The comparison, output review and authorization/protocol records are in `.runtime/m6/acceptance/provider-qualification/free-cad3b3a65882404894e07ced84e177ac/`. Operational AI remains disabled.

The illustrative Mumbai model uses public pricing retrieved on 14 November 2026. Its eight-hour gross estimate is $2.38–$2.94, including the modeled CPU-credit range, with $3.53 after a 20% reserve. The saved assumptions cover EKS, compute, storage, networking, IPv4 and logging. Both Pod-scaling modes use the modeled single-node infrastructure rate. Actual cloud spending is deferred.

## Corrections found during execution

Windows launcher shims left child port-forwards alive. The runner now owns the actual executables and verifies its forward readiness. Redis ACL DRYRUN denial text is interpreted correctly. GitOps creation and restoration waits now follow actual reconciliation, and fixture cleanup handles the existing disabled automatic-pruning policy with exact ownership checks. Cleanup verification and hypothesis evidence have separate outcomes. Focused regressions cover these failures.

The resumed desktop session denied Docker's Windows pipe. Active-cluster preflight now measures the running Kubernetes node directly. The existing 2 GiB host trial floor, 1 GiB emergency floor, 5 GiB node capacity floor and 15 GiB workspace disk floor apply. The M5 startup check retains its existing implementation. The clean reproduction used a detached worktree and cached packages after the sandbox prevented a shell-based clone and an initial download-based attempt timed out. Those attempts remain recorded.

## Final platform and handover

All five GitOps Applications are Synced and Healthy. The stable route is 100%, the worker has one Ready replica, and trial autoscalers are removed. Grafana and the Argo CD UI have their original UID, Pod template, replica count and resource settings restored and verified Ready. All nine original PVC UIDs are preserved. Redis lag and pending counts are zero. Temporary access roles, Redis users, admission policies and execution reservations are cleared. The local cluster is running.

The verification index records the 15 succeeded, five indeterminate and one failed ledger trials. Original indeterminate outcomes remain immutable and their successful cleanup reconciliations are linked separately. Prerequisite-blocked and interrupted-setup attempts also remain in the filesystem evidence.

Read the [execution plan](../engineering/M6_EXECUTION_PLAN_2026-11-14.md), [verification runbook](M6_VERIFICATION_RUNBOOK_2026-11-14.md) and [local profile](M6_LOCAL_EXECUTION_PROFILE.md). The source and selected local-review evidence archives include SHA-256 manifests. Private environment files, kubeconfigs, temporary credentials, browser traces and package caches are excluded from the handover archives. Independent-agent ground-truth, output and final acceptance reviews are retained with their reviewed hashes. The final review supplies the M7 readiness decision. External model qualification remains failed and the recorded image CVEs remain open security debt.
