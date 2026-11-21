# Repository engineering review

Date: 16 November 2026. Scope: establish a maintainable local baseline before M7.
M7 implementation is paused pending separate owner approval. No Terraform apply,
AWS writes, image publication, Git push or model requests are part of this review.

## Audit and decisions

The audit covered the tracked source tree, application entry points and imports,
configuration layers, lockfiles, migrations, tests, scripts, workflows, operational
guides, ignored runtime artifacts and local Git references. The repository began
with 381 tracked files and uncommitted approved UI/evidence improvements. Those
improvements were checkpointed in `7ebb99b` before restructuring. Base history was
`8c973263fb5e3b1b9ddee671ca10894f0aad5057`.

- Replaced milestone tooling directories with `platform`, `reliability` and `cloud` responsibilities. Renamed active application modules, tests, workflow files and UI symbols around their purpose. All callers, imports, test selections and maintained documentation were updated.
- Consolidated the older partial source runner into one gate covering all tool packages, both Python applications, web tests/build, Helm and secret scanning. It records actual commands and results.
- Preserved the three application boundaries and all deployment/safety decisions. No framework, service or runtime dependency was added. Python package locks and application migration bytes remain unchanged.
- Kept the identical shutdown implementation in the independently packaged applications. Sharing it would require changing build boundaries for a tiny module. Matching Python pins and empty package markers also have a purpose.
- Kept Compose overlays because recovery, telemetry and integration are independently opt-in concerns. They are not duplicate base deployments.
- Moved dated status and acceptance snapshots into `docs/history`, with explicit historical context. Maintained procedures have responsibility-based filenames. Replaced the root milestone delivery note with the cohesive project README.
- Moved the existing replay HTML shell out of Python into a template, separating validation/rendering code from presentation. Escaping, bounded schema and publication review requirements are preserved.
- Extended lint and formatting coverage to previously unchecked tools. Fixed import ordering, unused imports, exception chaining and long strings without changing operational policy.
- Preserved frozen held-out fixture bytes across Git checkouts. Their recorded SHA256 values refer to original bytes, so `.gitattributes` now exempts only that frozen fixture directory from text normalization. The four indexed blobs were checked against the recorded hashes.
- Pinned the remaining mutable workflow actions to verified upstream release commits. Release remains manual and approval-gated. No workflow was dispatched.

See [the relocation map](repository-structure.md) for every tracked move and
compatibility boundaries. Existing SQL object names, environment variables,
Helm values, HTTP API paths and immutable evidence identities are intentionally
preserved. These are compatibility contracts, not leftover source modules.

## Artifact retention

Seven redundant handover/acceptance ZIPs were removed from ignored runtime
storage only after inspecting all 5,248 members. Existing raw evidence and Git
objects preserve duplicate contents. Ninety unique historical files were retained
by content hash in `.runtime/evidence/retained-artifacts/`. The manifest
`.runtime/evidence/archive-retention.json` records archive checksums, member
checksums and each retention location. Text files retained through Git normalize
CRLF to LF, explicitly recorded in that manifest. About 15.5 MiB of redundant
packaging was removed. No new ZIP was produced.

Checksum-pinned tool packages and browser failure traces retain their distinct
verification purpose. Credential files, raw trial receipts, prior failed trials,
cluster identity, database volumes and image identities were preserved.

## Git reference audit

Only one worktree exists. No tags existed. Every pre-existing local feature
branch was already reachable from the checkpointed current history. No unmerged
commits were found. No remote branch or published history was rewritten.

The audited local references before consolidation were:

| Reference | Preserved commit |
|---|---|
| `codex/repository-standardization` | `7ebb99bf9f08767d58b1e99638b726d6a818d823` |
| `feature/ai-investigation-safe-recovery` | `e28100da67d73268801c327c24f7228b2f1ff3ed` |
| `feature/control-plane` | `542f2ee6ec8f04c80021800a4c9de44a4c90a738` |
| `feature/forest-porcelain-redesign` | `3b93b7a117fcbf1ab79ca4a6e198b4614bdc6d03` |
| `feature/m5-local-foundation` | `9360869467aad9f291ce743b11cf75d9bb652f15` |
| `feature/m6-durable-trial-ledger` | `7ebb99bf9f08767d58b1e99638b726d6a818d823` |
| `feature/observability-incidents` | `5b8d6a74138baf8b52cadaa6b67aec8ea5af38fe` |
| `feature/operations-ui` | `1a5943be21fc4dc7cb6bf8a8f729a887925895ca` |
| `feature/opsproof-m6-m7-integration` | `38b3a4620882467805b10f36a3260ed55188116a` |
| `main` | `812ef2ab2541847a16276e7225ae79bffd0d0094` |

