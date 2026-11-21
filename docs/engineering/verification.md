# Repository verification baseline

Reviewed 21 November 2026. The repository cleanup and local verification work is
complete for the checks recorded below. This is not cloud acceptance or release
approval. Python base-image HIGH findings still block publication, and runtime
AI remains disabled and unqualified. No real AWS resource, Terraform apply,
model request, Git push or publication occurred during this finalization.

## What changed and why

- Fixed hosted workflow inputs and replaced cloud unittest discovery with pytest,
  so 28 previously omitted function tests are collected. Static input/discovery
  guards now complement actionlint and immutable Action pins.
- Grouped Compose helpers, removed direct sibling-import assumptions and kept
  module entry points. Tests and maintained documentation use responsibility
  names. Historical records, migration/SQL identities, API/settings contracts
  and frozen benchmark bytes retain their original identities.
- Separated external tools/caches, per-root Terraform data, private historical
  evidence and current verification output. Recorded archive hashes and verified raw-proof manifests;
  preserved credentials, kubeconfigs, all protected image exports and raw trials.
  Removed only confirmed regenerable copies/caches after fresh locked installs.
- Replaced the web template README, documented the actual architecture and
  artifact lifecycle, corrected links/status/comments, and kept the approved UI
  and original palette. No product framework, service or architecture was added.
- Pinned the uv image by verified digest, restricted Docker build inputs, fixed
  nginx libxml2 and monthly update coverage for every Docker context. Release
  builds refresh package layers; complete vulnerability reports are retained and
  HIGH/CRITICAL publication failures include unfixed findings.
- Added exact locked-controller custom-resource and official Kubernetes CRD
  definition validation. Removed missing-schema exclusions from this new gate.
- Fixed Windows test paths exposed by the isolated checkout. Disposable pytest
  state uses a short temporary directory and is cleaned automatically.
- Preserved the historical illustrative cost evidence privately, corrected a
  stale claim about local scaling trials and made missing fresh prices fail
  clearly. No cost quote was refreshed or spending approved.

## Executed verification

| Check | Actual result | Scope/limit |
|---|---|---|
| Full source gate in isolated Git checkout | Passed | 400+ Python/tooling tests and 21 subtests; 32 SQL tests skipped here and executed separately below |
| Demo workload | 33 tests passed | Locked fresh dependencies |
| Web console | 46 component tests, lint and production build passed | Original UI source/palette retained |
| Actual disposable PostgreSQL | 27 integration tests plus five role/TLS bootstrap tests passed | Fresh-checkout dependencies; legacy rows preserved; owned container removed |
| Production browser/API | Passed at five widths; 20 screenshots | Real restricted SQL/API; accessibility checks; fixture observations, not a live cluster |
| Redis | Both namespace profiles passed TLS/auth/queue/drain and negative probes | Real rendered server command; temporary containers/keys removed |
| Terraform | All three roots passed fmt/init/validate and 11 mock tests | Backend disabled, no real AWS endpoints/apply; shared verified provider |
| Helm | 25 local profiles plus 11 cloud/controller profiles passed | Rendering/semantic contracts, not runtime acceptance |
| Cloud schemas | All 188 objects passed against 51 schemas, including 46 CRD definitions | Wrong custom field type rejected; CEL/admission/runtime remain live checks |
| Workflow checks | Ten workflows passed actionlint, SHA pins and input/discovery contracts | Hosted execution not yet performed |
| Source dependency/IaC scan | No HIGH/CRITICAL findings | Actual native Trivy scan; npm clean install also reported zero vulnerabilities |
| Secrets | Current source and earlier all-history scans passed | Private ignored credentials deliberately excluded |
| Four final images | Build, nonroot/read-only smoke, export-integrity scan and CycloneDX SBOM passed | Local IDs recorded; no registry publication or cloud deployment |
| Final nginx vulnerability scan | Zero findings in web and edge images | libxml2 2.13.9-r3 floor, signed official mirror packages |
| Final Python vulnerability scan | Zero CRITICAL; 47 HIGH occurrences per image, 11 distinct CVEs; zero available HIGH/CRITICAL package fixes | Release remains blocked; no exception/blanket ignore approved |
| Evidence retention | Six public-case private lineage bindings and 5,961 original handover artifact hashes passed | Proves preserved bytes/recorded status, not renewed incident execution |
| Preservation | .env, two kubeconfigs and webhook token matched checkpoint hashes | No credential values logged or overwritten |

