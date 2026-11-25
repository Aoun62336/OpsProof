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
- Five-image release/SBOM/provenance workflows, pinned Actions, six curated
  historical public cases with verified private lineage, and exact-ID teardown
  auditing across 22 resource categories.
- Explicit evidence units/freshness/thresholds and mechanical citation validation.
  The final NVIDIA development qualification passed all 42 cases on 24 November
  2026, including ten runtime cause/action cases and independent factual review.
  Earlier Groq/Gemini and NVIDIA failures remain preserved separately. Runtime AI
  stays disabled; operational enablement and deployment validation are separate
  from benchmark qualification. No repeat comparison is required for unchanged
  model request and policy contracts. See the documented precision limitations.

## Local verification

The [latest verification report](../engineering/verification.md#repository-finalization-follow-up--24-november-2026)
records the clean-checkout tests, disposable SQL and browser checks, chart and
schema validation, Terraform mocks, and the scanned local artifacts. Earlier
Redis TLS, emulator and observability rehearsals are documented in the same guide.
The runtime advisory feature remains disabled. This evidence establishes local
behavior for the tested revisions. Real EKS admission, account-specific settings,
service connectivity, billing and teardown require the owner deployment session.

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
