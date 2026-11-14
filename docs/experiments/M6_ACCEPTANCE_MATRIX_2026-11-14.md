# M6 acceptance matrix — 14 November 2026

**Complete M6 acceptance: NOT ACHIEVED.** All 178 numbered criteria from the
supplied acceptance TXT are represented below. This is an evidence assessment,
not an independent sign-off or a percentage score.

- **VERIFIED LOCAL**: the stated bounded source/isolated behavior has actual evidence.
- **PARTIAL**: useful implementation/evidence exists, but the complete criterion is unproven.
- **BLOCKED**: a stated resource, authorization, security or review prerequisite is missing.
- **NOT RUN**: the required real execution was not performed.

A local verified row does not promote its overall gate. Evidence is indexed in
`.runtime/m6/handover/verification-summary.json`; raw paths and exact source hashes
are in the selected evidence manifest. Read the [report](M6_ACCEPTANCE_REPORT_2026-11-14.md)
for caveats that apply across rows.

The unnumbered requirements also remain mandatory: all six named scenarios must
satisfy C01–C15 separately; D2 exact durable job/Redis correctness and D4 actual
detection/recovery timelines are NOT RUN; E3/E4 required metrics and reporting
need real measurements and at least three passing comparable runs per mode.
Current counts are six live scenarios 0/6, real k6 0, capacity trials 0/9,
real model comparisons 0 and second-workload runtime investigations 0.

