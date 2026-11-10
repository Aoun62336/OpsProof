# OpsProof M7 | Reviewable GitHub release, OIDC and artifact security

## Existing controls preserved

The original M2–M5 workflows remain. New workflows add offline M6 contracts, filesystem/secrets checks, and **manual** GHCR publication. No existing CI workflow is removed. Each must be checked in real hosted CI on the actual commit before it can support a release claim.

## GitHub setup

1. Confirm which repository and branch are authoritative. Check default branch and protected branch rules.
2. Configure GitHub Actions **environment `opsproof-release`** with required human reviewers and restrictions to `main`, to prevent accidental manual publication.
3. Configure package visibility and permissions for the actual GitHub repository. Private images require additional Kubernetes image pull credentials; this sample has no automatic private registry secret injection.
4. Review repository Actions permissions: prefer minimal `GITHUB_TOKEN` permissions, restrict reusable/untrusted actions, pin action commits whenever possible.
5. The release workflow is `workflow_dispatch` with a `publish_approved` boolean, requires `main`, and builds each image from the selected source commit; Trivy scans occur before `docker push`.
6. Publication uses a commit SHA tag and verifies the registry push digest. An `actions/attest@v4` step requests provenance and SBOM attestations. Verify exact action SHA and the hosted behavior before final release; source syntax is not proof of successful attestations.
7. Link the actual released `sha256` image digest in the GitOps values, verify the live image digest and record run ID, scanner DB version, SBOM and attestation verification.

### OIDC for AWS: optional and read-only initially

The current Terraform includes an **optional GitHub read-only inspection role**, not a deploy role. Use an existing separately verified `token.actions.githubusercontent.com` IAM OIDC provider ARN. The trust policy requires both `aud=sts.amazonaws.com` and an **exact** `sub`. No wildcard repositories or branches are permitted.

**Important July 15, 2026 format change:** New GitHub repositories default to an immutable subject containing owner ID and repository ID, such as `repo:OWNER@OWNER-ID/REPO@REPO-ID:ref:refs/heads/main`. Older repos may still emit name-only subjects. Verify actual emitted subject on your repo before approving Terraform role creation. Do not guess IDs or copy examples into production.

No OIDC AWS role is required for ordinary GHCR publication; that uses GitHub's own package token. Avoid granting EKS/EC2 write to the image-publishing job.

### Supply-chain checklist

- All existing backend/frontend/observability and M5 source checks pass on the exact commit.
- Trivy source/image scans meet the documented HIGH/CRITICAL policy; findings are reviewed.
- Gitleaks searches source/history and any leaked credentials are rotated.
- Every published image has immutable digest and appropriate SBOM/provenance evidence.
- `gh attestation verify oci://... -R OWNER/REPO` succeeds for the published digest.
- Dependabot alerts and lockfiles reviewed; released code contains no `.env`, tokens, Terraform state or live kubeconfig.
- `git diff --check` and final branch/source provenance recorded.
- No Git push, tag, package publishing, AWS apply or public deployment without user's explicit approval.

**Sources:** https://docs.github.com/en/actions/reference/security/oidc ; https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws ; https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
