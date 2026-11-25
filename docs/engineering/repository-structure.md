# Repository structure and compatibility

OpsProof has three independently deployed applications and a minimal public edge.
The web UI calls the authenticated control API. Dedicated control-plane processes
collect evidence, investigate incidents, reconcile bounded actions and verify
outcomes. The demonstration workload owns its database and queue processing.
See [system architecture](../architecture/system.md) for these boundaries.

```text
apps/
  control-plane/     API, workers, migrations and application tests
  demo-workload/     Queue demonstration, migrations and application tests
  web/               Operator UI, component tests and browser tests
  edge-proof/        Isolated read-only public evidence page
benchmarks/          Frozen incident datasets and load-generation definitions
conftest.py          Shared test collection setup
scripts/
  compose/           Docker Compose preparation and verification
  platform/          Local Kubernetes, GitOps, gateway and platform checks
  reliability/       Trials, evidence, capacity, cost and verification
  cloud/             Cloud preparation, release contracts and owner safeguards
  paths.py           External cache/tool storage and historical evidence lookup
  security_tools.py  Checksum-pinned security tool bootstrap
infra/
  helm/              Application and dependency charts
  k8s/               Local/cloud controllers, policies and GitOps configuration
  terraform/         Independent state-bootstrap, platform and public-edge roots
  emulator/          Signed local AWS Emulator test packaging
  k3d/               Local cluster definition
observability/       Metrics, alerts and dashboards
.github/             CI, release and dependency update automation
docs/
  architecture/      Current design and UI conventions
  engineering/       Current structure, verification and AI qualification decision
  operations/        Maintained local operating procedures
  cloud/             Owner preparation, deployment, proof and teardown
  history/           Selected local acceptance and measured evidence
```

Root Compose overlays are separate opt-in recovery, telemetry and integration
configurations. They remain at the root because existing commands and build
contexts use them. Package markers, matching Python version files and per-service
shutdown code support independently built applications; they are intentional.

## Naming and compatibility

Use Python snake_case for modules/functions/tests, PascalCase for classes and
React components, kebab-case for documentation and infrastructure names, and
existing platform conventions for environment variables and SQL objects. Name
tests after behavior, not milestones. Run tooling from the repository root with
`python -m scripts.<responsibility>.<module>` so package imports are consistent.

Maintained tooling uses `platform`, `reliability`, `cloud` and `compose` names.
Legacy `/api/v1/m6` routes, `OPSPROOF_*_M6_*` settings, Helm `m6` values, SQL names,
migration revision IDs and frozen benchmark bytes remain compatibility contracts.
Historical documents use descriptive filenames. Original dates and milestone
labels stay in the records for provenance. Preserve original runtime evidence
locators and compatibility identifiers when renaming documents.

## Generated files and retention

Git tracks source, lockfiles, configuration and curated documentation. It ignores
`.env`, `.runtime`, dependencies, build output, bytecode and caches. Source and
lockfiles are required; installed `.venv` and `node_modules` are normal disposable
local dependencies. A large Explorer count is not the Git source count.

Current verification output stays under ignored `.runtime/verification`;
current local platform configuration uses `.runtime/platform`, and current
trial/build tooling uses `.runtime/reliability`. Preserve active kubeconfigs,
webhook tokens, private trial evidence and image exports until their retention
conditions have been checked. Never use a broad `git clean -fdx` as cleanup.

Large tools, package caches, isolated Terraform validation data and retained
historical records live outside the checkout:

- Windows: `%LOCALAPPDATA%/OpsProof`.
- Linux: `${XDG_CACHE_HOME:-~/.cache}/opsproof`.
- Override: absolute `OPSPROOF_LOCAL_DIR`, outside the source checkout.
- `tools/`: pinned scanner/plugin binaries; `cache/`: regenerable downloads.
- `terraform/validation/`: per-checkout, per-root backend-free validation data.
- `private/checkpoints/`: verified private configuration checkpoints.
- `private/archive/legacy-runtime/`: preserved historical evidence with original
  bytes/locators. Windows private storage has owner/SYSTEM-only ACLs.
- `private/archive/documentation-finalization/` retains the original reviews and
  interim reports removed from the working tree, with their paths and SHA-256
  hashes in the archive manifest.

`scripts.paths.read_artifact` resolves current paths, old `.runtime/m5` and
`.runtime/m6` aliases, then private archived originals. Isolated test checkouts
cannot silently consult another checkout's historical archive. Archived handover
copies may have Windows paths longer than 260 characters; use extended-length
paths for exhaustive archive inspection. They are not build inputs.

Relocation reduces checkout size; it does not free disk by itself. Hash-verified
provider hardlinks remove duplicate payloads. Unique evidence is archived, not
deleted. Retention inventories and private reports stay outside the public source.

## Reproduction and verification

Copy `.env.example` only when `.env` does not exist, generate independent local
passwords/tokens, and leave AI/recovery disabled. Never copy another checkout's
secrets, installed environments or `.runtime` into a reproduction checkout.

```text
uv sync --project apps/control-plane --locked
uv sync --project apps/demo-workload --locked
npm --prefix apps/web ci
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.reliability.validate_source
uv run --project apps/control-plane --locked python -m scripts.cloud.validate_infrastructure
uv run --project apps/control-plane --locked --with PyYAML==6.0.3 python -m scripts.cloud.validate_schemas
```

The source gate renders charts before the schema gate. Public dependency/schema
registries may be needed; these commands need no model key or AWS account.
Terraform validation uses external data and committed mocks; it never initializes
a state backend or runs apply. Docker integrations are separate bounded checks
and remove only their owned resources. Local Kubernetes need not be running.
Historical commands in `docs/history` refer to their recorded revisions.

See [cloud readiness](../cloud/readiness.md) for the distinction between local
verification, hosted release proof and owner-run cloud acceptance.


## Dependency updates and commit identity

The existing Dependabot configuration proposes monthly Python, npm, Docker and
Action updates. It does not authorize automatic merges. Review compatibility,
security and the resulting commit attribution before accepting a proposal.
The current local history contains the owner's identity; that is not a guarantee
about future automated commits or GitHub's contributor display. The owner decides
whether to retain update PRs or replace them with a manual review process.
Do not falsify third-party authorship or disable security updates silently.
