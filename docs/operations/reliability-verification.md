# Reliability verification runbook

Updated 24 November 2026. The [acceptance report](../history/reliability-trials-acceptance.md) and [matrix](../history/reliability-acceptance-matrix.md) identify the executed results and remaining reviews.

## Toolchain and source checks

Use Python 3.14, pinned uv and the repository's Node/npm toolchain. Chart checks use the pinned PyYAML tooling environment; Kubernetes checks require Helm/kubectl/k3d, and load checks require k6. Only live checks require a running local cluster and private configuration. Source and mocked infrastructure checks do not.

Run these commands from the repository root in Windows Git Bash. Each source validator invocation creates a unique evidence directory.

```bash
uv sync --project apps/control-plane --locked
uv sync --project apps/demo-workload --locked
npm.cmd --prefix apps/web ci
uv run --project apps/control-plane --locked python -m scripts.reliability.validate_source
```

The source validator runs Python lint/format/regressions, frontend lint/tests/build, 25 Helm profiles, k6 syntax, whitespace and the pinned source secret scanner. SQL tests require the separate real database validation below. In managed Windows sessions, an explicit writable `UV_CACHE_DIR` can be set for uv's cache.

The final implementation was also verified from a fresh detached Git worktree. Both Python environments and npm dependencies were installed from their locks using cached packages. The saved import provenance points into that worktree. Its commands, outputs and source hashes are in the reproduction evidence.

## Real SQL and isolated browser validation

```bash
uv run --project apps/control-plane --locked python scripts/reliability/validate_postgres.py --browser
```

This command requires local Docker access and creates an owned disposable PostgreSQL 18 container on localhost port 15432. It migrates through the preserved baseline schema, inserts preservation data, upgrades to head (`0008`) and runs the selected real SQL integration suites, including alert concurrency and AI-worker ownership. The browser option exercises a real isolated API/database using the existing frontend. The harness removes its container and stops its servers. A passing result includes migration, preserved rows, integration, browser and cleanup checks.

Use the [latest verification receipt](../engineering/verification.md#repository-finalization-follow-up--24-november-2026) for current source/test identities. Earlier acceptance records remain bound to their original source; they do not certify later changes.

## Local deployment and resource profile

```bash
python -m scripts.reliability.start_local
```

Startup uses the existing k3d cluster and explicit `.runtime/platform/kubeconfig.yaml` context `k3d-opsproof`. It checks the existing 5 GiB host RAM, 5 GiB Docker capacity and 15 GiB disk floors and preserves PVC identities. It refreshes the reviewed private API endpoint peers when required.

Active trials require 2 GiB free host RAM and 15 GiB free disk, with the existing 1 GiB emergency stop. Live Kubernetes node identity, Ready status and at least 5 GiB node capacity establish the running cluster's capacity. The verified node exposes six CPUs and approximately 9.7 GiB memory. Active trials can use that API measurement when the desktop sandbox cannot open Docker's Windows pipe.

Historical deployment records bind actual source/image, role and Secret identities. Inspect a current deployment independently; do not use an old commit or migration as its expected identity. HTTP arming and AI remain disabled by default.

The optional measurement profile pauses Grafana and the Argo CD UI server while controllers, collectors, data services and the OpsProof UI run. Every accepted capacity trial used that profile. Restore and verify both UIs after measurements.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.ui_test_profile restore
```

## Bounded fault trials and reconciliation

Review [the local execution profile](local-trials.md) before dispatch. The CLI acknowledges a local fault experiment, verifies a healthy baseline and creates a new durable trial.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.run_local_trial --scenario worker_saturation --acknowledge M6_LOCAL_FAULT_TRIAL
```

The fixed catalog also includes `faulty_release`, `database_connectivity`, `worker_failure`, `downstream_latency` and `misleading_evidence`. The worker-failure CLI uses exact Pod deletion. A short job can complete during shutdown, producing a failed hypothesis with verified cleanup. The passing hard-crash evidence used the owner's separately approved one-off container signal test. Its exact helper and target guards are retained with the local-review evidence.

Success requires an independent matching hypothesis and cleanup receipt. Missing hypothesis evidence can produce a failed trial after restoration. Unknown dispatch or restoration retains an indeterminate record. Cleanup reconciliation appends evidence and releases the reservation when restoration is independently established.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.reconcile_local_trial --run-directory .runtime/reliability/trials/RETAINED_RUN_ID --acknowledge M6_RECONCILE_ONLY
```

Use the actual retained run directory. Reconciliation uses the original checkpoint and performs cleanup only. Inspect the original result, reconciliation result, independent receipt and access-cleanup record together.

## k6 and capacity measurements

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.run_k6_local --run-id m6-local-example-01 --rate 2 --seconds 30 --duration-ms 250 --vus 4 --acknowledge M6_LOCAL_DURABLE_JOBS
```

Choose a fresh lowercase run ID matching the CLI contract. This profile submits exactly 60 bounded jobs and reconciles their durable outcomes. The recorded stop test injected a below-threshold memory reading, stopped an actual owned k6 process and checked both submitted jobs in PostgreSQL and Redis.

```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.run_local_trial --scenario worker_saturation --capacity-mode fixed --acknowledge M6_LOCAL_FAULT_TRIAL
uv run --project apps/control-plane --locked python -m scripts.reliability.run_local_trial --scenario worker_saturation --capacity-mode hpa --acknowledge M6_LOCAL_FAULT_TRIAL
uv run --project apps/control-plane --locked python -m scripts.reliability.run_local_trial --scenario worker_saturation --capacity-mode keda --acknowledge M6_LOCAL_FAULT_TRIAL
```

Execute sequentially and collect at least three independently passing trials per mode under the same profile. The capacity protocol uses 60 jobs at 2,000 ms, a 120-second background target of 80 requests per second, bounded concurrency and nearest-rank percentiles. Actual served rates, failures, IDs, resource samples and scale transitions are retained. Failed attempts keep their original outcome. The analysis CLI accepts repeated `--trial MODE:PATH` arguments and requires all three modes with at least three valid equivalent trials.

## Additional verification and evidence review

The retained operator checks deploy the existing reuse Helm contract, collect actual normal/delayed/recovered investigations, verify unsupported targeting and remove the owned resources. The image comparison uses preserved M5 and current M6 images with the same read-only protocol and limits. The deployed browser check covers authentication, CSRF, actual trial evidence, desktop/mobile navigation, accessibility and session revocation.

Deterministic synthetic diagnosis uses the versioned dataset. The NVIDIA adapter subsequently passed its frozen 42-case development qualification; earlier Groq/Gemini failures remain historical evidence. Runtime AI stays disabled. See [the current decision](../engineering/advisory-evaluation.md). No provider rerun is needed for routine source verification. AWS acceptance remains owner-run.
```bash
uv run --project apps/control-plane --locked python -m scripts.reliability.qualify --provider deterministic --output .runtime/reliability/acceptance/NEW_DETERMINISTIC_RESULT.json
```

Earlier provider receipts remain private historical evidence. Preserve failed/unknown outcomes; use the current advisory decision for present qualification status.
