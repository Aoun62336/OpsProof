# GitOps reconciliation protocol

Argo CD owns the adopted application resources. Source/image identity and a single
reconciler are the operational contracts; local Git availability is separate from
GitHub publication. Dated outcomes are in [verification](../engineering/verification.md).

## Local source and adoption

The local generator validates repository/revision syntax, not remote reachability.
The read-only local Git server can provide a reviewed local commit without pushing
it to GitHub. It must be reachable by repo-server at the intended full SHA. Ensure
the recorded image provenance also matches the source; a commit-derived tag alone
does not prove an image built from a dirty tree.

The existing helpers are `scripts.platform.serve_local_git`,
`scripts.platform.install_argocd` and `scripts.platform.adopt_gitops`.
Run them only in an approved local deployment session with locked dependencies;
the installer requires `--with PyYAML==6.0.3` in the uv invocation. Adoption consumes
`.runtime/platform/acceptance/gitops-images.json`; inspect that existing provenance
before any write. It adopts five Applications in order while retaining Helm history
and PVCs. Do not reconstruct deployment identities or assume this file exists in a
fresh checkout. Follow [local operation](local-runbook.md).

For existing Applications, update reviewed Git revisions and affected image
parameters, preserving narrowly scoped controller-owned-field exceptions. Never run
parallel `helm upgrade` commands against Argo-owned releases. Secrets remain outside
Git. Do not add whole-resource drift exclusions or automatic PVC pruning.

## Acceptance

Verify repository reachability, source SHA, actual image identity, scoped AppProject
and Kubernetes permissions, initial sync, non-destructive drift reconciliation and
recovery from missing prerequisites. Application annotations in a JSON List do not
order independent sync operations; verify dependencies/storage before applications
and migrations, then UI routing. Controller health is not progressive-delivery proof.

## Temporary cloud profile

Cloud controller charts and checksums are pinned under `infra/k8s/cloud/`.
`scripts.cloud.render_gitops` consumes the verified five-image release manifest
and renders six workload Applications at its exact source SHA. Initial sync is
manual and ordered. Reconciliation may be enabled only after bootstrap checks;
automatic pruning stays off. The cloud profile uses Deployments/HPA/KEDA, not an
unverified transplant of the local traffic-router integration.

See [approved release](../cloud/release.md) and
[runtime deployment](../cloud/runtime-deployment.md). A local passing check does
not establish hosted CI, registry trust, real IAM, CNI or AWS deployment acceptance.