The completed cleanup is committed locally and fast-forwarded to `main`. The eight
merged feature branch names and the temporary review branch are removed only
after ancestor checks. Every audited commit remains reachable from `main`. No
tags required removal. No remote references were deleted or pushed. The local
review does not imply that GitHub-hosted CI has run.

## Verification

The executed final gate results are recorded below. Check logs are retained under ignored runtime
verification storage. Initial test attempts exposed renamed imports and a legacy
SQL table reference and a text-encoding conversion error; these were corrected before final verification. The Helm gate now explicitly supplies its existing pinned PyYAML tool dependency
through uv instead of depending on whichever global Python happened to be on PATH.
This adds no application runtime dependency and leaves lockfiles unchanged. A sandbox
attempt also could not access the user-owned pytest temporary directory; a
repository-local test temporary directory resolved that environment limitation.

## Reviewed secret-scanner exception

The first full Git-history scan flagged one English prose sentence about duplicate
job keys in `docs/experiments/M6_ENGINEERING_DETAILS.md` at commit
`38b3a4620882467805b10f36a3260ed55188116a`, line 55. The original line was inspected:
it describes receipt validation and contains no credential. `.gitleaksignore`
contains only that exact commit/path/rule/line fingerprint. No secret pattern,
file, directory or entire historical commit is broadly exempted. Git history is
preserved. Current source scanning already passed without that exception.

## Remaining boundaries

- M7's supplied overlay is not applied. Its previously reviewed infrastructure,
  cloud permissions, deployment and teardown gaps remain for an approved M7 phase.
- AI is disabled. New external candidate comparison remains deferred.
- Historical Kubernetes acceptance applies to its recorded revision. The cluster
  remains stopped during this source cleanup. No new live fault claim is made.
- Vulnerability scanning and native configuration checks must be reported with
  their actual findings. A successful scanner process is not a zero-vulnerability claim.

## Final executed results

| Check | Executed result |
|---|---|
| Backend and tooling pytest | 309 passed, 27 SQL-only skips, 14 subtests passed |
| Dedicated disposable SQL suite | All 27 passed; prior rows preserved; container cleanup verified |
| Authenticated browser integration | Passed using isolated PostgreSQL/API; desktop/mobile accessibility and CSRF assertions |
| Demo pytest | 33 passed; one existing deprecation warning |
| Web Vitest | 44 passed across five test files |
| Python lint / formatting | Passed for both applications and all tooling |
| Web lint / TypeScript / Vite production build | Passed |
| Reliability Helm profiles | 25 positive/negative profiles passed; no deployment |
| Platform Helm checks | Eight render configurations, 61 objects passed |
| Built-in Kubernetes schemas | 25 resources passed strict Kubernetes 1.35 validation |
| Upstream gateway chart | Pinned Traefik 42.3.0 render/schema and exposure checks passed |
| Existing Terraform | Format, backend-disabled initialization with readonly lockfile, and validation passed; zero validation warnings |
| Compose configuration | All six supported base/overlay combinations passed with quiet secret-safe output |
| CI workflow validation | actionlint 1.7.12 passed for all eight workflows; ShellCheck integration unavailable on this host |
| Current source secret scan | Passed |
| Git history secret scan | 36 commits passed after the single inspected prose fingerprint exception |
| npm dependency audit | Zero reported vulnerabilities |
| Final Docker images | Three built locally; nonroot/read-only/network-isolated smoke checks passed; none published |
| Final image vulnerability scan | Zero critical findings; 47 high findings per Python image, 11 distinct high CVEs across them; no fixed version reported. Web image zero findings |
| Reference and identity checks | Documentation links, JSON data, moved imports/test selections, original palette, unchanged lockfiles and migration bytes checked |
| Cluster state | Both existing k3d containers remained exited throughout this review; no Kubernetes start, rollout or fault injection |

TypeScript configuration files use JSON with comments and are validated by
`tsc -b`, rather than a strict JSON parser. The four held-out dataset files retain
their original byte hashes. Docker image context hashes identify the built
application source; no claim of byte-reproducible images is made.

The final diff review caught and corrected Unicode punctuation conversion before
closing. The unchanged operational pages and palette were compared directly with
the checkpointed original source. Generated Dockerfile strings from the moved
platform tooling were also evaluated and compared against the original output.

### Exact aggregate commands

These commands were executed by the final source gate. All returned zero.

