# Local Kubernetes and Helm foundation

## Local execution safety update (November 7, 2026)

Use `python -m scripts.platform.preflight`, then `python -m scripts.platform.bootstrap`.
Bootstrap writes only `.runtime/platform/kubeconfig.yaml`; it never switches the default context.
The inspected default context was an AWS EKS context, so **before any manual commands below**,
set the isolated config in each Git Bash terminal:

```bash
export KUBECONFIG="$PWD/.runtime/platform/kubeconfig.yaml"
test -f "$KUBECONFIG" || exit 1
test "$(kubectl config current-context)" = k3d-opsproof || exit 1
```

For the foundation, prefer `python -m scripts.platform.deploy_foundation`, followed by
`python -m scripts.platform.smoke`. Both use explicit local configuration; the latter owns
the dedicated port forwards. Do not run the old manual cluster-create commands again
after bootstrap. All runtime acceptance remains pending until the evidence exists.


**Status:** source authored; Kubernetes runtime not executed in the audit environment.

## Design and scope

- The source of truth is the latest corrected M4, not the historical original ZIP.
- One k3d server node hosts two isolated application namespaces: `opsproof-demo` and `opsproof-control`.
- Two installs of `opsproof-dependencies` provide independent PostgreSQL and Redis; two installs of `opsproof-services` provide the actual services.
- No application service account receives a Kubernetes API token or RBAC grant in this foundation stage.
- Secrets are created locally from the existing ignored `.env` and never committed or printed to the terminal.
- Both AI and controlled recovery remain disabled by default.
- PostgreSQL PVCs and Redis AOF PVCs survive Helm uninstall; their deletion requires explicit permission.
- The demonstration API is internal to the cluster; developer access uses `kubectl port-forward`.
- Local `api` and worker data must not be claimed identical to existing Compose volumes. These are separate experimental stores.

## Resource gate, BEFORE creating the cluster

Record Git HEAD, Docker memory total, host memory available and disk available. Abort if the machine does not have adequate headroom. Suggested provisional thresholds to **measure, not assume:** at least 5 GiB currently free system memory and 15 GiB free disk space. If values are below these, close excess workloads instead of increasing allocations blindly. Operators and observability are an additional profile and will be tested separately.

```bash
git status --short
git rev-parse HEAD
docker info --format '{{.MemTotal}}'
docker system df
powershell.exe -NoProfile -Command "Get-CimInstance Win32_OperatingSystem | Select-Object FreePhysicalMemory,TotalVisibleMemorySize"
df -h .
k3d version
kubectl version --client
helm version
```

## Stage 1 | Cluster

**Do not run if a cluster named `opsproof` already exists without inspecting it.**

```bash
k3d cluster list
k3d cluster create --config infra/k3d/cluster.yaml
kubectl config use-context k3d-opsproof
kubectl get nodes -o wide
kubectl get storageclass
kubectl apply -f infra/k8s/namespaces.yaml
kubectl get namespaces -l app.kubernetes.io/part-of=opsproof
```

## Stage 2 | Build and load immutable local images

On the **corrected M4 working tree**, record the full commit hash after applying the accepted changes. Use a short but unique SHA tag, never `:latest`.

```bash
export M5_TAG="m5-$(git rev-parse --short=12 HEAD)"
docker build -f apps/demo-workload/Dockerfile -t "opsproof-demo:$M5_TAG" apps/demo-workload
docker build -f apps/control-plane/Dockerfile -t "opsproof-control:$M5_TAG" apps/control-plane
docker image inspect "opsproof-demo:$M5_TAG" --format '{{.Id}}'
docker image inspect "opsproof-control:$M5_TAG" --format '{{.Id}}'
k3d image import "opsproof-demo:$M5_TAG" "opsproof-control:$M5_TAG" -c opsproof
```

Git dirty-state must be recorded if local changes are uncommitted; a Git-derived tag is not sufficient image provenance for a dirty tree.

