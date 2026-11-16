> Historical record. Commands, paths and results below describe the recorded revision. See [the current repository guide](../../README.md) for maintained commands and status.

# OpsProof v1.0 | Local-to-cloud verification commandbook

**Applicability:** M6 additive source built against `OpsProof(3).zip` and the frozen November 5 canonical handoff. The latest user-approved M5 changes and acceptance evidence **must** be audited before activating live fault/scaling/recovery tests. This handbook makes no cloud creation request and contains no unconditional “run everything” script.

## Verification profiles, never conflate their meaning

| Profile | Operation class | Requires environment | Can change state? | Gate |
|---|---|---|---|---|
| A | Source, Python/frontend tests, Helm rendering, AI deterministic qualification | Windows Git Bash, uv, Node, Helm | Only local caches/artifacts | No AWS; no cluster needed |
| B | Original demo/control/telemetry regression | Local Docker Compose | Starts services, writes local DB test rows | Preserve volumes; run published M4 docs |
| C | Kubernetes preflight, queries and workload smoke | Accepted `k3d-opsproof` cluster | Read-only for queries; smoke adds bounded jobs | Explicit kubeconfig; resource gate |
| D | GitOps, Rollouts, KEDA and worker-failure experiments | Accepted M5 cluster/controllers | Yes | Separate explicit approval and rollback plan |
| E | k6 bounded jobs, reconciliation and repeated capacity trials | Accepted M5 and suitable port-forward | Adds ordinary durable jobs | Idle queue and resource gate |
| F | AI deterministic/real model qualification | M6 dataset and optional provider account | External paid network only in approved mode | Separate model spend authorization |
| G | Terraform, pricing and AWS plan | M7 Terraform code **not yet available here** | Read-only locally, AWS identity may reveal account details | No apply without cost/authorization |
| H | Temporary EKS/cloud verification | Explicit M7 authorization | Chargeable mutations | Scoped plan, budget and teardown required |
| I | Public replay/release | Sanitized approved artifacts | Publish only after separate approval | Full source/release review |

Every run must record: Git SHA, clean/dirty tree, UTC, local platform, image digests, test parameters, outputs, status, failures, cleanup and limitations. `.env`, kubeconfig, provider keys, cookie/session data and DB passwords are **never** sent in logs or a public evidence directory.

## Profile A | Source and no-cost quality gates

Run from the actual repo root in Git Bash. Save only nonsecret output into the ignored `.runtime/` directory.

```bash
cd "$HOME/Desktop/opsproof"
mkdir -p .runtime/m6/acceptance

# Source identity: the commit ID alone omits uncommitted work.
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check

git ls-files .env .runtime

# Verify original Python apps against current lockfiles; do not fake missing deps.
uv run --project apps/demo-workload --locked ruff check apps/demo-workload
uv run --project apps/demo-workload --locked ruff format --check apps/demo-workload
uv run --project apps/demo-workload --locked pytest apps/demo-workload/tests -v
uv run --project apps/control-plane --locked ruff check apps/control-plane
uv run --project apps/control-plane --locked ruff format --check apps/control-plane
uv run --project apps/control-plane --locked pytest apps/control-plane/tests -v

# M6 source and isolated tests, same Python as the control plane.
export PYTHONPATH="$PWD/apps/control-plane/src"
uv run --project apps/control-plane --locked ruff check scripts/m6
uv run --project apps/control-plane --locked ruff format --check scripts/m6
uv run --project apps/control-plane --locked pytest scripts/m6/tests -v

# Actual JavaScript syntax, not a k6 runtime test.
node --check benchmarks/k6/jobs.js
```

**Expected:** Each command exits zero. Preserve all failures. A Python parser pass does not prove live DB/Redis access; `node --check` does not execute k6. `git ls-files .env .runtime` should print no tracked secret/runtime entries.

Review the current UI separately:

```bash
cd apps/web
npm ci
npm run lint
npm run test
npm run build
cd ../..
```