- `uv run --project apps/control-plane --locked ruff check --config apps/control-plane/pyproject.toml scripts conftest.py`
- `uv run --project apps/control-plane --locked ruff format --check --config apps/control-plane/pyproject.toml scripts conftest.py`
- `uv run --project apps/control-plane --locked ruff check apps/control-plane`
- `uv run --project apps/control-plane --locked ruff format --check apps/control-plane`
- `uv run --project apps/control-plane --locked python -m pytest apps/control-plane/tests scripts/platform/tests scripts/reliability/tests scripts/cloud/tests -q`
- `uv run --project apps/demo-workload --locked ruff check apps/demo-workload`
- `uv run --project apps/demo-workload --locked ruff format --check apps/demo-workload`
- `uv run --project apps/demo-workload --locked python -m pytest apps/demo-workload/tests -q`
- `npm.cmd --prefix apps/web run lint`
- `npm.cmd --prefix apps/web run test`
- `npm.cmd --prefix apps/web run build`
- `uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.reliability.validate_charts`
- `node --check benchmarks/k6/jobs.js`
- `git diff --check`

Additional executed native and integration commands were:

```text
python -m scripts.reliability.validate_postgres --browser
python -m scripts.reliability.build_images_local
python -m scripts.reliability.smoke_images
python -m scripts.reliability.inspect_image_runtime
python -m scripts.reliability.scan_images
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python scripts/platform/validate_charts.py
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python scripts/platform/validate_gateway.py
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python scripts/platform/security_checks.py
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/terraform validate -json
.runtime/m5/security-tools/gitleaks.exe git . --redact --no-banner --report-format json --report-path .runtime/verification/repository/history-secrets-reviewed.json
npm.cmd --prefix apps/web audit --json
.cache/tools/actionlint/1.7.12/actionlint.exe -shellcheck=
git diff --cached --check
```

The Python module commands above used
`apps/control-plane/.venv/Scripts/python.exe`. The command log for Compose contains
the full `docker compose -f ... config --quiet` command for every profile in
`.runtime/verification/repository/compose.json`. Exact native gate commands and
initial exit codes are in `native-checks.json` beside it. Its initial history-scan
failure is retained, with the reviewed successful rerun in
`history-secrets-reviewed.json`; the initial failure is not overwritten.

Final source gate: `.runtime/verification/source/checks-3684498dbd0a49aca6c3d43e94027c29/result.json`.
SQL/browser receipt: `.runtime/m6/acceptance/postgres/opsproof-m6-pg-test-3cf252c102/result.json`.
Final image scan: `.runtime/m6/acceptance/images/scan-73c67f94937c4ceda89aaa98e5c65420/result.json`.

| Component | Final image | Local image ID |
|---|---|---|
| demo | `opsproof-demo:src-cf28d11cf0705eb1` | `sha256:a0d2a1fd590b9585acfebf9c9ba9b03fc7d7b66d4c573e5ad007f15ddd9fd553` |
| control | `opsproof-control:src-ecd7cf563ceb0a6b` | `sha256:5dfae56d279b70a89662675312f54a23b2aa92af911646629a8410e7f8f2595a` |
| web | `opsproof-web:src-839fe954902e5dd6` | `sha256:9e0a56bfb5ef170eade6593132a6d63a4e99bbb5eb1b3b6cd8f174170780c7ff` |

Twenty disposable image-scan tar exports were removed only after confirming
their completed scan reports and matching image IDs still existed in Docker.
This recovered 955.3 MiB in
addition to the seven ZIP packages. Four exports remain because the original
image IDs are unavailable locally, so they preserve distinct evidence. Their
retention/removal manifest is `.runtime/evidence/removed-image-exports.json`.
Generated obsolete cache/test directories were removed, including the seven
owner-restricted scratch directories after using their actual sandbox owner.

## Acceptance boundary

Repository standardization is complete within the verified local scope. The known
base-image vulnerability findings remain explicitly open. GitHub-hosted workflows
were validated locally but not run remotely. No new Kubernetes integration/fault
run or final AWS acceptance is claimed. M7 requires the owner's next approval.

### Final checkout identity

After the local fast-forward, Git normalized only line endings in `types.ts` and
`investigations.css`. Their previous hashes matched the exact CRLF representation
of the current files. The web image was rebuilt from the final clean checkout,
then all image smoke checks and the final vulnerability scan were repeated. All
three component context hashes now match the final checkout exactly. The final
web build command and identity are in
`.runtime/verification/repository/final-web-image.json`. Both k3d containers stayed
exited; Docker Desktop was restored to its original stopped state after validation.