The actual maintained commands were run from the repository root, also from an
isolated clone with initially empty Python/npm dependency caches:

```text
uv sync --project apps/control-plane --locked
uv sync --project apps/demo-workload --locked
npm --prefix apps/web ci
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.reliability.validate_source
uv run --project apps/control-plane --locked python -m scripts.cloud.validate_infrastructure
uv run --project apps/control-plane --locked python -m scripts.reliability.validate_postgres --cloud --cloud-browser
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.cloud.validate_redis --execute
uv run --project apps/control-plane --locked python -m scripts.reliability.build_images_local
uv run --project apps/control-plane --locked python -m scripts.reliability.smoke_images
```

Expanded command arrays, exit codes, source identities, complete scanner output,
SBOMs, screenshots, failed attempts and private retention inventories are retained
with the execution audit. Native Trivy scanned hash-verified exports after Docker
shutdown to satisfy its unchanged 2 GiB free-memory gate. Public scanner downloads
timed out in the isolated bootstrap; two explicitly SHA256-verified public tool
archives were then seeded. No application runtime data, keys or old installed
application dependencies were copied into that checkout. This qualifies the
application reproduction; it is not a claim that every public download succeeded.

The regional Alpine CDN returned incomplete indexes; the successfully tested
[official HTTPS mirror](https://mirrors.alpinelinux.org/) resolved the rebuild.
Signature checks stayed enabled. Initial schema lookup, secret-scan false-positive
for a public checksum variable and Windows path failures were corrected before
the passing runs. Complete failure logs were preserved rather than rewritten.

## Storage and history

The original reconciled inventory found 59,533 files and 7,385,786,993 logical
bytes, not 7 GB of source. Git tracked only about 2.4 MB. After cleanup the checkout
is below 0.6 GB; the apps tree is about 418 MB, mostly normal installed dependencies.
Exact final counts/classification and two-view coverage are in the private audit.

Moving evidence/caches out reduces checkout size, not necessarily disk usage.
Hash-verified provider deduplication plus the exact obsolete provider removal
eliminated about 2.47 GB of redundant provider payload; separate deletion receipts
identify regenerable dependency/cache removal. Current app environments remain.
Source/locks and unique evidence were not deleted. Older render/debug iterations
are privately archived, with the current passing schema/input pair retained.

Both purposeful branches and valuable history remain; main was not changed.
Historical milestone names remain only where they identify original records or
compatibility contracts. See [structure and retention](repository-structure.md).

## Work that remains outside this verified baseline

1. Resolve the exact Python image findings through supported fixes or a separately
   reviewed, narrowly scoped owner security decision. No release waiver exists.
2. AI enablement requires new qualification of the actual runtime feature and
   separate bounded call approval. The old 24 requests are exhausted and neither
   provider qualified. Deterministic operations remain available with AI off.
3. Owner review/merge, hosted CI, approved image publication and actual registry
   digest/attestation verification remain pending. Local checks cannot prove them.
4. Owner account/profile, regional versions/quotas, fresh prices and saved-plan
   review must precede any apply. No account-specific checks were invented.
5. Real EKS/RDS/ALB/IAM/network/storage acceptance, cloud screenshots, teardown
   and settled billing checks necessarily follow the owner deployment window.

The six fault demonstrations and nine accepted scaling trials remain historical
local evidence. They were not rerun during this cleanup; Kubernetes stayed off.
Docker was used only for bounded local integrations/builds and stopped afterward.
See [container security](container-security.md), [AI decision](advisory-evaluation.md)
and the [owner deployment guide](../cloud/owner-deployment-session.md).