Only run Playwright when the correctly authenticated and routed local stack is available. Keep both the browser output and the matching backend/source revision.

## Profile B | Original Compose and telemetry regressions

**Before any cluster experiments**, use the canonical M4 runbooks and verify original functionality still works. The following checks are structural, not all-purpose runtime acceptance:

```bash
docker compose -f compose.yaml -f compose.target-integration.yaml config --quiet
docker compose -f compose.control.yaml config --quiet
docker compose -f compose.observability.yaml config --quiet

docker stats --no-stream
```

When the appropriate independent Compose projects are running according to the existing runbooks, execute `scripts/verify_demo.py`, `scripts/verify_control.py`, `scripts/verify_milestone4.py`, `scripts/verify_observability.py`, `scripts/verify_m4_security.py` with their documented arguments. **Do not** run `docker compose down -v` on retained data. Confirm post-test recovery and AI remain disabled by default.

**Acceptance:** Actual database job IDs, M4 action acknowledgment, independent outcome, webhook firing/resolved transitions, Loki **real worker log**, Tempo real trace, negative auth/CSRF and no false success.

## Profile C | Explicit local Kubernetes read-only preflight

The M5 code `scripts/m5/local_cluster.py` requires the isolated server `https://127.0.0.1:6550`. The new M6 preflight and queue collector apply the same URL restriction. Never use the default kubeconfig because the user's historical context may point at EKS.

```bash
cd "$HOME/Desktop/opsproof"
export KUBECONFIG="$PWD/.runtime/m5/kubeconfig.yaml"

# Fail closed if the context or cluster is not the local OpsProof k3d.
test "$(kubectl config current-context)" = "k3d-opsproof" || exit 1

uv run --project apps/control-plane --locked python scripts/m6/preflight.py \
  --kubeconfig .runtime/m5/kubeconfig.yaml \
  --output .runtime/m6/acceptance/cluster-preflight.json

kubectl get nodes -o wide
kubectl get pods -A
kubectl get deployments,statefulsets -A
kubectl get pvc -A
kubectl get applications.argoproj.io -A
kubectl get rollouts,analysisruns -A
kubectl get hpa -A
kubectl get scaledobjects -A
kubectl get gateway,httproute -A
```

**Expected:** The local API is responsive, nodes Ready, application namespaces exist, the relevant custom resources exist after M5 acceptance. Unknown CRDs mean corresponding M5 functionality is not established, **not** that M6 passed.

Review least privilege with the precise existing ServiceAccounts:

```bash
kubectl auth can-i patch deployment/demo-worker \
  -n opsproof-demo --as=system:serviceaccount:opsproof-control:control-action
kubectl auth can-i patch deployment/demo-api \
  -n opsproof-demo --as=system:serviceaccount:opsproof-control:control-action
kubectl auth can-i get deployment/demo-worker \
  -n opsproof-demo --as=system:serviceaccount:opsproof-control:control-evidence
kubectl auth can-i patch deployment/demo-worker \
  -n opsproof-demo --as=system:serviceaccount:opsproof-control:control-evidence
```

**Expected by the reviewed `infra/k8s/recovery-rbac.yaml`:** yes, no, yes, no respectively. These are read-only authorization review commands; they do not prove the ServiceAccount credentials are actually mounted only into the intended Pods or that the API has never been misused. Also inspect the rendered Pod specs and the namespace network policy.

Open **a separate Git Bash terminal** to keep a loopback-only demo API forward active:

```bash
cd "$HOME/Desktop/opsproof"
export KUBECONFIG="$PWD/.runtime/m5/kubeconfig.yaml"
kubectl --context k3d-opsproof -n opsproof-demo port-forward \
  svc/demo-api 18088:8080 --address 127.0.0.1
```

In the main terminal capture the real queue and job-state snapshot:

```bash
uv run --project apps/control-plane --locked python scripts/m6/collect_queue_state.py \
  --kubeconfig .runtime/m5/kubeconfig.yaml \
  --output .runtime/m6/acceptance/queue-before.json
```

