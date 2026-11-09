> Historical checkpoint. See [the November 9 report](M5_ACCEPTANCE_REPORT_2026-11-09.md) for current results.

# Milestone 5 implementation and acceptance report

Date: November 7, 2026 (Asia/Calcutta).

**Decision: M5 NOT YET COMPLETE. Live foundation and Gateway verification now pass. The earlier source-only assessment below is historical; see the latest live-validation addendum at the end. Remaining controller/recovery gates are still in progress.**

## Scope and provenance

The user requested analysis, implementation, verification, validation, and an acceptance report. The three supplied documents were treated as requirements and proposed implementation material; their historical claims were not counted as results from this machine.

Base commit: `e28100da67d73268801c327c24f7228b2f1ff3ed`. Changes remain local and uncommitted. The tested working files are individually SHA-256 recorded in [source-validation.json](../../.runtime/m5/acceptance/source-validation.json). This distinguishes the dirty working tree from the M4 commit. No remote CI result is claimed.

User-selected origin: `https://github.com/Aoun62336/OpsProof.git`, now configured locally. Read-only `git ls-remote` succeeded with **no refs**. The remote is reachable but has no deployable revision. No push occurred.

| Input | SHA-256 |
|---|---|
| M5 criteria.txt | `420df2e66d47fb9da5f69cad1066720e3519ac5e4d1175cdd1aef0f8a1e7846a` |
| OPSPROOF_M5_STAGE1_TO_4_EDITOR_READY.md | `7b5f6df1099fb028cc369298c338826cbc04adbded0b7f6c43cda385e97806da` |
| M5_K3D_HELM_FOUNDATION.md | `3ec10f58f5f28c862d55d0cc7f23e63ee5a3205852061c1f07f96362b8744780` |

## Implemented and corrected

All 30 proposed files were added after confirming their paths did not contain newer M5 implementations. Existing M4 application behavior was preserved. Additional work includes:

- Resource/tool preflight with separate exit codes and measured RAM/disk evidence; bootstrap refuses unmet gates and existing clusters.
- Isolated `.runtime/m5/kubeconfig.yaml`, explicit `k3d-opsproof` context, and loopback API validation. The inspected default context points to AWS EKS. No AWS API requests or mutations were performed.
- Sequential dependency/application deployment helper, local content-derived image tags, image identity records, and an Argo ownership conflict guard. Deployment helper is source-validated, not live-accepted.
- Smoke helper owns both Kubernetes port forwards, rejects occupied ports, verifies five distinct exact jobs independently, and clears stale success evidence before starting a new trial.
- Actual Helm lint/render checks covering role credential boundaries, restricted Pod configuration, resource limits, private application services, and autoscaler ownership. HPA/KEDA targets omit fixed `spec.replicas` when autoscaling is enabled.
- GitOps URL validation at the callable boundary, explicit resource-kind allowlist excluding Secrets/RBAC, and removal of blanket HTTPRoute drift exclusions. Reachability is a separate gate; a syntactically valid SHA is not proof of remote availability.
- Production Nginx build, explicit writable temporary paths, web Pod fsGroup, and pinned observed base/dependency digests.
- Traefik 42.3.0 corrections: `accessLog` replaces rejected `logs`; `service.spec.type` replaces ineffective `service.type`. The rendered service is now NodePort 30080, not LoadBalancer. Added controller resource requests/limits.
- Configurable Playwright base URL to target the real gateway in later tests.
- Foundation CI workflow for unit contracts, Helm render/security contracts, and the pinned upstream gateway chart. This is not yet the complete M5 security/CI pipeline.
- Updated local-execution runbooks and source verification scripts.

## Actual local results