## Stage 2 | Secret distribution and dependencies

Store `.env` outside Git; the script uses it locally and writes no file. Do not use `kubectl -o yaml` to dump Secrets to logs. The namespaced `apply` operation requires operator privileges locally but no Pod receives those privileges.

```bash
python -m scripts.platform.render_local_secrets --env .env | kubectl apply -f -
helm lint infra/helm/opsproof-dependencies
helm upgrade --install demo-deps infra/helm/opsproof-dependencies -n opsproof-demo --wait --timeout 5m
helm upgrade --install control-deps infra/helm/opsproof-dependencies -n opsproof-control --wait --timeout 5m
kubectl rollout status statefulset/demo-deps-postgres -n opsproof-demo --timeout=5m
kubectl rollout status statefulset/control-deps-postgres -n opsproof-control --timeout=5m
kubectl rollout status statefulset/demo-deps-redis -n opsproof-demo --timeout=5m
kubectl rollout status statefulset/control-deps-redis -n opsproof-control --timeout=5m
```

## Stage 2 | Application deployments

The migrations are Helm pre-install/pre-upgrade Job hooks. Dependencies must already be healthy. Apps are released only after successful migrations.

```bash
helm lint infra/helm/opsproof-services -f infra/helm/opsproof-services/values-demo.yaml --set-string image.tag="$M5_TAG"
helm lint infra/helm/opsproof-services -f infra/helm/opsproof-services/values-control.yaml --set-string image.tag="$M5_TAG"
helm template demo infra/helm/opsproof-services -n opsproof-demo -f infra/helm/opsproof-services/values-demo.yaml --set-string image.tag="$M5_TAG" > /dev/null
helm template control infra/helm/opsproof-services -n opsproof-control -f infra/helm/opsproof-services/values-control.yaml --set-string image.tag="$M5_TAG" > /dev/null
helm upgrade --install demo infra/helm/opsproof-services -n opsproof-demo -f infra/helm/opsproof-services/values-demo.yaml --set-string image.tag="$M5_TAG" --wait --timeout 6m
helm upgrade --install control infra/helm/opsproof-services -n opsproof-control -f infra/helm/opsproof-services/values-control.yaml --set-string image.tag="$M5_TAG" --wait --timeout 6m
kubectl get pods -n opsproof-demo -o wide
kubectl get pods -n opsproof-control -o wide
kubectl get pvc -n opsproof-demo
kubectl get pvc -n opsproof-control
```

## Smoke and evidence

In separate Git Bash terminals:

```bash
kubectl port-forward -n opsproof-demo svc/demo-api 18088:8080 --address 127.0.0.1
kubectl port-forward -n opsproof-control svc/control-api 18090:8080 --address 127.0.0.1
```

Then (from a third terminal):

```bash
curl -fsS http://127.0.0.1:18088/health/ready
curl -fsS http://127.0.0.1:18090/health/ready
python -m scripts.platform.verify_k3d --env .env
kubectl logs -n opsproof-demo deploy/demo-worker --tail=50
kubectl logs -n opsproof-control deploy/control-evidence --tail=50
```

The M5 smoke intentionally uses dedicated ports 18088/18090, avoiding accidentally hitting Compose on 8088/8090. The resulting `.runtime/platform/k3d-smoke.json` records actual run IDs, without secrets. This does not by itself qualify as the complete M4 recovery drill.

## Verification boundary

Use current verification commands and explicit local kubeconfig/context. Historical
acceptance reports describe their recorded revisions. A fresh deployment must pass
storage, network, telemetry, rollout and permission checks before being accepted.
The original cluster's existence is not proof of a fresh checkout's reproducibility.

## Cleanup (requires checking current state)

Record PVC and database backups before deleting anything. `helm uninstall` alone does not imply data deletion. `k3d cluster delete opsproof` destroys local cluster and potentially its storage. Never execute the delete sequence automatically or before explicit user approval.