**Why:** It distinguishes Redis `lag` (work not yet delivered to consumer group) from `pending` (delivered but unacknowledged); it also captures desired/ready replicas and actual PostgreSQL-backed API job totals. A null `lag` is unknown, never silently treated as zero. Snapshots are sequential and not transactionally atomic.

## Profile D | Existing M5 controller and failure validation

Do not begin while M5 is incomplete. Once accepted, retain Git SHA, image digests, controller versions, actual analysis results and recovery receipts for:

- Argo CD initial sync, deliberate safe drift, observed reconciliation and recovery from missing Secret.
- Argo Rollouts healthy candidate promotion; **separate** deliberately faulty candidate, actual error metrics, failed AnalysisRun, abort, final stable routing and healthy response.
- HPA demo API actual scale-out/scale-in and KEDA worker actual lag/PEL-driven replicas.
- Narrow Kubernetes restore via operator approval: exact Deployment identity, stale approval denial, race/replay denial, actuator acknowledgment **and independent proof**.
- Actual pending-message consumer recovery. The existing `scripts/m5/verify_consumer_recovery.py` mutates the local test workload; run only inside its documented approved trial environment.

Do not use `kubectl apply`, `delete pod`, `patch`, `scale`, `rollout undo`, `helm upgrade`, or Argo `sync` indiscriminately. Each requires its separate tested runbook, target lock and cleanup semantics. Argo CD may revert imperatively injected changes.

## Profile E | Bounded k6 and exact durable reconciliation

**Preconditions:** The M5 cluster and demo API pass smoke and security tests; queue is suitably idle; local free RAM and disk are adequate; port-forward 18088 is running. These k6 calls create ordinary persistent demo jobs and should be run only in the dedicated local test environment.

Check `k6 version` and create ignored output directory:

```bash
mkdir -p .runtime/m6
k6 version
set -o pipefail

# Each trial MUST have a new run ID. Rate * seconds <= 120.
export M6_RUN_ID="m6-$(date -u +%Y%m%d%H%M%S)"
export M6_BASE_URL="http://127.0.0.1:18088"
export M6_RATE=2
export M6_SECONDS=30
export M6_DURATION_MS=250
export M6_VUS=4
export M6_SUMMARY_PATH=.runtime/m6/k6-summary.json

k6 run benchmarks/k6/jobs.js 2>&1 | tee .runtime/m6/k6-receipts.log
```

**Why and expected:** A constant-arrival-rate test attempts 60 job creation requests, each with a unique idempotency key. The k6 thresholds fail on HTTP errors, dropped iterations or failed checks. The receipt log contains each accepted job ID and every rejected attempt. If k6 fails, keep the failure output; do not silently proceed as if all 60 jobs succeeded.

**Independent postcondition:**

```bash
uv run --project apps/control-plane --locked python scripts/m6/reconcile_jobs.py \
  --receipts .runtime/m6/k6-receipts.log \
  --run-id "$M6_RUN_ID" --expected-count 60 \
  --base http://127.0.0.1:18088 --timeout 300 \
  --output .runtime/m6/k6-durable-reconciliation.json
```

This rejects partial receipt counts, duplicate job IDs, missing/wrong job identities, failed jobs, unknown states and unfinished work. It reports p50/p95 on actual completed job timestamps, with no exactly-once execution claim. A successful k6 HTTP 202 alone is insufficient.

After the trial, capture queue state again:

```bash
uv run --project apps/control-plane --locked python scripts/m6/collect_queue_state.py \
  --kubeconfig .runtime/m5/kubeconfig.yaml \
  --output .runtime/m6/acceptance/queue-after.json
```

If queue lag/pending remain or resource alarms occur, STOP adding load and investigate. Do not reset queues or database volumes to force a green result.

### Repeatable capacity comparison using actual M5 harness

