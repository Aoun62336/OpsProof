# Approved release and public evidence

`.github/workflows/release.yml` is manual, restricted to reviewed `main`, and
requires `publish_approved=true` plus the protected `opsproof-release` environment.
Configure environment reviewers before first use. No publication has run during
local implementation. No AWS identity is needed by the publishing workflow.

## Four-image identity

The same source commit builds demo, control, web and isolated edge images. Each
image is scanned before push, receives a CycloneDX SBOM and requested provenance
and SBOM attestations. The policy blocks fixable HIGH/CRITICAL findings; unfixed
findings still require review and must not be described as zero vulnerabilities.
The workflow retains per-image receipts/SBOMs and assembles one manifest with the
source SHA, repository, workflow run ID and exactly four immutable GHCR digests.
Mixing runs, commits, repositories or duplicated roles fails assembly.

```sh
python -m scripts.cloud.verify_release_manifest --input .runtime/cloud/release-manifest.json
```

This is only offline consistency validation. After approved publication, verify
that all four actual digests are pullable, and verify both signatures against
the exact repository, source commit, main ref and release workflow:

```sh
gh attestation verify oci://ACTUAL_IMAGE_BY_DIGEST --repo ACTUAL_OWNER/ACTUAL_REPO --signer-workflow ACTUAL_OWNER/ACTUAL_REPO/.github/workflows/release.yml --source-digest ACTUAL_SOURCE_SHA --source-ref refs/heads/main --deny-self-hosted-runners
gh attestation verify oci://ACTUAL_IMAGE_BY_DIGEST --repo ACTUAL_OWNER/ACTUAL_REPO --signer-workflow ACTUAL_OWNER/ACTUAL_REPO/.github/workflows/release.yml --source-digest ACTUAL_SOURCE_SHA --source-ref refs/heads/main --deny-self-hosted-runners --predicate-type https://cyclonedx.org/bom
```

Use public, verified packages for the temporary cluster unless private registry
access has been separately designed and approved. No private registry token
injection is provided. Record hosted CI results, scanner database version,
SBOMs, actual attestation verification and the exact approved release manifest.
Do not relabel a locally built image or a requested attestation as verified
registry provenance. All workflow action references are immutable upstream SHAs;
review their official releases when updating.

## Reconciliation ownership

`scripts.cloud.render_gitops` binds all six workload Applications to the release's
full source SHA and image digests. Initial synchronization is manual and ordered;
Application sync-wave annotations alone do not order independent Application
syncs. After bootstrap validation, regenerate with `--enable-reconciliation` to
allow self-heal, with automatic pruning off. Thereafter update Applications/Git,
not parallel `helm upgrade` commands. Namespace RBAC excludes Secret access,
cluster resources and RBAC writes; owner bootstrap handles those resources.

Cloud APIs initially use Deployments/HPA and workers KEDA. The proven local
Rollout/Gateway profile is preserved. The cloud profile does not pretend to
exercise that local traffic-router plugin; enabling it in EKS would require a
separately reviewed router/plugin composition. Argo Rollouts controller health
and actual progressive delivery are different acceptance claims.

## Static publication

`.github/workflows/evidence-pages.yml` is a separate manual public release.
It requires the exact SHA256 of reviewed `docs/public/cases.json` at `main` and
a protected `github-pages` environment. Its renderer/auditor require exactly one
uniquely identified record for each of the six scenarios, escape text, block
obvious secrets/private endpoints/scripts/forms, and identify real source-tree
hashes plus clean/dirty state. Hash validation does not prove truthful prose.
Bind each curated record to actual private accepted evidence and independently
review privacy, claims and limitations before publication. Publish neither raw
logs nor provider credentials, account data or live operator URLs.

The static edge serves only GET `/` and `/healthz`; it cannot proxy the operator
API. The operator console stays private on loopback port-forwarding. Both static
surfaces retain the original forest/porcelain palette. Publishing evidence and
running public AWS ingress are separate activities and approvals.

References: [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations),
[official Pages actions](https://github.com/actions/upload-pages-artifact).
