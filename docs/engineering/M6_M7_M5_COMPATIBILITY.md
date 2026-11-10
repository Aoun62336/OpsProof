# M5 compatibility and non-regression map

This document exists because the 9 November M5 source is more advanced than the older staged M6/M7 ZIP.

## Protected M5 interfaces (unchanged)

- `apps/control-plane/src/opsproof_control/kubernetes_operations.py`: current `/api/v1/kubernetes/...` route separators and typed operations.
- `kubernetes_policy.py`, `kubernetes_client.py`, `kubernetes_worker.py`: exact-target policy, UID/resourceVersion checks, action/evidence separation and indeterminate state behavior.
- `apps/control-plane/alembic/versions/0005_kubernetes_recovery.py`: latest accepted schema.
- `infra/helm/opsproof-services/templates/rollout.yaml`: verified M5 Gateway reference formatting and rollout analysis.
- `apps/web/src/app/App.tsx`, `lib/api.ts`, `KubernetesPage.tsx`: actual M5 operator UI.
- M5 installation, security, telemetry, GitOps, scaling, recovery and release-trial scripts.

## Modified M5 interfaces (reviewed additive changes)

1. `apps/demo-workload/src/opsproof_demo/config.py`: strict fixed downstream address and bounded flags, all disabled by default.
2. `apps/demo-workload/src/opsproof_demo/__main__.py`: independent `fixture` entrypoint for the test-only HTTP dependency.
3. `apps/demo-workload/src/opsproof_demo/worker.py`: opt-in HTTP probe *before* terminal completion, leaving lease, fencing, retry, worker-hold and graceful shutdown machinery intact.
4. `infra/helm/opsproof-services/values.yaml`: optional image digest and disabled M6 fixture parameters.
5. `infra/helm/opsproof-services/templates/_helpers.tpl`: image digest selection, bounded fixture rendering and worker environment variable.
6. `infra/helm/opsproof-web/values.yaml`: optional image digest.
7. `infra/helm/opsproof-web/templates/web.yaml`: image digest selection.

## Do not infer runtime compatibility from source checks

The source-level tests assert key interfaces but **cannot prove** the opted-in fixture's real HTTP dependency/trace behavior, the M5 recovery after the new worker image is built, or Kubernetes resources admission. Rebuild only changed images, deploy to the isolated k3d environment under an approved local test, and run a new M5 smoke and negative security verification before using the new M6 profile. This is not authorization to mutate the existing accepted cluster.

## M5 evidence reuse

The user supplied an independent sanitized acceptance ZIP and reports. Do not embed unreviewed raw `.runtime` evidence into this source ZIP or claim to have reproduced historical trial outcomes. M6 may cite previously established results only with the original source/image identities and appropriate limitations. One capacity trial per mode is insufficient for the frozen repeated M6 comparison acceptance gate.