| Check | Observed result | Evidence / limitation |
|---|---|---|
| Demo regression | 23 passed | `demo-tests.log`; one existing Starlette deprecation warning |
| Control regression | 113 passed | `control-tests.log` |
| M5 boundary/evidence tests | 15 passed | `m5-tests.log`; mocked HTTP negative cases are unit tests, not cluster smoke |
| Frontend lint | Exit 0 | `web-lint.log` |
| Frontend unit tests | 4 passed | `web-test.log` |
| Production frontend build | Exit 0 | `web-build.log` |
| Own Helm charts | 7 configurations, 50 objects pass | `chart-contracts.json`; real Helm, offline policy contracts |
| Upstream Traefik | 8 objects pass chart schema and exposure assertions | `gateway-contracts.json`, `traefik-render.yaml` |
| Argo CD version lookup | Chart 10.14.0 exists, appVersion v3.6.1 | Official Helm repository lookup; supplied 3.5 compatibility statement needs revision |
| Python lint | Pass after fixes | Ruff against `scripts/m5` |
| Image builds | All three pass | `images.json` and individual build logs |
| Restricted Nginx configuration | Exit 0 after correction | `nginx-config-test.log`; read-only rootfs, UID 101, 64 MiB cap, writable `/tmp` |
| Browser login accessibility | One assertion passed; runner interrupted during shutdown | Diagnostic only, **not an accepted full browser run**; backend unavailable |
| Whitespace | Exit 0 | `diff-check.log` |
| Cluster bootstrap | Correctly blocked before creation | Resource gate below |

Logs above are in [the acceptance evidence directory](../../.runtime/m5/acceptance). Source checks retain each command's exit code so an earlier failure cannot be hidden by a later successful command. Kubernetes API schema admission, NetworkPolicy enforcement and live controller behavior remain untested.

### Images actually built

| Local image | Observed image identity | Build |
|---|---|---|
| `opsproof-demo:m5-28e38598d58c34ae410f1294` | `sha256:e3acdffa5230e6543d614b5c459c97901f0cb7988e670f6aa7d7eb707a062222` | Pass |
| `opsproof-control:m5-28e38598d58c34ae410f1294` | `sha256:69c9c5135e314a142f04290d5e608da35135490bd2a8de54d8caec8a97f5cfc9` | Pass |
| `opsproof-web:m5-foundation-verified` | `sha256:db24d03a66b1550944c4ccbd0bb1bd52a06f9a9412c49fa7d856b645861b417b` | Pass |

These image identities are local build evidence, not stable/canary release evidence. The content-derived demo/control tag identifies the build-time source; subsequent infrastructure-only corrections do not imply that tag identifies the final entire repository. The web tag is a local diagnostic tag, not a GitOps release tag. Deployment must record the final revision and image identities together.

## Mandatory acceptance checklist

No box is checked merely because source exists.

| Gate | Required acceptance criteria from the TXT | Status and observed evidence | Still required |
|---|---|---|---|
| 0: M4 baseline | Corrected demo/control tests; frontend lint/unit/build/browser; real telemetry and approved M4 recovery | **Partial**: 23 + 113 backend and 4 frontend tests pass; lint/build pass | Full browser exit 0, real telemetry verification, recovery run ID on the tested deployment |
| 1: Foundation/resources | Pinned cluster Ready; measured RAM/disk; bootstrap and safe cleanup tested | **Blocked**: tools/resources recorded, gate refuses low RAM; no cluster exists | Adequate memory, Ready node, storage class, measured bootstrap, separately authorized cleanup trial with preserved backups |
| 2: Helm/security | Real services in both namespaces; separate PostgreSQL/Redis; migrations/PVC persistence; five-job smoke; secrets/PSA/network/RBAC tests | **Source partial, runtime pending**: charts and secrets contracts pass; images build | Install, migration records, Pods/PVCs, actual five-ID smoke JSON, controlled persistence restart, live enforcement/denial checks |
| 3: Gateway | Frontend/API HTTP; Accepted/ResolvedRefs; login/CSRF/logout; private storage/actuators | **Source partial, runtime pending**: upstream chart corrected and rendered; Nginx restricted config passes | Install pinned CRDs/controller, route conditions, real HTTP/browser/security results |
| 4: GitOps | Approved reachable revision; Git change -> cluster change; observed drift correction; missing Secret/sync error recovery without data loss | **Blocked / partial source**: generator and permissions contracts pass; origin reachable but empty | Publish tested revision after review, install controller, explicit Helm-to-Argo adoption, actual synchronization/drift/failure trials |
| 5: Rollouts | Distinct healthy promotion; faulty image measurable failure; analysis abort/rollback; independent stable digest/routing/health | **Not implemented or run** | Verified telemetry baseline, pinned checksum-verified router plugin/controller, Rollout/Services/route/analysis, three image identities and real trials |
| 6: HPA/KEDA | Valid CPU/Redis metrics; bounded load scale-out/in; queue integrity; comparable fixed/scaled measurements | **Templates only; not accepted**: disabled by default, separate lag and pending metrics, replica ownership fixed | Controllers/metrics health, baseline-driven safe load, time series, exact durable outcomes, throughput/latency/resources and comparable trials |
| 7: Recovery/UI/CI/docs | Approved narrow Kubernetes operation; unauthorized/expired/stale/replayed fail closed; independent restoration proof; real-data UI/accessibility; security CI; runbooks/evidence | **Partial foundation only**: source CI/runbooks added, existing M4 preserved | New typed operation and execution-time policy, scoped RBAC, independent verifier, full denial matrix, real Workloads/Deployments/Capacity views, complete security CI and hosted results |