The existing `scripts/m5/verify_scaling.py --mode fixed|hpa|keda` **modifies the local Argo CD Application, deletes trial autoscaler objects where appropriate, creates a bounded load Pod and resets to fixed mode**. It is not a read-only command. Execute only after final M5 safety acceptance and with a separate run approval for each trial.

The existing script **overwrites** `scaling-<mode>.json` with each execution. Copy each result immediately to a unique filename, never copy/rename a failed trial into a pass. Example of the *approved* one-trial flow:

```bash
mkdir -p .runtime/m6/capacity
python scripts/m5/verify_scaling.py --mode fixed
cp .runtime/m5/acceptance/scaling-fixed.json .runtime/m6/capacity/fixed-1.json
```

Obtain three independent, comparable runs of each mode, with proper cooldown, queue drain, resource record and randomized execution order when feasible. Name artifacts `fixed-1.json` through `fixed-3.json`, and equivalently for `hpa` and `keda`. Record failed trials separately, not as successful comparison inputs.

Then analyze **only recorded passing trials**:

```bash
uv run --project apps/control-plane --locked python scripts/m6/analyze_capacity.py \
  --trial fixed:.runtime/m6/capacity/fixed-1.json \
  --trial fixed:.runtime/m6/capacity/fixed-2.json \
  --trial fixed:.runtime/m6/capacity/fixed-3.json \
  --trial hpa:.runtime/m6/capacity/hpa-1.json \
  --trial hpa:.runtime/m6/capacity/hpa-2.json \
  --trial hpa:.runtime/m6/capacity/hpa-3.json \
  --trial keda:.runtime/m6/capacity/keda-1.json \
  --trial keda:.runtime/m6/capacity/keda-2.json \
  --trial keda:.runtime/m6/capacity/keda-3.json \
  --output .runtime/m6/capacity/comparison.json
```

**Expected:** Source SHA, script SHA, parameters, exact completed job IDs and per-mode sample count all match accepted comparison requirements. The calculated p95 reduction is a median-based *local synthetic test result*, not a production MTTR claim. A single archived M5 run per mode cannot satisfy this gate.

## Profile F | AI evaluation: OFF by default

The dataset consists of 20 independently authored synthetic cases. The initial evaluator uses only local code:

```bash
export PYTHONPATH="$PWD/apps/control-plane/src"
uv run --project apps/control-plane --locked python scripts/m6/qualify.py \
  --provider deterministic \
  --output .runtime/m6/ai-deterministic.json
```

**Expected:** 20 cases evaluated, all predictions/abstentions reported, no provider request, no token spend. This is **synthetic** qualification, not held-out real-fault accuracy.

Real provider qualification with frozen Groq `openai/gpt-oss-120b` and Gemini requires (1) newly verified availability/pricing, (2) separate explicit cost authorization from the user, (3) a supplied provider key, (4) the CLI's dual authorization flags, and (5) no more than two cases per invocation. **Do not execute real-model commands automatically as part of this runbook.** No model can execute tools or authorize recovery.

## Six scenario acceptance and raw evidence

Read `M6_SCENARIO_CATALOG.md`. Each scenario needs a distinct injection event, real workload observations, independent proof and cleanup. Save one structured JSON record per scenario using actual UTC timestamps, image/source identities and actual evidence paths. Group the six records into an array and run:

```bash
uv run --project apps/control-plane --locked python scripts/m6/verify_scenarios.py \
  --input .runtime/m6/acceptance/six-scenario-records.json \
  --output .runtime/m6/acceptance/six-scenario-metadata-check.json
```

**Important:** This checks **metadata consistency only**. Even when `metadata_consistent=true`, `independent_runtime_acceptance` remains `NOT_VERIFIED_BY_THIS_SCRIPT`. An engineer must inspect raw telemetry, job IDs, actions, controller events, approvals and cleanup independently.

## Evidence manifest / integrity

Choose only curated nonsecret artifacts, never a directory glob that contains credentials:

