# Local Kubernetes platform

For routine checks on an existing deployment, use the [operating runbook](local-runbook.md).

## Safe context and prerequisites

Run from the repository root. Install the documented pinned tools and locked app
dependencies. Kubernetes helpers use `.runtime/platform/kubeconfig.yaml`, validate
the loopback API and never infer authorization from the default context.

```powershell
uv run --project apps/control-plane --locked python -m scripts.platform.preflight
```

Startup requires 5 GiB free host memory and 15 GiB free disk, plus the existing
Docker/node checks. A failed resource gate must not be lowered to continue.
Inspect an existing `opsproof` cluster instead of recreating it. Bootstrap is for
a genuinely new local installation only:

```powershell
uv run --project apps/control-plane --locked python -m scripts.platform.bootstrap
```

## Foundation and ownership

Prepare independent credentials in ignored `.env`; preserve existing configuration.
The foundation tool builds/imports images, records provenance, installs dependencies
and applies migrations before applications. Verify its actual output and readiness.

```powershell
uv run --project apps/control-plane --locked python -m scripts.platform.deploy_foundation
uv run --project apps/control-plane --locked python -m scripts.platform.smoke
```

These are deployment commands, not static checks. Inspect the target and source
before running them. After [GitOps adoption](gitops.md), Argo owns application
resources: update the approved source/image parameters rather than running a
parallel Helm reconciler. [Gateway access](gateway.md) remains loopback-only.

## Manual inspection

Always specify both local flags, even if another terminal selected a context:

```powershell
kubectl --kubeconfig .runtime/platform/kubeconfig.yaml --context k3d-opsproof get nodes -o wide
kubectl --kubeconfig .runtime/platform/kubeconfig.yaml --context k3d-opsproof get pods -A
```

Verify DNS, storage, migration completion, restricted roles, intended traffic and
denied cross-namespace traffic. Rendered policies do not prove CNI enforcement.
Use the smoke tool's owned loopback forwards; do not accidentally inspect Compose
on another port. Readiness alone does not prove telemetry delivery or recovery.

## Shutdown and evidence

Keep the cluster stopped when no live check needs it. Preserve PVCs, job history,
private credentials and unique evidence. Never automatically delete `opsproof`,
its volumes, or use `git clean -fdx`. Current private platform records are under
`.runtime/platform`; historical receipt paths resolve through `scripts.paths`.
AWS deployment has separate [owner gates](../cloud/owner-deployment-session.md).