## Required experiment evidence inventory

| Required record | Present? | What it must establish |
|---|---|---|
| Source/tool/resource evidence | Yes, preflight and source ledger | Exact base/source hashes, tool versions, RAM/disk, command exit codes |
| Kubernetes five-job experiment | No | Five exact durable IDs, independent completed reads, successful experiment and verified events |
| Database/Redis persistence | No | Controlled Pod restart preserves state and acknowledged work |
| Gateway access | No | Real HTTP routing, auth/CSRF/logout, internal boundary denials |
| GitOps trial | No | Remote SHA, desired/live change, drift and reconciliation, failed sync recovery |
| Healthy rollout | No | Distinct candidate digest, analysis success, promotion and actual routing |
| Faulty rollout | No | Faulty digest, measured errors, failed analysis, abort and stable restoration |
| Scaling trials | No | Declared identical load, trials/failures, fixed/HPA/KEDA time series, lag/pending, exact job integrity, throughput/latency/resource use |
| Kubernetes recovery trial | No | Incident/run/approval IDs, exact authorized target, acknowledgment and independently verified restoration |
| Kubernetes security trials | No | Unauthorized, expired, stale, replayed, unsupported target, missing credential/metrics, RBAC and indeterminate outcomes |
| Runtime observability | No | Queryable real metrics, logs, traces and incident transitions for this deployment |
| Full browser/security/CI results | No | Final-source API-backed browser/accessibility results, relevant security scans and hosted CI logs |
| Minimum/full profile resources | Preflight only | Actual sustained runtime RAM/CPU/disk for each tested profile |

No screenshots or old M4 results were substituted for missing M5 experiments.

## Current blockers and next executable sequence

Latest resource sample: `2026-11-07T11:01:59.088745+00:00` UTC. Host free RAM **3.30 GiB**, below the adopted **5 GiB** foundation gate; disk free **302.89 GiB**, above the **15 GiB** gate. Docker reports approximately 7.76 GiB available to its VM. There were no running Compose services at initial inspection. The failed gate is host memory, not disk or missing tooling. The resource thresholds are the supplied provisional foundation requirements; a full controller profile still needs measurement.

1. Free host memory by closing unused applications, then run `python scripts/m5/preflight.py`. Do not silently lower the threshold or stop unrelated processes.
2. Once it passes, run `python scripts/m5/bootstrap.py`, then `python scripts/m5/deploy_foundation.py`. These are local-only. Inspect storage, migrations and workload health; retain logs and events.
3. Run `python scripts/m5/smoke.py`. Prove persistence, PSA and network/RBAC restrictions before treating Gate 2 as passed.
4. Install the verified pinned Gateway components using the isolated kubeconfig and run real routing/session/security/browser checks. Use `OPSPROOF_E2E_BASE_URL=http://127.0.0.1:8081` for the gateway browser suite.
5. Prepare and review the actual tested Git revision for the supplied empty repository. Publish that concrete revision, then prove Argo access and perform explicit ownership cutover. Do not infer independent Application ordering from sync-wave annotations alone.
6. Implement and measure Rollouts, autoscaling and restricted Kubernetes recovery using the actual runtime/telemetry baseline. Thresholds and recovery preconditions cannot be claimed validated from source templates.
7. Complete real-data UI, full security/CI checks and every trial above; update this report only from saved observations.

