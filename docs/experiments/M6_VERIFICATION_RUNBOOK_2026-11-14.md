# M6 verification and continuation runbook — 14 November 2026

The [acceptance report](M6_ACCEPTANCE_REPORT_2026-11-14.md) defines the current
limits. These commands reproduce isolated checks. They do not accept the six
live adapters or authorize cloud/model spending. All paths below start at the
repository root. PowerShell and Windows Git Bash can run these commands; use
`npm` in Git Bash if `npm.cmd` does not resolve.

## Prerequisites

- Python 3.14.10 and uv 0.13.7 for the locked applications; Node/npm from the
  existing project toolchain; installed Playwright Chromium.
- Docker Desktop Linux engine for disposable PostgreSQL and image checks.
  Keep the full k3d cluster stopped during these isolated checks.
- Helm, k3d, kubectl and k6 for later live work. Native chart validation currently
  also uses Python 3.12 with PyYAML; this helper dependency is outside app locks.
- Local Gitleaks 8.30.1 archive/executable under `.runtime/m5/security-tools`,
  verified by the checksum in `scripts/m6/validate_source.py`. Trivy 0.76.2 is
  downloaded and checksum checked by the image scanner.
- Preserve `.env`, `.runtime`, kubeconfig and existing Docker data locally.
  Do not copy them into source or public artifacts. The source zip deliberately
  excludes them and is not a ready-to-run configured deployment.

## Isolated checks

```bash
uv sync --project apps/control-plane --locked
uv sync --project apps/demo-workload --locked
npm.cmd --prefix apps/web ci
node apps/web/node_modules/@playwright/test/cli.js install chromium
python -m scripts.m6.validate_source
```

`validate_source` runs locked Python lint/format/tests, web lint/unit/build,
21 Helm profiles, k6 syntax, whitespace and a source secret scan. It writes
unique `checks-*` directories under `.runtime/m6/acceptance/source` and requires
an unchanged source hash throughout. SQL tests skipped here must pass below.
The scanner is currently a native Windows helper; Linux CI uses its own pinned
checks rather than this Windows wrapper. Installing dependencies can require
network access; the tests do not call real model providers.

```bash
uv run --project apps/control-plane --locked python scripts/m6/validate_postgres.py --browser
```

This launches an owned PostgreSQL 18 container on localhost port 15432, migrates
to 0005, inserts an M5 preservation sentinel, applies 0006 and runs real SQL/API
tests. `--browser` adds actual FastAPI and Playwright on local ports 8090/5173.
The script uses a random ephemeral password, an isolated API key and no M5
database credentials. It removes its owned container and stops its servers.
Expected result: `passed: true`, `m5_rows_preserved: true`, browser exit zero and
`cleanup_verified: true`. Do not point its SQL tests at a real database.

```bash
uv run --project apps/control-plane --locked python -m scripts.m6.qualify --provider deterministic --output .runtime/m6/acceptance/deterministic-qualification.json
python -m scripts.m6.build_images_local
python -m scripts.m6.inspect_image_runtime
python -m scripts.m6.smoke_images
python -m scripts.m6.scan_images
python -m scripts.m6.fetch_pricing
python -m scripts.m6.finops_model
```

The deterministic check uses the versioned synthetic dataset. It is not a
Groq/Gemini comparison. Image builds need 2 GiB free host RAM and stop below
1 GiB. They tag local images, record exact local image IDs and publish nothing.
Runtime inventory and smoke checks use isolated nonroot containers with no
network. Missing downstream databases intentionally cause readiness 503 while
liveness remains 200. Trivy saves and scans the exact local image IDs, including
unfixed vulnerabilities. Inspect the findings; a successful scanner process
does not imply security acceptance. Pricing downloads are public AWS catalogs,
not account APIs; the model uses selected Mumbai rows fetched within 24 hours.

The source and evidence archives include SHA-256 manifests. Compare hashes
before reviewing or sharing. Full browser traces may carry ephemeral session
material and remain private outside the selected evidence archive.

## Live continuation is still experimental

Do not treat the following sequence as an already accepted deployment recipe.
First resolve restricted actuator authority and trusted verification producers
listed in the report. Then review the fixed protocols in
[M6_LOCAL_EXECUTION_PROFILE.md](M6_LOCAL_EXECUTION_PROFILE.md), including their
resource bounds and original-state restoration rules.

```bash
python -m scripts.m6.start_local
```

This starts the existing `k3d-opsproof`, preserves its volumes, verifies its
identity and refreshes narrowly validated private API endpoint peers in the two
existing policies. It requires the existing 5 GiB startup resource floor.
It does not deploy the new M6 images or migrate the M5 control database.
After startup, require the full known-good stack and at least 2 GiB free RAM;
stop below 1 GiB. The previous attempt failed this gate. A larger machine or
an explicitly reviewed infrastructure change is required before live load.

Review `python -m scripts.m6.run_local_trial --help` for the explicit
`M6_LOCAL_FAULT_TRIAL` acknowledgment, six allowed scenario identifiers and
optional capacity modes. There is no accepted live example command in this
handover because authority and runtime verification remain incomplete. Keep
arming and all experiment flags off until those gaps are resolved. Separate
fixed/HPA/KEDA comparisons require at least nine passing comparable runs, not
one run per mode. Keep every failed and aborted attempt.

If a trial becomes uncertain, retain its reservation. Establish original
resource identities and verify current cleanup independently before recording
reconciliation. Do not edit the terminal row or call an indeterminate trial a
success. Restore only owned configuration; do not delete the cluster, its PVCs,
or broad Docker volumes. `ui_test_profile.py restore --stop-cluster` is the
specific recovery used for the optional UI pause; its record says replicas
were restored but readiness was not verified before stopping.

Real Groq/Gemini evaluation remains blocked by the user's current instruction.
Do not add authorization flags or use provider credentials to bypass it. AWS
infrastructure creation and M7 promotion are outside this local handover.
