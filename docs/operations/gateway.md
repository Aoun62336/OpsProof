# Local gateway and private operator access

The local Gateway profile exposes the production web application on
`http://127.0.0.1:8081`. Historical acceptance is recorded separately from the
state of any current cluster. See [verification](../engineering/verification.md).

Traefik runs in `opsproof-gateway`; the UI HTTPRoute targets its same-namespace web
Service. Nginx serves the compiled React application and proxies `/api/` to the
internal authenticated control API. It does not expose demo actuators or databases.
The existing Forest & Porcelain palette is unchanged.

## Deployment and verification

Use the [local foundation procedure](local-platform.md) first. The maintained
helper consumes the recorded foundation source/image identity, an isolated local
kubeconfig, Gateway API v1.6.1 and Traefik chart 42.3.0. Review pins before upgrades.

```powershell
uv run --project apps/control-plane --locked python -m scripts.platform.deploy_gateway
uv run --project apps/control-plane --locked python -m scripts.platform.verify_gateway
```

Run deployment only for an approved local session. After GitOps adoption, application
updates belong to Argo rather than a competing Helm upgrade. Inspect the helper's
scope and existing ownership before reusing an installation command.

Verify loopback binding, Gateway/HTTPRoute acceptance, the actual served asset/image
identity and API proxy behavior. An unauthenticated session request must return 401,
not frontend HTML. Verify login/logout, invalid CSRF, keyboard/mobile navigation,
observation freshness and inaccessible integration states. Record screenshots with
source/image identity; do not expose cookies or keys.

Local progressive delivery uses the separately verified Rollouts/router profile.
Gateway health alone does not prove traffic weighting, abort or rollback.

## Cloud boundary

Temporary EKS keeps the operator UI private through loopback port-forwarding.
Its isolated public edge is managed HTTPS and cannot proxy the operator API.
Do not make the local HTTP-cookie profile publicly reachable. See
[cloud runtime](../cloud/runtime-deployment.md) and
[release boundaries](../cloud/release.md). Starting Kubernetes is unnecessary for
source tests, builds and mocked Terraform checks.