```bash
uv run --project apps/control-plane --locked python scripts/m6/evidence_manifest.py \
  --root . \
  --file .runtime/m6/ai-deterministic.json \
  --file .runtime/m6/k6-durable-reconciliation.json \
  --file .runtime/m6/capacity/comparison.json \
  --output .runtime/m6/evidence-manifest.json
```

**Expected:** Each selected evidence file has a SHA-256 and exact length. Hashes prove identity only; they do not independently establish truth or guarantee immutability.

## Profile G/H | Cloud separation and cost gate

The current `OpsProof(3).zip` does not contain an accepted M7 Terraform/EKS project; **no exact `terraform -chdir=... plan/apply/destroy` command is grounded in the current source**. Once the user's promised full-seven-milestone ZIP arrives, inspect its `infra/terraform` or equivalent actual paths and then specify exact environment, provider lock, variables, region, state backend, cost gates, apply and teardown commands.

Generic **read-only** inventory/preflight (do not publish account IDs/credentials):

```bash
terraform version
aws --version
aws configure get region
# Only when you explicitly intend to inspect the selected AWS account:
aws sts get-caller-identity
```

Before real cloud execution: verify credit balance/eligibility, region-specific costs (control plane, instances, storage, network/NAT/LB, IPv4, logs), preapprove a charge envelope, configure cost alerts but not treat them as caps, plan emergency cleanup, restrict the AWS identity and inspect Terraform plan. No `terraform apply`, cluster creation or real provider AI requests without authorization.

Once approved, the release must include actual apply evidence, bounded cloud smoke, GitOps/recovery observations, `terraform destroy`, AWS resource inventory reconciliation and billing follow-up. Never mark teardown complete from a single successful `destroy` exit code.

## Global stop conditions / troubleshooting

Stop live experiments when the kubeconfig is not the exact local API, required M5 acceptance is missing, unexplained resource changes occur, free host RAM falls below the agreed floor, exact jobs do not complete, Redis lag becomes unknown, an alert/trace is missing, permission boundaries fail, a rollout is stuck or cleanup cannot be guaranteed. Collect read-only evidence first; do not wipe state or change deployment controllers blindly.

Classification per gate: `PASS` only for actual observed evidence on the exact revision; `FAIL` for a proved violation; `BLOCKED` for missing prerequisite; `NOT RUN` when no execution occurred. Never conceal failing trials or replace them with a screenshot of a healthy state after manual recovery.

## Preferred hardened k6 execution (owned port-forward)

The manual port-forward method above is useful for inspection, but **the preferred command is the new `run_k6_local.py`**, which checks the explicit k3d API endpoint, refuses to use a pre-existing process on port 18088, creates and owns the forward, requires a distinct authorization string for local test-data writes, runs bounded k6, reconciles the exact jobs and closes the forward in `finally`.

**Close any manually opened 18088 port-forward first.** This runner creates ordinary durable jobs; it does **not** inject faults, patch Kubernetes resources, access AWS or call paid AI.

```bash
cd "$HOME/Desktop/opsproof"
export PYTHONPATH="$PWD/apps/control-plane/src"
mkdir -p .runtime/m6

uv run --project apps/control-plane --locked python -m scripts.m6.run_k6_local \
  --kubeconfig .runtime/m5/kubeconfig.yaml \
  --run-id "m6-$(date -u +%Y%m%d%H%M%S)" \
  --rate 2 --seconds 30 --duration-ms 250 --vus 4 \
  --timeout 300 \
  --acknowledge M6_LOCAL_DURABLE_JOBS
```

**Success:** A single trial directory `.runtime/m6/<run-id>/` contains `k6-receipts.log`, `k6-summary.json`, and `exact-job-results.json`; all 60 accepted and completed jobs are independently verified. The run ID must be unique. **Failure:** The command returns nonzero and preserves its log; do not claim completed jobs from partial receipts. The forward is terminated even when k6 or reconciliation fails. Run only after resource preflight and accepted M5 deployment.
