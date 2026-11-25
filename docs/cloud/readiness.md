# Cloud readiness

AWS deployment acceptance is pending. The
[owner deployment session](owner-deployment-session.md) covers account setup,
regional and cost preflight, deployment, live acceptance and teardown.

## What is implemented

- Three guarded Terraform roots: state bootstrap, two-AZ private platform and
  isolated read-only public edge; exact provider locks and native mock tests.
- Resumable database credential/role bootstrap, granular grants, TLS verification,
  authenticated TLS Redis and separate application/migration identities.
- Read-only EKS observation, disabled recovery/model execution, and the existing
  operational UI/palette preserved with backend-owned capabilities.
- Scoped controller/GitOps permissions, five integrity-locked controller charts,
  namespace network boundaries, secrets, storage and shared telemetry rendering.
- Per-replica cloud metrics discovery, bounded API/worker scaling and explicit
  capacity/request review. No cloud progressive-delivery claim is made.
- Five-image release/SBOM/provenance workflows, pinned Actions, six curated
  historical public cases with verified private lineage, and exact-ID teardown
  auditing across 22 resource categories.
- Runtime AI is disabled. The [advisory decision](../engineering/advisory-evaluation.md)
  records the evidence contract and qualification limits.

## Remaining owner gates

1. Review/merge the final branch, run hosted CI and approve/publish the exact
   five-image release; verify actual registry digests and attestations.
2. Configure the named short-lived AWS profile, verify Mumbai service versions,
   offerings/quotas, actual node capacity and fresh account-specific costs.
3. Review and owner-apply saved bootstrap/platform/edge plans in order. Bootstrap
   and verify runtime permissions, storage, networking and all intended paths.
4. Capture real cloud screenshots/machine evidence, then complete ordered
   teardown, exact-ID/discovery checks and later settled billing review.

Local tests cannot establish EKS/CNI/Pod Identity/RDS/ALB behavior, an enforced
spending ceiling or absence of future charges. Live AWS deployment and the
owner acceptance checks remain pending.

Start your session with [owner deployment steps](owner-deployment-session.md).
Detailed procedures: [identity/cost](identity-and-cost.md),
[Terraform](terraform-operations.md), [runtime](runtime-deployment.md),
[release](release.md), [acceptance/teardown](verification-and-teardown.md),
and [emulator rehearsal](emulator-rehearsal.md).
