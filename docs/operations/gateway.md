# Milestone 5 | Gateway API, web application, and restricted local access

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


**Status: source prepared; chart and runtime acceptance pending.** Apply only after the Helm foundation is verified and existing local M4 corrections pass.

## Architecture and why

- Traefik Helm 42.3.0 runs in the `opsproof-gateway` namespace, with Gateway API CRDs installed separately from the official pinned release.
- One HTTP listener receives traffic only through the k3d port binding `127.0.0.1:8081`.
- An HTTPRoute in `opsproof-ui` points to `opsproof-web` in the same namespace.
- The Nginx container serves the compiled React build and forwards `/api/` to the internal control API. The demo API is **not** exposed through the public route.
- Sessions remain local-development HTTP cookies. Never use the loopback-only configuration for publicly reachable EKS.
- This stage does not claim actual Gateway traffic weighting or Argo Rollouts integration. Those require separately verified plugin/controller compatibility.

## Verify controllers before installation

Traefik uses Kubernetes Gateway API. At the time of authoring, chart 42.3.0 and Gateway API CRDs v1.6.1 were available; verify signatures, current chart release notes and compatibility before installing. Apply in the local k3d cluster only.

```bash
kubectl config current-context
helm repo add traefik https://traefik.github.io/charts
helm repo update traefik
helm show chart traefik/traefik --version 42.3.0
mkdir -p .runtime/m5
curl --fail --location --silent --show-error \
  https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.6.1/standard-install.yaml \
  --output .runtime/m5/gateway-api-v1.6.1.yaml
kubectl apply --server-side -f .runtime/m5/gateway-api-v1.6.1.yaml
kubectl get crd gateways.gateway.networking.k8s.io httproutes.gateway.networking.k8s.io
helm pull traefik/traefik --version 42.3.0 --untar --untardir .runtime/m5/charts
helm lint .runtime/m5/charts/traefik -f infra/k8s/traefik/values-local.yaml
helm upgrade --install traefik traefik/traefik \
  --version 42.3.0 \
  -n opsproof-gateway \
  -f infra/k8s/traefik/values-local.yaml \
  --wait --timeout 6m
kubectl get gatewayclass
kubectl get gateway -n opsproof-gateway -o wide
```

**Important:** Review the pinned chart values and rendered RBAC before installation. Never substitute `latest`.

## Build and run the local-only production UI

This build uses the existing React source, compiled with Vite. It does not change Forest & Porcelain styles.

```bash
export M5_TAG="m5-$(git rev-parse --short=12 HEAD)"
docker build -f apps/web/Dockerfile -t "opsproof-web:$M5_TAG" apps/web
k3d image import "opsproof-web:$M5_TAG" -c opsproof
helm lint infra/helm/opsproof-web --set-string image.tag="$M5_TAG"
helm template web infra/helm/opsproof-web -n opsproof-ui --set-string image.tag="$M5_TAG" > /dev/null
helm upgrade --install web infra/helm/opsproof-web -n opsproof-ui \
  --set-string image.tag="$M5_TAG" --wait --timeout 5m
kubectl get httproute -n opsproof-ui -o wide
kubectl describe httproute opsproof-web -n opsproof-ui
curl -I http://127.0.0.1:8081/
curl -i http://127.0.0.1:8081/api/v1/auth/session
```

Without a browser session, `/api/v1/auth/session` must return 401, not the frontend HTML. Check `Gateway` and `HTTPRoute` Accepted/ResolvedRefs conditions. In a browser confirm login, CSRF rejection, logout revocation, navigation, responsive layout, and screenshots using the project Playwright suite. No default admin account and no public network binding.

## Gate before Argo CD

Verify Nginx does not leak the demo actuator, Redis, database, configuration credentials or unauthenticated control mutations. Check the gateway port is bound to loopback on Windows and that Firefox/Chrome use the intended origin. Evaluate network policy enforcement before allowing GitOps or rollback controller writes. On EKS, require real TLS and secure cookies rather than inheriting local HTTP assumptions.
