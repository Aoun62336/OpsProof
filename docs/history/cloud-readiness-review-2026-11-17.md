# Pre-cloud engineering verification review

Reviewed 17 November 2026 on `codex/cloud-readiness`, based on clean `5dddbf6`
and first checkpoint `b97302a`. The final source gate records its own source-tree
identity and command/exit-code receipts under `.runtime/verification/source/`.
This report closes local preparation, not AWS acceptance or an approved release.

## Changes and justification

The existing architecture, UI palette, SQL migrations, API contracts and local
fault boundaries were preserved. Cloud deployment uses separate state/platform/
edge responsibilities, private application resources, scoped Pod Identity and
namespaced GitOps. Shared grant/telemetry/permission logic avoids parallel
implementations. No new application framework or runtime dependency was added.
The AWS SDK exists only in an isolated tooling environment.

Integration exposed and repaired genuine issues: strict Python TLS rejected the
Redis CA without key-usage extensions; read-only database/queue filesystems
needed bounded writable mounts; Docker auto-removal needed bounded confirmation;
controller certificate permissions were broader than their actual use; ALB
startup needed an explicit verified VPC ID; cloud metrics needed per-replica
headless discovery and removal of an absent local-only canary target. Failed
receipts remain available and are not relabelled as successes.

## Executed checks and reproduction

Run these from the repository root with the documented tools/caches installed.
Source-only checks do not start Kubernetes, call model providers or contact AWS.
Do not rerun the comparison: its 24-request authorization is exhausted.

| Command/check | Executed outcome |
|---|---|
| `uv run --project apps/control-plane --locked python -m scripts.reliability.validate_source` | Aggregated source/test/build/lint/secret/Helm gate; 397 Python tests + 21 subtests, 33 demo and 46 web tests passed; 32 SQL skips separately executed |
| `terraform -chdir=infra/terraform/ROOT fmt -check -recursive`, `validate -no-color`, `test -no-color` | All three roots valid; 11 native mock tests passed; no AWS provider calls |
| `.cache/tools/actionlint/1.7.12/actionlint.exe` | All ten workflow definitions valid locally; hosted CI not run |
| `uv run --project apps/control-plane --locked python -m scripts.reliability.validate_postgres --cloud-browser` | 32 actual SQL/TLS/grant tests plus real API/production UI browser checks passed; cleanup verified |
| `uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.cloud.validate_redis --execute` | Both namespace profiles passed TLS/auth/hostname/CA/plaintext and stream lag/pending/drain checks |
| `uv run --project apps/control-plane --locked python -m scripts.reliability.build_images_local` | Four local images built; exact context hashes/image IDs retained; not registry release identities |
| `uv run --project apps/control-plane --locked python -m scripts.reliability.smoke_images` | Four isolated nonroot/read-only/networkless smoke tests and cleanup passed; edge POST root/health rejected |
| `uv run --project apps/control-plane --locked python -m scripts.reliability.scan_images` | All four scanned; no CRITICAL or fixable HIGH; Python bases retain unfixed findings |
| `.runtime/cloud/sdk/Scripts/python.exe -m scripts.cloud.validate_emulator --execute` | Signed 1.0.385 package, 34 loopback requests; S3/versioned locking and owned Secret reconciliation/cleanup passed |
| `scripts.cloud.verify_curated_evidence`, public renderer/auditor | Six actual historical local trials bound to source/proof hashes; not publication approval |
| Native `promtool check config /etc/prometheus/prometheus.yml` against rendered cloud configuration | Configuration and all four alert rules valid |

The browser test checked authenticated capabilities and a genuine forbidden
mutation response, original colors, zero horizontal overflow at 1440/1280/768/
390/320 widths, and no serious/critical accessibility issues. Its seeded workload
observation is explicitly synthetic. Twenty screenshots are test proof, not AWS
screenshots. The static historical replay was separately checked at three widths,
with six cards, no overflow or browser errors; desktop/mobile previews inspected.

Primary retained receipts:

- Native Terraform: `.runtime/verification/cloud/terraform/result.json`.
- SQL/browser: `.runtime/verification/cloud/postgres/opsproof-m6-pg-test-5b04a61429/result.json`.
- Redis: `.runtime/verification/cloud/redis/` (latest passing result).
- Emulator: `.runtime/verification/cloud/emulator/run-8c682ff080704a839a992d32bc5472f4/result.json`.
- Images: `.runtime/m6/acceptance/image-provenance.json` and `images/smoke-*/`, `images/scan-*/`.
- Cloud Helm: `.runtime/verification/cloud/helm/`; source security: `cloud/security/`.
- Public lineage/render/visuals: `.runtime/verification/cloud/public-lineage.json`, `public/`.
- AI: `.runtime/verification/ai/comparison-v2/`, including independent review.

Legacy private runtime paths retain compatibility names. They are ignored evidence,
not newly introduced milestone-specific source structure. Private exports and
credentials are excluded from Git. Original migrations/frozen regression bytes
and valuable history remain intact.

## Security and interpretation limits

Python demo/control image scans each report 47 HIGH occurrences (11 distinct
unfixed advisories), zero CRITICAL and no available HIGH/CRITICAL fix. Web and
edge scans report no vulnerabilities. No findings were hidden with an allowlist;
unfixed issues remain a release review item and need fresh scans before publishing.
Dependency deprecation warnings also remain visible in the test logs.

Strict Kubernetes 1.35 schema validation passed for 161 standard resources
with zero invalid objects. The default registry lacked 39 CRD-definition schemas
and the ALB IngressClassParams schema; that first full check failed and its
exclusions are explicit in `.runtime/verification/cloud/schema-exclusions.json`.
Kubernetes native schema validation therefore covers available standard schemas; controller
CRD definitions and custom objects need their locked schemas and ultimately real
API-server admission/runtime checks. Helm lint, values schemas and semantic safety
checks passed; these do not prove CNI enforcement or controller readiness.

The rendered request worksheet is `.runtime/verification/cloud/capacity.json`:
32 steady Pods request 1175 millicores and 2552 MiB; bounded maxima plus concurrent
Deployment surge request 1955 millicores/4024 MiB across 54 Pods. Migration/init
Jobs are listed separately. Six AWS addons, node reservations, placement/AZ/PVC
constraints and real usage are excluded. Reconcile against actual per-node
allocatable capacity and Pod IP limits before syncing/scaling; this is not a fit
certificate or a high-availability claim.

The approved comparison completed all 24 calls without retries/fallbacks/tools.
Neither provider qualified. Gemini's better frozen-label scores do not excuse
unsupported threshold claims; old regression label/contract tensions and narrow
held-out coverage are documented in the [decision](advisory-evaluation.md).
Runtime AI stays disabled and does not block deterministic/manual cloud operation.
Billing was not independently audited and no additional model calls are needed.

The emulator proves local API contracts only. It cannot validate IAM/resource
policies, real EKS/RDS/ALB networking, account quota or billing. No Terraform apply,
AWS account request, real M7 Kubernetes deployment, hosted workflow, image push
or public publication was executed. The original local Kubernetes cluster stayed
stopped. The owner explicitly deferred account checks to the later deployment
session; see [the complete sequence](../cloud/owner-deployment-session.md).
