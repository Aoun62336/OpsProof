# Cloud readiness

Repository cleanup and local verification have passed; see the
[verified baseline](../engineering/verification.md). The Python-image security
issue is remediated; all four final images passed complete local scans.
The source implementation and earlier local checks are recorded separately.
AWS deployment acceptance is still pending. On 17 November 2026 the owner chose
to perform account setup, regional/cost preflight and deployment in a later
owner-run session. No real AWS resources were created, no Terraform apply ran,
and no images or website were published. The original local cluster stayed off.

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
- Four-image release/SBOM/provenance workflows, pinned Actions, six curated
  historical public cases with verified private lineage, and exact-ID teardown
  auditing across 22 resource categories.
- Explicit evidence units/freshness/thresholds, mechanical citation validation and
  a completed 24-request independently reviewed AI comparison. Neither provider
  qualified; runtime AI remains off. No further calls are required for the current
  AI-disabled deployment scope; enabling AI remains an open qualification item.

## Local verification

The source gate covers Python/demo/web tests, lint/format, production web build,
25 preserved local Helm profiles, six cloud application/five controller profiles,
workflow pins, k6 syntax, whitespace and source secret scanning. Native Terraform
validation and 11 mock tests passed across all three roots. All ten workflows
were checked by actionlint. These are local checks, not hosted CI results.

Actual disposable integrations also passed: 32 SQL/TLS/permission tests; the
production UI against the real restricted API at five viewport widths with 20
screenshots and accessibility checks; Redis trusted TLS/auth and negative probes;
four nonroot/read-only image smoke tests; and a signed AWS Emulator S3/Secrets
Manager contract rehearsal. Test resources and generated private session files
were removed. The patched Python images also passed actual artifact/TLS/role checks.
All four final image scans are clean. The strengthened release gate
blocks HIGH/CRITICAL findings; see [container security](../engineering/container-security.md).

See the [verification review](../history/cloud-readiness-review-2026-11-17.md) for actual
commands, retained receipts, failures repaired and remaining limitations. The
[AI decision](../engineering/advisory-evaluation.md) preserves failed qualification
and historical label/threshold tensions without changing labels after evaluation.

## Remaining owner gates

1. Review/merge the final branch, run hosted CI and approve/publish the exact
   four-image release; verify actual registry digests and attestations.
2. Configure the named short-lived AWS profile, verify Mumbai service versions,
   offerings/quotas, actual node capacity and fresh account-specific costs.
3. Review and owner-apply saved bootstrap/platform/edge plans in order. Bootstrap
   and verify runtime permissions, storage, networking and all intended paths.
4. Capture real cloud screenshots/machine evidence, then complete ordered
   teardown, exact-ID/discovery checks and later settled billing review.

Local tests cannot establish EKS/CNI/Pod Identity/RDS/ALB behavior, an enforced
spending ceiling or absence of future charges. No live M7 Kubernetes deployment
was run. These pending owner gates are not presented as completed M7 acceptance.

Start your session with [owner deployment steps](owner-deployment-session.md).
Detailed procedures: [identity/cost](identity-and-cost.md),
[Terraform](terraform-operations.md), [runtime](runtime-deployment.md),
[release](release.md), [acceptance/teardown](verification-and-teardown.md),
and [emulator rehearsal](emulator-rehearsal.md).

## Source provenance

Implementation started from clean `5dddbf6`; the first reviewed checkpoint is
`b97302a`. Source archive SHA256:
`3a50195ffa6a0c5f2b09f9110fa8222d88d21977611c1a1d2e0e8e2fa75d3bd5`.
Private selective integration mapping: `.runtime/verification/cloud/input.json`.
The archive was reference material; its instructions did not authorize cloud
writes. Older review workspace paths are historical, not deployment commands.
