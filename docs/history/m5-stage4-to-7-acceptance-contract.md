> Historical record. Commands, paths and results below describe the recorded revision. See [the current repository guide](../../README.md) for maintained commands and status.

# OpsProof Milestone 5 | Stages 4–7 detailed implementation and acceptance contract

**Status: requirements and interfaces specified, not implementation acceptance.** Do not fabricate or bypass prerequisites. This document accompanies prepared Stage 1–3 source. Existing M4 code remains the baseline.

## Stage 4: Argo CD GitOps

### Source and prerequisites

- Current source: `scripts/m5/render_gitops.py`, which emits a tightly scoped AppProject and five Application objects from the **actual** Git remote and full already-pushed revision. It never pushes, provisions or modifies the cluster.
- Add audited Helm chart values for a pinned Argo CD 3.5 compatible release, with local resource limits, minimal replicas and no publicly exposed UI. Dedicated `argocd` namespace.
- Before sync, reconcile manually managed Helm releases with Argo-owned resources. The same resource must not be independently managed by `helm upgrade` and Argo CD. Never prune PVCs or local secrets.
- Secrets are created out-of-band from `.env` and must be refreshed safely; Argo never stores raw credentials in Git.
- Source repos must be allowlisted; private repo access requires reviewed read-only credential, not a deploy key with write access.
- Bootstrap CRDs/controllers explicitly, pin image/chart versions, document upgrade and teardown.

### Verification

1. Argo CD can access the exact remote Git SHA and Helm values without resolving `latest`.
2. Initial sync yields healthy Pods and the M5 bounded queue-burst experiment passes.
3. An approved Git change produces a corresponding observed live-state change with matching revision.
4. Make a **non-destructive** unapproved drift in a test-only resource and observe configured self-healing.
5. Prove the app correctly reports missing Secrets/out-of-sync rather than false green; recover without deleting state.
6. Capture controller events, resource diffs, SHA, image digests and the terminal state. Do not claim GitOps from a static manifest.

## Stage 5: Argo Rollouts, Gateway API plugin and bad release

### Implementation requirements

- Install a pinned Argo Rollouts version and the compatible **pinned + checksum-verified** Gateway API traffic-router plugin. Do not use an unverified remote binary at runtime.
- Prove Traefik Gateway API and Argo Rollouts plugin can write only specific allowlisted HTTPRoute backend weights. Use a namespaced Role/RoleBinding for controller traffic routing wherever supported; avoid a blanket cluster-wide HTTPRoute write grant.
- Evolve the actual demonstration API deployment to a Rollout while keeping a stable internal target (`demo-api`) for the control plane, not an arbitrary external sample.
- Release artifacts must have distinct image digests for stable, healthy candidate and intentionally failing candidate. A changed ConfigMap or an artificial screenshot alone does not satisfy the frozen faulty-release requirement.
- Add stable and canary Services, a controlled HTTPRoute, matching Rollout strategy and Prometheus AnalysisTemplate. Determine real failure/latency thresholds using a known baseline, and make every analysis query valid for the configured service/job labels.
- Keep Argo CD from fighting Rollouts-managed weights using narrowly scoped `ignoreDifferences`. Never ignore entire routes or workloads.
- The rollouts controller can automatically abort a bad release; OpsProof observes and independently verifies that outcome. Do not credit an autonomous Rollouts abort to the M4 operator-approved action worker.

### Verification

1. Show a successful promotion with distinct candidate digest and clean analysis.
2. Introduce a known bad image under the same measured route, capture real failed requests and Prometheus analysis failures.
3. Prove controller-triggered abort, final stable image/revision, actual healthy responses and the correct HTTPRoute weights.
4. Confirm stored incident/evidence traces and that no database volume or job history is lost.
5. Test unsupported traffic-router state and missing metrics fail closed or remain indeterminate, never claim fabricated weighted traffic.

## Stage 6: HPA, KEDA and workload capacity

### Implementation requirements