Cleanup has not been executed. No data/PVC deletion, cloud provisioning, paid AI calls, or remote publication was performed. The deliverable is a verified foundation with explicit blockers, **not a completed Milestone 5**.

## Primary references checked

- [Kubernetes HPA ownership guidance](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/) supports omitting declared replicas when autoscaling owns them.
- [k3d config documentation](https://k3d.io/stable/usage/configfile/) documents disabling default kubeconfig updates/context switching.
- [KEDA Redis Streams source](https://github.com/kedacore/keda/blob/main/pkg/scalers/redis_streams_scaler.go) distinguishes lag and pending-entry trigger configuration.
- [Argo CD Helm hook documentation](https://github.com/argoproj/argo-cd/blob/master/docs/user-guide/helm.md) maps pre-install/pre-upgrade hooks to PreSync. This does not prove dependency health across separate Applications.
- Traefik 42.3.0 and Argo CD 10.14.0 were also checked directly through their official Helm repositories. Actual chart defaults, schema and rendered resources took precedence over assumptions in the supplied documents.

## Resumption check ? November 7, 2026

At `2026-11-07T11:11:12.987890+00:00` UTC, free host RAM measured **4.32 GiB**, still below the 5 GiB gate (shortfall **0.68 GiB**). Docker had no running containers. Docker VM filesystem buffers were synced and reclaimable cache released; no files, volumes, applications, or services were deleted/stopped. WSL subsequently returned some RAM to Windows. No leftover OpsProof Node test servers were found.

Live cluster creation remains blocked pending additional free host memory. The user has been asked to close unused applications or select another machine. No additional acceptance gate is marked passed, and no remote publication occurred.

## Latest live-validation addendum

After the user closed unused apps, host free RAM reached 5.36 GiB and preflight passed.
The local k3d cluster is now Ready on Kubernetes v1.35.5+k3s1. First bootstrap exceeded
the supplied 120-second image-download timeout; a verified empty-cluster retry with
600 seconds succeeded. All demo/control services, migrations and four PVCs are live.

- Five-job Kubernetes smoke passed both before and after enforcing NetworkPolicies.
  Latest run ID: `ea7e5e3a-d087-4115-9349-53e4e207b957`; exact IDs and statuses are in
  `.runtime/m5/k3d-smoke.json`.
- 26 live foundation security checks passed: 21 RBAC denials, privileged Pod admission
  rejection, three required connections, and foreign-database access changing from
  permitted to denied after policy installation. See `k8s-foundation-security.json`.
- All four PostgreSQL/Redis Pods were replaced with unchanged PVC UIDs. Redis markers,
  five completed jobs, experiment success and exactly one verified event survived.
  See `persistence.json`. No volumes or business records were deleted.
- Traefik Gateway and HTTPRoute current-generation conditions passed; 12 real HTTP/auth
  checks passed, including CSRF and revoked-session replay. See `gateway-http.json`.
- All eight Playwright browser/accessibility tests passed through port 8081 with exit 0.
  See `gateway-browser.log`.
- Observed Kubernetes node usage after gateway deployment: 353m CPU, 1568 MiB RAM.
  This is a runtime sample, not the full-profile capacity acceptance result.
- Argo CD 10.14.0 installed successfully with no cluster-wide Role/RoleBinding grants
  and controller write access limited to three application namespaces.
- User requested keeping all changes local. No GitHub push will occur. A read-only
  in-cluster Git server is being prepared for local GitOps reconciliation trials;
  GitHub-hosted CI remains unverified.

The Windows smoke helper was corrected to terminate its owned Chocolatey wrapper and
child process tree, avoiding stale kubectl port forwards. The repeated live smoke passed.
The earlier memory blocker is resolved; do not use the historical source-only table
as the current runtime status. Full M5 completion still requires GitOps/rollout/scaling,
new restricted recovery, telemetry, UI extensions and final evidence.