| ID | Supplied acceptance criterion | Current status | Evidence / remaining gap |
| --- | --- | --- | --- |
| A01 | All M6 source changes are based on the correct accepted M5 source revision | VERIFIED LOCAL | Source reconciliation, locked checks and native Helm results; see final evidence index. No live compatibility claim. |
| A02 | Existing M4/M5 recovery, GitOps, scaling and observability implementations remain compatible | PARTIAL | M4/M5 source regressions pass and protected files are unchanged; deployed M6 compatibility is untested. |
| A03 | Python dependencies remain locked and application source passes Ruff and pytest | VERIFIED LOCAL | Source reconciliation, locked checks and native Helm results; see final evidence index. No live compatibility claim. |
| A04 | Frontend passes linting, Vitest, TypeScript checks and production build | VERIFIED LOCAL | Source reconciliation, locked checks and native Helm results; see final evidence index. No live compatibility claim. |
| A05 | Helm charts render correctly for default, enabled and disabled M6 configurations | VERIFIED LOCAL | Source reconciliation, locked checks and native Helm results; see final evidence index. No live compatibility claim. |
| A06 | Invalid Helm values and unauthorized component combinations are rejected | VERIFIED LOCAL | Source reconciliation, locked checks and native Helm results; see final evidence index. No live compatibility claim. |
| A07 | No experimental fault capability is enabled by default | VERIFIED LOCAL | Source reconciliation, locked checks and native Helm results; see final evidence index. No live compatibility claim. |
| A08 | All documented source differences, including your Grafana memory adjustment, are reviewed | VERIFIED LOCAL | Source reconciliation, locked checks and native Helm results; see final evidence index. No live compatibility claim. |
| A09 | No credentials, kubeconfigs, Terraform state or runtime secrets enter the source commit | PARTIAL | Source Gitleaks scan and sanitized bundle review pass; no staged/committed release exists. |
| A10 | Source checks are repeatable from the documented toolchain and dependency locks | PARTIAL | Locked source-copy reproduction is recorded; full clean committed deployment reproduction remains open. |
| B01 | M6 database migration applies successfully to an isolated PostgreSQL database | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B02 | Existing M4/M5 tables, data and migrations remain intact | PARTIAL | Original migration hashes and core source preserved; 0005 sentinel data survives 0006 in an isolated database. Existing M5 database was not migrated. |
| B03 | Trial creation, state transitions and events are durable across process restarts | PARTIAL | Durable SQL state and new-connection restart behavior tested; actual deployed coordinator/actuator process interruptions are untested. |
| B04 | The scenario ID, target identity, source revision, timestamps and status are retained | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B05 | Identical idempotent requests return the same logical result | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B06 | Reusing an idempotency key with conflicting inputs is rejected | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B07 | Two simultaneous trials cannot acquire the same exclusive target | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B08 | Database transactions prevent partially committed trial state | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B09 | Stale worker leases or fencing tokens cannot modify a new owner's trial | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B10 | Events have reliable ordering and an auditable append-only history under normal application permissions | PARTIAL | Ordered append-only trigger behavior tested; independent least-privilege database-role acceptance is incomplete. |
| B11 | The trial coordinator runs separately from existing M4/M5 recovery workers | PARTIAL | Separate bookkeeping role and tokenless chart configuration exist; role not deployed for acceptance. |
| B12 | Work claiming, retries and timeouts have durable records | PARTIAL | Ledger intent, timeout, abort/ack races and retained reservations tested in SQL; live actuator crash/replay behavior awaits qualification. |
| B13 | Pending work survives dispatcher or worker interruption | PARTIAL | Durable SQL state and new-connection restart behavior tested; actual deployed coordinator/actuator process interruptions are untested. |
| B14 | An action's dispatch intent is recorded before an externally visible mutation can occur | PARTIAL | Ledger intent, timeout, abort/ack races and retained reservations tested in SQL; live actuator crash/replay behavior awaits qualification. |
| B15 | Lost acknowledgments do not cause blind fault-injection replay | PARTIAL | Ledger intent, timeout, abort/ack races and retained reservations tested in SQL; live actuator crash/replay behavior awaits qualification. |
| B16 | Unknown execution outcomes remain indeterminate until reconciled | PARTIAL | Ledger intent, timeout, abort/ack races and retained reservations tested in SQL; live actuator crash/replay behavior awaits qualification. |
| B17 | Aborting a possibly injected trial does not falsely claim cleanup | PARTIAL | Ledger intent, timeout, abort/ack races and retained reservations tested in SQL; live actuator crash/replay behavior awaits qualification. |
| B18 | Unverified cleanup prevents release of a target reservation where another trial could be unsafe | PARTIAL | Ledger intent, timeout, abort/ack races and retained reservations tested in SQL; live actuator crash/replay behavior awaits qualification. |
| B19 | Terminal trials cannot be modified into new success states | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B20 | A trial cannot be marked succeeded without independent verification and successful cleanup | PARTIAL | SQL requires evidence/cleanup references and guards success. Trusted independent artifact provenance and live postconditions are incomplete. |
| B21 | M6 API endpoints require existing operator authentication | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B22 | Cookie-authenticated state-changing requests enforce CSRF protections | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B23 | Malformed requests, wrong data types and unsupported scenario identifiers are rejected | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B24 | Approval expiration is enforced using trustworthy server-side time | VERIFIED LOCAL | Actual disposable PostgreSQL/API tests, including concurrent connections, transactions, fencing and server-clock expiry. |
| B25 | Approval applies only to the exact scenario, target and intended execution | PARTIAL | Scenario/target approval and dispatch identity checks implemented; live execution identity/authority must be independently qualified. |
| B26 | Ordinary API and evidence workers cannot obtain unrestricted Kubernetes mutation permissions | PARTIAL | Existing role boundaries and tokenless coordinator preserved; new actuator uses local admin credentials and needs restricted authority. |
| B27 | AI output cannot authorize or execute operational changes | VERIFIED LOCAL | Diagnosis remains advisory with action none; model output has no new execution path. External model calls disabled. |
| B28 | Every accepted, rejected, expired, aborted or indeterminate request has an appropriate audit record | PARTIAL | Trial transition history tested; complete rejected-request and runtime authorization audit coverage remains unproven. |
| C01 | Versioned scenario identifier and written hypothesis | PARTIAL | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C02 | Fixed, authorized target with recorded identity | PARTIAL | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C03 | Known-good baseline state before injection | PARTIAL | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C04 | Explicit Kubernetes context and environment | PARTIAL | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C05 | Predeclared fault mechanism and maximum duration | PARTIAL | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C06 | Resource limits and stop conditions | PARTIAL | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C07 | Controlled actual injection, not merely a mocked function | NOT RUN | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C08 | Observable effects from the intended target | NOT RUN | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C09 | Real metrics, logs, traces or application evidence appropriate to the scenario | NOT RUN | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C10 | Incident/diagnosis outcome, including abstention when evidence is insufficient | NOT RUN | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C11 | Clearly attributed recovery or containment mechanism | NOT RUN | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C12 | Safe cleanup and restoration | NOT RUN | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C13 | Independent postcondition verification | NOT RUN | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C14 | Preserved failures, aborts and uncertainty | PARTIAL | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| C15 | Complete run identity and evidence references | PARTIAL | Six fixed source contracts/adapters and protocol exist. Zero real M6 fault trials; universal per-scenario acceptance is not established. |
| D01 | Experiments run only in the approved local k3d-opsproof environment | PARTIAL | Explicit isolated cluster identity checked for startup/maintenance; source guards exist. No actual fault dispatch. |
| D02 | Explicit kubeconfig and expected Kubernetes API-server identity are verified before mutation | PARTIAL | Explicit isolated cluster identity checked for startup/maintenance; source guards exist. No actual fault dispatch. |
| D03 | Existing M5 workloads, GitOps and dependencies are healthy before trials | BLOCKED | Initial startup readiness failed on stale API allowlists; controller recovered after repair, but full fresh M6 baseline was not accepted. |
| D04 | Available host RAM, CPU and disk meet the recorded resource preflight | BLOCKED | Startup floor initially passed; sustained active-stack trial headroom failed and emergency floor halted optional UI profile. |
| D05 | New M6 images have identifiable source revisions and immutable image digests | PARTIAL | Final content hashes and exact local image IDs captured; images unpushed and undeployed, no registry manifest digest claimed. |
| D06 | M6 configuration is deployed through the intended ownership mechanism, without unmanaged drift | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D07 | Experiments do not affect unrelated workloads, databases or namespaces | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D08 | No two conflicting faults run simultaneously | PARTIAL | Reservation, abort/cleanup and stale-evidence logic tested offline/SQL. Actual cluster enforcement remains unproven. |
| D09 | Every experiment has an available abort and cleanup mechanism | PARTIAL | Reservation, abort/cleanup and stale-evidence logic tested offline/SQL. Actual cluster enforcement remains unproven. |
| D10 | Final application state is verified after each experiment | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D11 | Prometheus contains actual relevant metrics with trustworthy timestamps | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D12 | Loki contains relevant application/worker log observations | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D13 | Tempo contains relevant client/server or service traces where applicable | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D14 | Alerts and incidents correctly distinguish firing, active and resolved states | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D15 | Missing or stale telemetry is recognized rather than accepted as healthy | PARTIAL | Reservation, abort/cleanup and stale-evidence logic tested offline/SQL. Actual cluster enforcement remains unproven. |
| D16 | Incident observations link to the correct trial and workload | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D17 | The experiment records real detection and recovery event times | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| D18 | Verification observes current workload health, not merely an earlier cached result | BLOCKED | No live M6 trial/deployment acceptance. Active-stack memory failed; existing cluster restored to stopped state. |
| E01 | Real k6 is executed, not just JavaScript syntax-checked | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E02 | Test parameters are declared before execution | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E03 | Only the approved demo workload receives test traffic | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E04 | Load generation has bounded arrival rate, users, duration and job count | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E05 | Every run uses a unique run ID | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E06 | k6 receipts and summary files are retained | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E07 | Submitted IDs are independently reconciled against actual durable job outcomes | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E08 | Failed, missing or duplicate receipts cannot be silently counted as successes | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E09 | Resource exhaustion terminates the load safely | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E10 | The runner closes its owned port-forward and preserves failure logs | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E11 | Same job count, job duration, HTTP background-load profile and measurement methodology | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E12 | Same underlying application revision and load-script identity | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E13 | Separate unique timestamps and trial identities | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E14 | Correct fixed-worker, API-HPA and worker-KEDA configurations | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E15 | Autoscalers do not compete for ownership of the same target | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E16 | Actual desired/available replica observations captured | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E17 | CPU and RAM observations captured | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E18 | Every submitted job is identified and reconciled | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E19 | Clean comparison trials contain no unexplained failures or retries | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| E20 | Successful, failed and aborted trials remain distinguishable | NOT RUN | Runner/contracts have source tests only. Real k6: 0; comparable capacity trials: 0/9. No performance claim. |
| F01 | A deterministic diagnosis baseline is tested | VERIFIED LOCAL | Versioned synthetic dataset, strict schemas and conservative deterministic checks; advisory-only authority. No real model result. |
| F02 | A versioned labeled evaluation dataset exists | VERIFIED LOCAL | Versioned synthetic dataset, strict schemas and conservative deterministic checks; advisory-only authority. No real model result. |
| F03 | Initial synthetic cases cover recognizable faults, unknowns and abstentions | VERIFIED LOCAL | Versioned synthetic dataset, strict schemas and conservative deterministic checks; advisory-only authority. No real model result. |
| F04 | Additional held-out cases are built from actual recorded M6 faults | BLOCKED | No recorded live faults for held-out cases and no independent ground-truth review. |
| F05 | Ground truth is independently authored and reviewed | BLOCKED | No recorded live faults for held-out cases and no independent ground-truth review. |
| F06 | The evaluated model does not receive scenario labels or injection metadata revealing the answer | BLOCKED | Synthetic safeguards exist; real provider qualification/comparison is disabled by user instruction. No paid calls or usage/cost result. |
| F07 | Predictions use a constrained structured schema | VERIFIED LOCAL | Versioned synthetic dataset, strict schemas and conservative deterministic checks; advisory-only authority. No real model result. |
| F08 | Missing/stale/contradictory evidence causes appropriate abstention | VERIFIED LOCAL | Versioned synthetic dataset, strict schemas and conservative deterministic checks; advisory-only authority. No real model result. |
| F09 | Unsupported assertions and unsafe recommendations are identified | BLOCKED | Synthetic safeguards exist; real provider qualification/comparison is disabled by user instruction. No paid calls or usage/cost result. |
| F10 | Real model errors, malformed responses and incomplete outputs are counted | BLOCKED | Synthetic safeguards exist; real provider qualification/comparison is disabled by user instruction. No paid calls or usage/cost result. |
| F11 | Latency, token usage and costs are recorded where available | BLOCKED | Synthetic safeguards exist; real provider qualification/comparison is disabled by user instruction. No paid calls or usage/cost result. |
| F12 | Candidate and comparator results are reported against the same applicable evaluation criteria | BLOCKED | Synthetic safeguards exist; real provider qualification/comparison is disabled by user instruction. No paid calls or usage/cost result. |
| F13 | AI has no permission to approve or perform a recovery action | VERIFIED LOCAL | Versioned synthetic dataset, strict schemas and conservative deterministic checks; advisory-only authority. No real model result. |
| F14 | A model that fails safety qualification remains disabled or advisory-only | VERIFIED LOCAL | Versioned synthetic dataset, strict schemas and conservative deterministic checks; advisory-only authority. No real model result. |
| F15 | At least one additional independent compatible test workload is deployed | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F16 | Deployment uses the intended reusable configuration/Helm contract | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F17 | The second workload is actually Ready and accessible through its intended internal interface | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F18 | OpsProof collects real health and operational observations from it | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F19 | An investigation uses genuine observations from the second workload | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F20 | Both workloads retain separate identity, state and authorization boundaries | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F21 | Unsupported recovery actions against the second workload are rejected | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F22 | Reuse does not require duplicating or rebuilding the entire control plane | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F23 | The second workload operates within the recorded local resource budget | BLOCKED | Reuse chart and read-only observer source implemented/tested; no second-workload deployment or genuine investigation. |
| F24 | Record baseline container-image size, build and relevant runtime measurements | PARTIAL | Actual image size/build/package inventories captured; comparable deployed runtime baseline is absent. |
| F25 | Evaluate Dockerfile and dependency optimizations without removing required functionality | VERIFIED LOCAL | Final exact-ID image smoke/scan evidence retained; locked app dependencies and security features preserved. Open CVEs are disclosed. |
| F26 | Preserve image identity and security-scanning evidence | VERIFIED LOCAL | Final exact-ID image smoke/scan evidence retained; locked app dependencies and security features preserved. Open CVEs are disclosed. |
| F27 | Compare before/after measurements under comparable conditions | BLOCKED | No comparable runtime/scaling trials; no measured optimization gain or savings claim. |
| F28 | Measure resource usage and scaling behavior relevant to cost | BLOCKED | No comparable runtime/scaling trials; no measured optimization gain or savings claim. |
| F29 | Estimate fixed-capacity versus scale-to-demand tradeoffs | BLOCKED | No comparable runtime/scaling trials; no measured optimization gain or savings claim. |
| F30 | Prepare an AWS cost model using current region-specific pricing and stated assumptions | VERIFIED LOCAL | Fresh public Mumbai price rows and explicit illustrative model; no actual spend, AWS provisioning or credits assumed. |
| F31 | Include major likely cloud costs such as EKS, compute, storage, networking, IPv4 and logging | VERIFIED LOCAL | Fresh public Mumbai price rows and explicit illustrative model; no actual spend, AWS provisioning or credits assumed. |
| F32 | Clearly distinguish modeled costs, credits and actual spending | VERIFIED LOCAL | Fresh public Mumbai price rows and explicit illustrative model; no actual spend, AWS provisioning or credits assumed. |
| F33 | Document optimization tradeoffs and limitations | VERIFIED LOCAL | Fresh public Mumbai price rows and explicit illustrative model; no actual spend, AWS provisioning or credits assumed. |
| G01 | Operator authentication is enforced on protected endpoints | VERIFIED LOCAL | Actual isolated API auth/CSRF tests pass; existing protected endpoints retained. |
| G02 | CSRF protection is verified for applicable browser-authenticated mutations | VERIFIED LOCAL | Actual isolated API auth/CSRF tests pass; existing protected endpoints retained. |
| G03 | Invalid, expired, replayed and unauthorized approvals are rejected | PARTIAL | Malformed, expired, stale-fence and replay denial tested; complete live unauthorized actuator behavior remains open. |
| G04 | Kubernetes ServiceAccounts follow least privilege | BLOCKED | Restricted deployed fault authority and actual RBAC/NetworkPolicy negative tests are incomplete. Chart rendering is insufficient. |
| G05 | Fault-execution permissions are restricted to approved resources and operations | BLOCKED | Restricted deployed fault authority and actual RBAC/NetworkPolicy negative tests are incomplete. Chart rendering is insufficient. |
| G06 | API and evidence workers cannot perform arbitrary Kubernetes mutations | BLOCKED | Restricted deployed fault authority and actual RBAC/NetworkPolicy negative tests are incomplete. Chart rendering is insufficient. |
| G07 | NetworkPolicy restrictions are actually enforced where claimed | BLOCKED | Restricted deployed fault authority and actual RBAC/NetworkPolicy negative tests are incomplete. Chart rendering is insufficient. |
| G08 | Experimental configuration is disabled by default | VERIFIED LOCAL | Defaults off, strict fixed inputs/no arbitrary shell or URL authority, and preserved M4/M5 regression results. |
| G09 | Security-sensitive configuration cannot be changed through arbitrary user-supplied URLs, namespaces or shell commands | VERIFIED LOCAL | Defaults off, strict fixed inputs/no arbitrary shell or URL authority, and preserved M4/M5 regression results. |
| G10 | Kubernetes Pod security, nonroot execution and credential exposure are reviewed | PARTIAL | Nonroot/read-only/no-capability image smoke tests and chart review pass; deployed credential/Pod-security proof remains open. |
| G11 | Existing M4/M5 recovery security tests still pass | VERIFIED LOCAL | Defaults off, strict fixed inputs/no arbitrary shell or URL authority, and preserved M4/M5 regression results. |
| G12 | Source and container security scans are performed and findings reviewed | PARTIAL | Actual source and exact-image scans performed; 47 high package findings per Python image remain unresolved. No clean-security claim. |
| G13 | Failure, timeout and uncertain-operation paths do not grant additional authority | PARTIAL | Failure/uncertainty guards tested in SQL; live least-privilege and crash paths unproven. |
| G14 | No test leaves unauthorized or uncontrolled fault resources active | VERIFIED LOCAL | No M6 fault dispatched. Owned test containers removed, UI desired counts restored, existing cluster stopped; no final readiness claim. |
| G15 | M6 trial information is connected to actual API and database records | VERIFIED LOCAL | Actual isolated FastAPI/PostgreSQL trial read and event history verified by browser test. |
| G16 | Operators can inspect trial identity, status, scenario, target and event timeline | VERIFIED LOCAL | Actual isolated FastAPI/PostgreSQL trial read and event history verified by browser test. |
| G17 | Experiment detail views show real observations and evidence references | PARTIAL | Trial details and distinct outcome types exist; no genuine live fault artifacts or full deployed lifecycle demonstrated. |
| G18 | Outcomes distinguish succeeded, failed, aborted, indeterminate and blocked where applicable | PARTIAL | Trial details and distinct outcome types exist; no genuine live fault artifacts or full deployed lifecycle demonstrated. |
| G19 | Missing data is presented as unavailable or unknown, not invented | VERIFIED LOCAL | Frontend unit/build plus actual desktop/mobile/accessibility browser checks; backend policy remains required. Bounded isolated scope. |
| G20 | Recovery, experiment and approval controls remain clearly separated | VERIFIED LOCAL | Frontend unit/build plus actual desktop/mobile/accessibility browser checks; backend policy remains required. Bounded isolated scope. |
| G21 | Navigation works on desktop and mobile | VERIFIED LOCAL | Frontend unit/build plus actual desktop/mobile/accessibility browser checks; backend policy remains required. Bounded isolated scope. |
| G22 | Loading, empty, unauthorized and API-error states are handled | VERIFIED LOCAL | Frontend unit/build plus actual desktop/mobile/accessibility browser checks; backend policy remains required. Bounded isolated scope. |
| G23 | Relevant Vitest, Playwright and accessibility tests pass | VERIFIED LOCAL | Frontend unit/build plus actual desktop/mobile/accessibility browser checks; backend policy remains required. Bounded isolated scope. |
| G24 | No unsafe operational action is exposed without the required backend policy and operator authorization | VERIFIED LOCAL | Frontend unit/build plus actual desktop/mobile/accessibility browser checks; backend policy remains required. Bounded isolated scope. |
| G25 | Exact Git commit and working-tree state | VERIFIED LOCAL | Dirty source file hashes, exact local image IDs/config records and unique UTC verification runs retained. Not a committed release. |
| G26 | Container image digests and configuration identities | VERIFIED LOCAL | Dirty source file hashes, exact local image IDs/config records and unique UTC verification runs retained. Not a committed release. |
| G27 | Unique run IDs and UTC timestamps | VERIFIED LOCAL | Dirty source file hashes, exact local image IDs/config records and unique UTC verification runs retained. Not a committed release. |
| G28 | Preflight and known-good baseline | PARTIAL | Actual startup/maintenance/resource records retained; no accepted known-good live-trial baseline. |
| G29 | Fault-injection records and bounded execution parameters | NOT RUN | No actual M6 injection, trial telemetry, exact live job outcomes or related controller events. |
| G30 | Relevant raw metrics, logs and traces | NOT RUN | No actual M6 injection, trial telemetry, exact live job outcomes or related controller events. |
| G31 | Exact database and Redis job outcomes | NOT RUN | No actual M6 injection, trial telemetry, exact live job outcomes or related controller events. |
| G32 | Controller, Kubernetes and GitOps events where relevant | NOT RUN | No actual M6 injection, trial telemetry, exact live job outcomes or related controller events. |
| G33 | Authorization and policy decisions | PARTIAL | SQL/API authorization and independent-process verifier source tested; no independent live trial verification. |
| G34 | Independent verification results | PARTIAL | SQL/API authorization and independent-process verifier source tested; no independent live trial verification. |
| G35 | Cleanup and final service-health verification | PARTIAL | Disposable cleanup and original replica restoration recorded; final running application health not verified before stop. |
| G36 | Failed, aborted and indeterminate attempts | PARTIAL | Failed source/security/browser attempts and resource-blocked startup/profile records retained; no injected trial attempts. |
| G37 | Benchmark source files and unmodified raw measurements | PARTIAL | Benchmark source preserved/hardened; no raw real k6/capacity measurement. |
| G38 | AI evaluation datasets, results and limitations | PARTIAL | Synthetic deterministic dataset/results retained; held-out and real model results absent by explicit restriction. |
| G39 | Second-workload verification evidence | NOT RUN | No runtime second-workload verification. |
| G40 | Performance and FinOps calculations | PARTIAL | Explicit FinOps calculations retained; real performance/scaling evidence absent. |
| G41 | SHA-256 manifest for the selected evidence artifacts | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G42 | Secret redaction and public/private evidence classification | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G43 | Another engineer can identify the exact source and dependency versions | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G44 | Prerequisites and Windows Git Bash commands are documented | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G45 | Test commands explain their purpose, options and expected outcomes | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G46 | Test data and resource limits are explicitly bounded | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G47 | Positive, negative and failure tests have retained outputs | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G48 | Recovery and cleanup procedures are documented | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G49 | Known limitations and deviations from the original plan are recorded | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G50 | M6 results can be reproduced without requiring AWS | PARTIAL | Delivered checks and source-copy reproduction use no AWS account; complete M6 cannot yet be reproduced because live gates remain open. |
| G51 | Temporary local test resources can be safely removed | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G52 | Existing M5 evidence and persistent data remain preserved | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G53 | The final acceptance report links every claim to actual evidence | VERIFIED LOCAL | See selected evidence manifest, source inventory/reconciliation, verification runbook and report. Applies to delivered local work, not missing live evidence. |
| G54 | An independent review confirms that documented claims do not exceed the evidence | BLOCKED | No independent final reviewer has accepted this changed implementation; this report is the implementing agent's evidence assessment. |
