# Milestone 5 | GitOps reconciliation protocol

## Local execution safety update (November 7, 2026)

Use `python scripts/platform/preflight.py`, then `python scripts/platform/bootstrap.py`.
Bootstrap writes only `.runtime/m5/kubeconfig.yaml`; it never switches the default context.
The inspected default context was an AWS EKS context, so **before any manual commands below**,
set the isolated config in each Git Bash terminal:

```bash
export KUBECONFIG="$PWD/.runtime/m5/kubeconfig.yaml"
test -f "$KUBECONFIG" || exit 1
test "$(kubectl config current-context)" = k3d-opsproof || exit 1
```

For the foundation, prefer `python scripts/platform/deploy_foundation.py`, followed by
`python scripts/platform/smoke.py`. Both use explicit local configuration; the latter owns
the dedicated port forwards. Do not run the old manual cluster-create commands again
after bootstrap. All runtime acceptance remains pending until the evidence exists.


**Prepared, not yet deployed.** The script `scripts/platform/render_gitops.py` reads the actual Git remote, rejects unknown hosts, requires an explicitly chosen reachable full commit SHA, and emits an Argo CD AppProject plus five Application manifests. It does not push or make network calls. The project restricts destinations to the three application namespaces; Kubernetes controller RBAC still needs separate assessment.

## Bootstrapping

1. Verify M5 Stage 1–3 and the approved local resource headroom. Argo CD adds CPU/RAM and may need to run as a separate experiment profile rather than alongside the entire observability suite.
2. Pin the chart version. As of November 7, 2026 the Argo CD Helm chart `10.14.0` exists; verify current compatibility and release notes before use. Use `helm show chart argo/argo-cd --version 10.14.0` after adding the repository.
3. Install Argo CD in a dedicated `argocd` namespace without a publicly accessible LoadBalancer. Use a locally approved minimal chart values file after resource benchmarking. Do not run `curl | sh` or fetch installation manifests without version pins.
4. Confirm your actual Git remote and that the revision is **pushed and readable by Argo CD**. The user has not authorized remote push/merge yet. A local-only SHA cannot be read by the Argo CD repo-server. If the remote is private, obtain explicit approval for a narrowly scoped read-only repo credential.
5. Render the manifests only after the remote revision exists and image tags are actually resolvable by k3d/GHCR; do not invent provenance.

```bash
git remote -v
git rev-parse HEAD
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update argo
helm show chart argo/argo-cd --version 10.14.0
export M5_REVISION="$(git rev-parse HEAD)"
export M5_TAG="m5-$(git rev-parse --short=12 HEAD)"
python scripts/platform/render_gitops.py --revision "$M5_REVISION" --tag "$M5_TAG" > .runtime/m5/argocd-applications.json
```

**Do not `kubectl apply` that manifest until the authorized Git revision and images are reachable, Secrets are installed, controller and namespaces are ready, and the application's resource ownership has been reconciled with earlier manual Helm releases.** Helm and Argo CD should not simultaneously claim ownership of the same release resources. Establish an explicit cutover and preserve PVCs.

## Acceptance: real GitOps

- Record AppProject, repo URL, commit SHA, image digest, sync history and application health.
- Demonstrate initial sync; a Git-approved manifest revision; intentional non-destructive drift; reconciliation; failure on missing Secret; and recovery from out-of-sync state.
- `prune` is disabled in generated Applications until a reviewed cleanup policy exists. No automatic deletion of PVC/data.
- Later Argo Rollouts owns HTTPRoute backend weights; Argo CD `ignoreDifferences` must be limited to those fields, not all HTTPRoute behavior. Verify plugin writes before claiming traffic proportions.

## Repository and ordering audit

User-selected repository: `https://github.com/Aoun62336/OpsProof.git`.
The November 7 read-only `git ls-remote` returned exit 0 with no refs: the repository
is reachable but has no deployable revision. No push has been performed.

The generator validates URL and SHA syntax; it does **not** verify remote reachability.
Check the exact revision separately before use. Sync-wave annotations on five independent
Applications do not orchestrate dependency health by themselves. For first adoption,
complete dependency sync and storage health first, then application migrations/workloads,
then web routing. Do not infer cross-Application ordering from the JSON List.
No blanket HTTPRoute drift exclusion is generated; introduce an exclusion only for the
exact route and fields proven to be controlled by a later Rollouts integration.