- Existing source: `infra/helm/opsproof-services/templates/autoscaling.yaml`, OFF by default. HPA targets API only. KEDA targets demo worker only, so the two do not compete for the same Deployment.
- Install pinned KEDA/metrics-server versions compatible with the actual k3s cluster. Verify CRDs and external metrics API health.
- Redis Streams queue uses `opsproof:jobs` and consumer group `opsproof-workers`. Consumer-group lag counts undelivered messages; PEL pending counts delivered but unacknowledged work. The prepared ScaledObject uses both KEDA trigger types to avoid treating only `XLEN` as work. Verify with actual XINFO GROUPS, XPENDING, XAUTOCLAIM and completed-job records.
- Keep min replicas 1 to preserve consumer readiness; cap max replicas at a measured safe value (initially 3) for a 16 GB laptop. Avoid autoscaling to 0 until group semantics, boot time and draining are validated.
- Predeclare an identical load shape for fixed replica, HPA and KEDA trials, including workload count, job duration, target CPU, warmup, abort ceiling and cooldown. Keep failure records.

### Verification

1. ScaledObject and HPA objects are healthy and can read actual metrics.
2. Measure scale-out, scale-in, worker count and consumer identities under equivalent generated work.
3. Confirm all exact IDs reach a durable terminal state without double completion, including interrupted consumers and pending work.
4. Capture queue lag, pending, completed throughput, p50/p95 job latency (if sample size supports), CPU/RAM and time series.
5. Demonstrate an HPA resource-driven change on a suitable target; do not infer autoscaling from configured YAML.

## Stage 7: Restricted Kubernetes recovery, UI, CI and M5 release gate

### Safety design

- M4 action worker currently owns only `resume_demo_worker` through the fixed demo HTTP endpoint. Preserve that contract. Do not give it generic `kubectl`, Docker socket, shell execution, arbitrary selectors or cluster-admin.
- After selecting exactly one justified supported Kubernetes operation, define a **separate typed runbook contract** with fixed namespace, target kind/name, preconditions, risk, expiring explicit approval, bounded parameters and idempotency key.
- Add a new durable schema migration if and only if required for action type and audit metadata. Never rewrite old migrations.
- Implement a namespace-scoped ServiceAccount with get/patch privileges for the specific resource and no secret read/list, no pod exec, no role binding changes, no job creation or arbitrary resource access. Confirm the chosen API/RBAC scope supports the fixed operation (resourceNames restrictions vary by verb and subresource).
- Only the restricted action worker receives Kubernetes API credentials. Control API and evidence worker must not have mutation rights; evidence worker has read-only rights only to evidence required by independent verification.
- Revalidate incident state, stored approval, expiry, target UID/resourceVersion, policy, current telemetry and replica/rollout constraints immediately before execution and on each bounded retry. Unknown action result is **indeterminate**.
- Independently verify workload readiness, exact revision, service response and corresponding alert transition. Kubernetes API 200/202 is not recovery proof. Never attribute natural controller reconciliation to the approved runbook.

### Console and CI

- Extend the Forest & Porcelain UI with real API-backed Workloads, Deployments and Capacity/Cost views and a typed runbook operation; keep existing navigation, reports, incident and experiments pages working.
- Add unit/integration/negative tests for missing/stale telemetry, unapproved/replayed action, namespace restrictions, RBAC denial, stale resourceVersion, transient API failure, restart and indeterminate outcomes.
- Extend CI with chart lint/template, Kubernetes schema/policy checks, secret scanning and bounded contract tests. No cloud resources or paid model calls in PR CI.

### Full milestone acceptance

- M3/M4 regression remains passing under the actual Kubernetes deployment.
- Actual k3d cluster bootstrap/cleanup is reproducible and measured against available memory and disk.
- Separate demo/control state and credential boundaries are maintained; least privilege and policy enforcement observed.
- Traefik/Gateway requests are tested, not assumed; internal storage and actuation remain inaccessible to anonymous users.
- GitOps sync and drift are proved with a reachable Git SHA.
- Argo Rollouts successful promotion and controlled bad-release abort/rollback are proved with actual telemetry.
- HPA/KEDA comparison is measured, and no durable jobs are lost or double-completed.
- One narrowly approved Kubernetes recovery operation passes positive and negative end-to-end tests with independent evidence.
- UI, accessibility, CI and runbooks are verified against the same image/source revision.

**Never call M5 complete just because the manifests exist.** Source, compilation, runtime, security enforcement and measured outcomes are distinct proof layers. The exact Kubernetes action, metrics threshold and resource ceiling must be set from actual preflight and run evidence rather than guessed values.
